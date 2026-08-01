# Decisions

A running log, newest first. Each entry: what was chosen, what was
considered instead, and why.

---

## Multi-branch simultaneous faults tested and verified

The seeded `pole_registry.csv` includes a genuine branch (P-3 feeds both
P-4→P-5→P-6 and P-7→P-8 as two independent lines), specifically to exercise
the "multiple simultaneous faults" requirement rather than leave it
theoretical. Injecting a fault on each branch at the same time produces two
separate fault cards on the console, each with the correct span and
downstream count, neither merged into the other nor mistaken for one
incident. This was verified manually via the simulator before recording
the demo video.

## Ticket lifecycle not implemented as a persisted state machine

**Chose:** Faults are computed live from telemetry on every request/poll,
not stored as tickets that move through detected → acknowledged → crew
assigned → resolved → verified → closed.

**Rejected:** Building the full state machine with persisted ticket
records and manual acknowledge/assign transitions.

**Why:** Given the time budget, the highest-weighted category (fault
localization, 25%) and the hard gates (Docker, deployment, simulator) were
prioritized first. This is a known, documented gap rather than a silent
one — see "What's next" below. The auto-verification behavior the brief
cares about most (restoration confirmed from telemetry, not a button click)
*is* implemented: a fault clears itself from the active list the moment
telemetry shows the affected poles live again, with no manual step. What's
missing is the intermediate states (acknowledged, crew assigned) and
persistence of resolved tickets for history.

## In-memory state instead of a database

**Chose:** Pole states and fault history live in Python dicts/lists inside
the running process.

**Rejected:** Standing up Postgres (or similar) for persistence.

**Why:** At this assignment's scale, and given the "not asking for
historical analytics" scope note in the brief, persistence wasn't worth the
added deployment surface (a DB service, migrations, connection handling) on
a free hosting tier within the time budget. The tradeoff is explicit: a
server restart loses all state. For a real deployment this would need to
change - flagged in `ARCHITECTURE.md` under "Known limitations."

## Geographic nearest-neighbour inference for missing topology

**Chose:** For the ~60% of transformers with no recorded pole ordering,
infer the parent as the nearest other pole on the same transformer by GPS
distance, and mark that edge's confidence as "low - inferred" rather than
"high."

**Rejected:**
- Degrading to DT-level (not span-level) localization for unknown regions.
- Waiting on the department to run a survey before shipping anything for
  that 60%.
- Learning topology from correlated outage history over time (not enough
  historical data exists yet in a fresh deployment for this to help on day
  one).

**Why:** A radial LT line's physical layout makes geographic adjacency a
reasonably strong prior - poles physically close to each other on the same
transformer are very likely wired together. A specific (if uncertain) span
is more actionable for a crew than "somewhere under this transformer," and
the confidence field means the operator isn't misled about which is which.

**Observed limitation (found during testing, not theoretical):** because
inference reshapes the tree, an inferred parent-child link can misfile a
pole under the wrong branch. During testing, injecting a fault at P-4 (a
pole with only one, live, downstream child due to an inferred edge) caused
the system to classify it as a dead sensor rather than a real fault,
because the "all children live" dead-sensor check fired on an incorrect
inferred structure. This is a genuine tradeoff of geographic inference, not
a bug in the check itself — documented rather than hidden. **What I'd fix
with two more weeks:** weight the inference by how many candidate anchors
are nearby (low-density evidence = explicitly lower confidence than a
single confident nearest neighbour) instead of always picking a single
nearest neighbour with no measure of how confident that "nearest" choice
actually was.

## AI feature: natural-language fault summaries, not fault localization

**Chose:** The only LLM touchpoint in the system converts a structured
fault record into a one-sentence operator-facing summary. Localization
itself stays fully deterministic (graph/tree logic in `fault_engine.py`).

**Rejected:** Using an LLM anywhere in the detection/localization path.

**Why:** The brief explicitly warns this will be interrogated hard, and for
good reason — a tree traversal is instant, free, deterministic, and fully
explainable, while an LLM is none of those for a safety-relevant judgment
like "is this a real outage." Communication/summarization is a much better
fit: low-stakes if occasionally imperfect (the structured data is always
shown alongside it, never replacing it), and it degrades safely - see next
entry.

## AI summary has a hard-coded template fallback

**Chose:** If `ANTHROPIC_API_KEY` is unset, or the API call fails/times out
for any reason, the system silently falls back to a templated sentence
built from the same structured data.

**Rejected:** Making the AI summary a hard dependency (if the API call
fails, show an error or omit the sentence).

**Why:** Brief requirement: "what happens when the model is unavailable or
wrong." A control-room tool that partially breaks because a third-party API
is slow or down is a worse outcome than a slightly blander sentence. This
was tested by simply not setting the API key at all during most of
development - the console never looked broken.

## Polling instead of WebSockets

**Chose:** The operator console re-fetches `/faults` and `/poles` every 5
seconds via plain `fetch()`.

**Rejected:** WebSocket push updates for lower latency.

**Why:** The FAQ explicitly flags WebSocket-through-proxy as "a classic
deployment failure" on free hosting tiers, and the brief says polling is
fine if justified. Given the 120-second p95 detection target, 5-second
polling adds negligible latency relative to that budget, and avoids an
entire class of deployment risk on Render's free tier for no real UX cost
at this alert frequency.

## Flask over a heavier framework

**Chose:** Flask, no ORM, no separate frontend build step - the dashboard
is server-rendered HTML with vanilla JS `fetch()` calls.

**Rejected:** FastAPI + a React frontend.

**Why:** Fastest to build correctly within the time budget, and the brief
explicitly says the stack is the candidate's choice with no hidden
favourite. A build step (npm, bundlers) is one more thing that can break in
someone else's Docker environment; keeping the frontend as static HTML
served by Flask removes that entire failure class.

## Scheduled outages checked at the DT and feeder level

**Chose:** A fault is suppressed if either its pole's `dt_id` or
`feeder_id` is covered by a published outage window, with a 45-minute grace
buffer added to the stated end time.

**Why the grace buffer:** the brief states shutdowns "start late and
overrun by 20-40 minutes routinely." Trusting the published end time to the
minute would cause real faults occurring in that overrun window to be
wrongly suppressed - the buffer is a deliberate, documented safety margin.

**Known gap:** the brief also notes about 1 in 10 scheduled outages is
cancelled without the feed being updated - meaning poles that go dark
during a "scheduled" window that was actually cancelled would be incorrectly
suppressed. This has no computational fix without a live feed - flagged as
a real operational risk to surface to the department in production, not a
software bug.

---

## Bug encountered and fixed during development

**Flask defaulted to `host="127.0.0.1"`.** This works fine when running
`python app.py` directly, but inside Docker it means the server only
listens for connections from inside its own container - `localhost:5000`
on the host machine gets a connection refused, even though `docker ps`
shows the container as healthy. Fixed by explicitly binding to
`host="0.0.0.0"`. Left in `DEPLOYMENT.md`'s troubleshooting section because
it's a genuinely common trap, not just a note-to-self.

**Werkzeug's debugger reserves the `/console` path.** The first version of
the operator console route was `/console`, which silently collided with
Flask's built-in interactive debugger (enabled via `debug=True`), which
intercepts that exact path for its own use. The route was renamed to
`/dashboard` to avoid the collision.

---

## What's next (with two more weeks)

1. Implement the full ticket state machine (detected → acknowledged → crew
   assigned → resolved → verified → closed) with persistence, so tickets
   survive a restart and build a real incident history.
2. Move state to Postgres; add a proper migration step.
3. Load-test ingestion against the stated targets (500 msg/s sustained,
   5,000-message burst in 10s) - currently unverified.
4. Improve topology inference to report a confidence *score*, not just a
   binary known/inferred flag, weighted by how many nearby anchors were
   available.
5. Add tests beyond the localization logic - currently only the core
   `find_faults` behaviour is exercised via manual/scripted checks, not a
   formal test suite in CI.

## What is currently known to be wrong or fragile

- No persisted ticket history - a server restart wipes all fault state.
- Scheduled-outage cancellation isn't detected (see above).
- The dead-sensor heuristic can misfire under inferred topology, as
  documented above.
- No authentication on the simulator endpoints - anyone with the URL can
  inject/repair faults. Acceptable for this assignment's scope (brief says
  auth is explicitly out of scope) but would need to change before any
  real deployment.

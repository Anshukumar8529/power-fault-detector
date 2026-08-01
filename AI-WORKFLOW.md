# AI Workflow

## Tools used

- **Claude** (chat-based, in a single continuous conversation) for design
  discussion, writing nearly all the code, debugging, and explaining
  concepts as I went. I do not have a strong prior background in backend
  systems or Docker, so I used it heavily and deliberately as a learning
  tool as well as a code generator — I asked it to explain each piece
  before moving on, rather than just accepting output.

I did not use a separate AI coding agent (e.g. Cursor/Copilot) — everything
went through one conversational thread, which is also why the reasoning
behind each decision is fairly traceable in that transcript.

## What I delegated vs. what I did myself

**Delegated to AI (wrote the actual code):**
- The core localization algorithm (`fault_engine.py`) — boundary detection,
  downstream grouping, the dead-sensor filter.
- The topology loader and missing-data inference (`topology_loader.py`).
- The Flask API, simulator, scheduled-outage suppression, and AI-summary
  module.
- The operator console HTML/CSS/JS.
- Docker configuration (`Dockerfile`, `docker-compose.yml`).
- First drafts of all five markdown documents, including this one.

**Did myself:**
- Every actual run, test, and verification — I did not take "it should
  work" as an answer at any point. I ran the fault-detection script myself
  before trusting it, tested every API endpoint via Thunder Client, and
  visually confirmed the dashboard behaved correctly (injecting and
  repairing faults, watching poles change state, watching the fault card
  disappear on auto-verify) before considering any feature done.
- Diagnosing environment problems on my own machine (see below) — AI
  proposed fixes, but I was the one running commands and reporting back
  exact error text, which is how we converged on the actual cause each
  time.
- All Git operations, GitHub setup, and Render deployment.
- Reading and understanding each explanation before moving to the next
  step — I deliberately worked through the boundary-detection logic by
  hand on paper examples before letting AI write the corresponding code,
  specifically so I could verify the code matched logic I already
  understood, not the other way around.

## Roughly how much of the final code is AI-generated

Honest estimate: **around 90%** of the actual code text was written by
Claude. What I contributed was direction (what to build next, in what
order), verification (running everything and reporting real output back),
and the underlying conceptual understanding needed to catch it if
something looked wrong. I can explain what every file does and why it's
structured the way it is, because each piece was explained to me before or
while it was written, and I tested each one before moving forward — I
expect to be able to walk through `fault_engine.py` line by line on the
follow-up call.

## Cases where AI output was wrong or needed correction

**1. A route name collided with Flask's own debugger.**
The operator console was originally built at `/console`. When I loaded it
in the browser, I got Werkzeug's interactive debugger console screen
instead of my dashboard — not an error, just silently the wrong page. This
wasn't obvious from the code itself; it only showed up when I actually
opened the URL and looked. The fix was renaming the route to `/dashboard`.
This is the kind of bug that AI-generated code can introduce silently
because the code is syntactically valid Python that happens to shadow a
framework internal — it only surfaces by actually running the thing, which
is why I insisted on testing every step rather than reading code and
assuming it was correct.

**2. Flask defaulted to binding `127.0.0.1`, which broke inside Docker.**
Code that worked perfectly when I ran `python app.py` directly failed
silently inside the Docker container — the container reported healthy, but
`localhost:5000` refused to connect from outside it. This is a classic
container-networking trap, and it wasn't caught until I actually ran
`docker compose up` and tried to open the browser. The fix
(`host="0.0.0.0"`) is one line, but finding *which* one line required
actually reproducing the failure rather than reading the Dockerfile and
assuming it would work.

**3. Inferred topology silently changed a fault-detection outcome.**
When I switched from a hand-written test topology to the CSV-based loader
with GPS inference, one of the faults I expected to see (a fault at P-4)
disappeared — not because of a code bug, but because the inferred parent
structure legitimately differed from the hardcoded example I'd tested
earlier, which changed which pole was classified as a "dead sensor" versus
a real fault. This wasn't AI being "wrong" in the sense of a bug, but it
was a case where I had to slow down, understand *why* the output changed,
and confirm it was a genuine consequence of the inference approach rather
than a regression — I wrote this up in `DECISIONS.md` because it's a real,
demonstrable limitation of geographic topology inference, not a
hypothetical one.

**4. Initial Python environment troubleshooting took several iterations.**
Not an AI code defect, but worth noting: my machine had a stale Python 2.7
install shadowing a newer Python 3 install in PATH, plus Windows Store
execution aliases interfering with `python3`. The first couple of proposed
fixes didn't fully resolve it — what actually worked was switching to the
`py -3` launcher, which came out of iterating on the *exact* terminal
output rather than a generic "reinstall Python" suggestion.

## What I consider my best work in this collaboration

The back-and-forth around the missing-topology problem (`02-data-and-
systems.md` §3) — I made sure I understood the physical reasoning (radial
network, live/dark boundary as the fault signal, why an isolated dark pole
with live children can't be a real outage) by working through paper
examples by hand *before* any of that logic was written as code. That's
also why I was able to notice and correctly interpret the P-4 discrepancy
in point 3 above, rather than assuming something was broken.

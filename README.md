# Power Grid Fault Detection & Localization System

A system that detects and localizes faults on a low-tension power distribution
network from pole-level "live/dark" telemetry, groups symptoms into a single
incident, and gives the control room a span-level location, a PIN code, and a
confidence rating — instead of the two-hour manual walk-the-line process
described in the assignment brief.

Built for the Propel AI Product Engineer take-home assignment.

---

## What it does

- Ingests telemetry from pole devices (`POST /telemetry`)
- Loads the pole network from a CSV registry, including transformers where
  the pole ordering was never digitized — and infers the likely topology
  geographically for those, flagging the result as lower confidence
- Localizes faults as the boundary between the last live pole and the first
  dark pole, and groups all downstream dark poles into a single incident
  rather than one alert per pole
- Distinguishes a real fault from a single lying sensor (a dark pole with
  live children is physically impossible as an outage)
- Ships a fault simulator so the system can be exercised without real
  hardware — inject a fault at any pole, then repair it, and watch the
  system detect, localize, and auto-clear it from telemetry alone
- A live operator console showing pole status and active faults, refreshing
  every 5 seconds

## Quick start

```bash
git clone <this-repo-url>
cd power-fault-detector
docker compose up
```

Then open:

- **Operator console:** http://localhost:5000/dashboard
- **API root:** http://localhost:5000

No manual setup, no migrations, no separate services — the pole registry is
seeded from the committed `pole_registry.csv` at startup.

## Live deployment

- **Live URL:** https://power-fault-detector.onrender.com/dashboard
- Hosted on Render's free tier, which cold-starts after inactivity — if the
  first load is slow, that is why. Give it 30-60 seconds.

## Using the simulator

From the dashboard: pick a pole from the dropdown, click **Inject Fault**.
Within 5 seconds the fault appears in the Active Faults panel and the
affected poles turn dark in the Pole Status panel. Click **Repair** on the
same pole to restore it — the ticket clears itself from telemetry, with no
manual "mark as fixed" step.

The same actions are available directly via the API:

```bash
curl -X POST http://localhost:5000/simulator/inject-fault \
  -H "Content-Type: application/json" \
  -d '{"pole_id": "P-3"}'

curl -X POST http://localhost:5000/simulator/repair-fault \
  -H "Content-Type: application/json" \
  -d '{"pole_id": "P-3"}'
```

## Documentation map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — data flow, the localization
  algorithm, the missing-topology approach, API surface, UI reasoning
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — environment variables, exact run
  commands, troubleshooting
- [`DECISIONS.md`](DECISIONS.md) — assumptions made, what was cut, what's
  next
- [`AI-WORKFLOW.md`](AI-WORKFLOW.md) — how AI tooling was used while
  building this

## Demo video

[link to be added]

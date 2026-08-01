# Deployment

Written for someone who has cloned this repo and nothing else.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Docker | 24+ | Docker Desktop on Windows/Mac, or Docker Engine on Linux |
| Docker Compose | v2+ | Ships with modern Docker Desktop as `docker compose` (no hyphen) |

No local Python install is required - everything runs inside the container.

## Running locally

```bash
git clone <this-repo-url>
cd power-fault-detector
docker compose up
```

First run will pull the `python:3.12-slim` base image and install
dependencies from `requirements.txt` - this takes a couple of minutes.
Subsequent runs are near-instant (Docker caches the image layers).

**How to verify it worked:**

1. Open http://localhost:5000 — you should see "Power Fault Detector API
   Running" with a link to the console.
2. Open http://localhost:5000/dashboard — you should see the operator
   console with 6 seeded poles, all showing "live".
3. In the dashboard, pick any pole from the Simulator dropdown and click
   **Inject Fault**. Within 5 seconds a fault card should appear on the
   left with a span, an AI-generated summary sentence, and a confidence
   badge, and the affected poles on the right should turn dark.
4. Click **Repair** on the same pole. The fault card should disappear and
   the poles should turn live again, with no manual "mark as resolved"
   step.

If all four of those work, the stack is healthy.

## Environment variables

| Variable | Required? | Default if unset | Purpose |
|----------|-----------|-------------------|---------|
| `ANTHROPIC_API_KEY` | No | *(unset)* | Enables real LLM-generated fault summaries. Without it, the system automatically falls back to a templated summary — the console still works fully, just with a plainer sentence. See `ai_summary.py`. |

To set it locally, create a `.env` file (not committed) and reference it in
`docker-compose.yml`, or export it before running:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up
```

No other configuration is required. There is no database to migrate and no
secrets file to create — the pole registry is a plain committed CSV.

## Live deployment (Render)

The hosted instance (https://power-fault-detector.onrender.com) is deployed
on Render's free web service tier, connected directly to this repo's `main`
branch for auto-deploy on push.

- **Build command:** none needed — Render builds directly from the
  `Dockerfile`.
- **Start command:** none needed — uses the Dockerfile's `CMD`.
- The free tier spins down after inactivity. The **first request after a
  period of idleness can take 30-60 seconds** while the instance cold-starts
  — this is expected, not a bug. Subsequent requests are fast.

## How to reset to a clean state

The system holds all telemetry and fault state in memory (see
`ARCHITECTURE.md` for why). To reset:

```bash
docker compose down
docker compose up
```

This restarts the container with a fresh in-memory state and re-seeds the
pole registry from `pole_registry.csv`. No volumes persist data between
restarts by design, at this stage of the project.

## Troubleshooting

**`docker compose up` fails with "port is already allocated"**
Something else on your machine is using port 5000 (on macOS this is often
AirPlay Receiver). Either stop that service, or change the host port in
`docker-compose.yml` — edit `"5000:5000"` to e.g. `"5050:5000"` and then
open http://localhost:5050 instead.

**Build fails partway through `pip install`**
Usually a transient network issue reaching PyPI. Re-run `docker compose up
--build`. If it persists, check that your machine's DNS/proxy settings
allow the Docker daemon outbound network access.

**Container starts but `localhost:5000` refuses to connect**
Check that `app.py`'s last line is `app.run(host="0.0.0.0", port=5000,
...)`. If it says `host="127.0.0.1"` (Flask's default), the server only
listens *inside* the container and is unreachable from the host, even
though the container looks healthy. This one bit us during development —
see `DECISIONS.md`.

**Apple Silicon (M1/M2/M3) / ARM vs x86 image issues**
The `python:3.12-slim` base image publishes multi-arch builds, so this
should pull the correct architecture automatically. If you hit an
`exec format error`, force the platform explicitly:
```bash
docker compose build --build-arg TARGETPLATFORM=linux/arm64
```

**Changes to the code aren't reflected after editing**
`docker-compose.yml` mounts the local folder as a volume for convenience,
but Flask's debug reloader (`debug=True`) should already pick up file
changes automatically. If it doesn't, restart with `docker compose up
--build` to force a clean rebuild.

**Dashboard loads but shows no poles / empty lists**
This means `pole_registry.csv` wasn't found at the expected path inside the
container. Confirm the CSV is in the repo root (not `.dockerignore`'d) and
that `Dockerfile`'s `COPY . .` step ran without errors in the build log.

**AI summaries all show the plain fallback sentence, never the "nicer" LLM
version**
This is expected if `ANTHROPIC_API_KEY` is not set — see "Environment
variables" above. This is a deliberate degrade-safely design, not a bug.

**Memory / free-tier resource limits on Render**
This app is intentionally light (in-memory state, no database), so it fits
comfortably in Render's free tier for this assignment's scale (a few
thousand simulated poles). It has not been tested against the full
38,400-pole production scale — see "Known limitations" in
`ARCHITECTURE.md`.

**WebSocket / CORS issues**
Not applicable — this system uses plain HTTP polling (the dashboard
re-fetches every 5 seconds), not WebSockets, specifically to avoid the
proxy-upgrade failures common on free hosting tiers. See `DECISIONS.md` for
the reasoning.

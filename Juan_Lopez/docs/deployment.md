# Render deployment

The Docker image builds React and serves its files through FastAPI. The browser uses the same HTTPS origin for the website and `/api/v1`; no hardcoded localhost API URL or separate CORS setup is required. Render supplies `PORT` and terminates HTTPS. The container runs as an unprivileged user.

## Deploy the team repository

1. Connect a Render account and grant it access to `kabir-singh19/AICorps4`.
2. Create a Blueprint using the branch containing this change. Set **Blueprint Path** to `Juan_Lopez/render.monorepo.yaml`. That file sets `rootDir: Juan_Lopez`, so the other team folders are excluded from the build context. See [Render's monorepo guide](https://render.com/docs/monorepo-support).
3. Review the `atsc-traffic-safety` service and its Free plan, then deploy. AI is disabled initially and there is no paid AI call during build/startup.
4. Wait for a successful deployment and open the service URL shown by Render. Verify `/api/v1/ready` returns `ready`, the map loads, and `/api/v1/runs` returns the approved published runs (an empty list on a fresh install).
5. Configure approved AI credentials separately using [ai-assistant.md](ai-assistant.md). Do not put credentials in GitHub, frontend variables, or chat messages.

For a separate repository with this app at its root, use `render.yaml` instead. The [Blueprint reference](https://render.com/docs/blueprint-spec) describes these fields. Account access is required to create the service; having these files does not itself deploy a website.

## Manual service alternative

Create a Render **Web Service**, select the repository and branch, choose **Docker**, set **Root Directory** to `Juan_Lopez`, **Dockerfile Path** to `./Dockerfile`, **Docker Build Context** to `.`, and **Health Check Path** to `/api/v1/ready`. Set `ATSC_ENV=production`, a random `ATSC_SESSION_SECRET` of at least 32 characters, and `ATSC_AI_ENABLED=false`. Do not supply a custom start command: the image honors Render's port.

## Local production check

From this app's root, with Docker installed:

```bash
docker build -t atsc-traffic-safety .
docker run --rm -p 10000:10000 atsc-traffic-safety
```

Open `http://localhost:10000/`. AI remains disabled. HTTPS and production project-access cookies must be tested on Render; production cookies are intentionally Secure.

Without Docker, build the frontend and run FastAPI from `backend/` with `ATSC_ENV=production` and `ATSC_FRONTEND_DIST` set to the absolute `frontend/dist` path. FastAPI serves both the files and API. `/api/v1/ready` fails if the frontend build is absent. Readiness does not depend on optional AI credentials or on having model results.

## Data and operating limits

- Only publish model runs approved for a public dashboard. The read API and CSV/GeoJSON downloads are public. The default published directory is empty; the synthetic documentation example is not bundled into it.
- The JSON adapter reads files packaged into the deployed image. Updating local files does not update Render. Publish approved files and redeploy, or implement the team's shared-database adapter. Container writes are not durable storage; this version has no model-upload endpoint or database connection.
- Project access protects AI usage with a shared project password, signed expiring cookies, same-origin checks, and in-process request limits. This is a prototype access mechanism, not TAMU SSO, per-user authorization, or a distributed quota service. Use institutional identity and a shared quota store before a broader operational rollout.
- The Free service can sleep while idle; initial loading can take longer. The map needs internet access and remains subject to [OpenStreetMap's tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Select a suitable hosted tile service before substantial traffic.
- AI failures leave published results, the map, backtests, and downloads available. API responses are not cached by browsers. Generated drafts are not stored or published automatically.
- The production content policy restricts scripts to this origin. Swagger's CDN scripts are consequently blocked in production; inspect `/api/v1/openapi.json` or use `/api/v1/docs` locally for interactive API documentation.

# Lotusbuild Backend

Backend for Lotusbuild — an AI software-builder web app (Devin / v0.dev / Codex-style): a user
describes software in a chat interface and an AI agent builds it, running and iterating on it
live in a real sandbox. This repo is the backend only; the frontend is separate.

Full system design lives in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — read that before
making a structural change. Individual judgment calls are recorded in **[docs/adr/](docs/adr/)**.

## Stack

FastAPI · Firebase Auth + Firestore (the only database) · e2b sandboxes (agent execution) · Redis
(task queue + event bus) · a VPS (control plane + published-app container fleet).

## Running it

There is no local-emulation setup. Development and production run the same way, on the VPS,
against the same real Firebase project (see [docs/adr/0010](docs/adr/0010-shared-dev-prod-environment.md)
for why, and its explicit trigger to change that before launch):

```bash
cp .env.example .env   # fill in real values
docker compose up -d --build
```

This brings up three services: `redis`, `app` (the FastAPI server, port 8000), and `worker` (the
arq background-job worker). `GET /healthz` confirms the app is up and can reach Redis.

## Repository layout

Transport code (`app/api/`, `app/ws/`) is thin; business logic lives in `app/services/`; Firestore
access lives only in `app/repositories/`. See docs/ARCHITECTURE.md §2 for the full map and the
reasoning behind it — this structure is the mechanism that keeps REST and WebSocket paths from
duplicating logic, not just a style preference.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`):
- **Every push/PR**: lint (`ruff`), type-check (`mypy`), unit tests (`pytest`, against a Redis
  service container — no live Firestore in CI).
- **Push to `main`**: after CI passes, deploys to the VPS over SSH (`git pull` + `docker compose
  up -d --build`). Requires these GitHub repo secrets to be set (not something this assistant can
  set for you): `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_APP_DIR`.

## One-time operational setup

- **Daily Firestore backups**: `scripts/setup-firestore-backups.sh <gcp-project-id>
  <backup-bucket>`, run with `gcloud` authenticated against the real project. See
  [docs/adr/0010](docs/adr/0010-shared-dev-prod-environment.md) for why this matters here — dev
  and prod share one Firebase project with no isolation, so this is the cheap insurance against a
  bad script wiping real data.
- **CI/CD deploy secrets**: add `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_APP_DIR` as GitHub
  repo secrets (Settings → Secrets and variables → Actions) for the deploy job in
  `.github/workflows/ci.yml` to work.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions before adding code.

# 0003: Hybrid ephemeral/snapshot sandbox lifecycle

## Status
Accepted

## Context
The agent needs a real compute environment (an e2b sandbox) to write and run code in. Three
shapes were considered:
- **Persistent per project** — one sandbox kept alive for the life of a project. Simple state
  management, but idle compute cost scales directly with the number of projects regardless of
  actual usage, which is a poor fit for paid multi-tenant SaaS.
- **Pure ephemeral per task** — a fresh sandbox from cold on every single agent turn. Cheapest at
  true idle, but cold-start latency on every turn hurts the "watch it build live" UX the product
  needs.
- **Pooled/warm** — a pool of pre-warmed sandboxes reused across users. e2b does not offer this
  natively (confirmed against their docs — see docs/ARCHITECTURE.md Context); it does offer
  **snapshots**, a point-in-time filesystem+memory capture that many sandboxes can restore from.

## Decision
Hybrid: a sandbox provisions when an agent session becomes active, stays warm for a config-driven
idle window, and is captured via an e2b **snapshot** before being suspended/torn down. The next
activity restores from that snapshot instead of a cold rebuild. The snapshot — not the sandbox —
is the durable source of truth for project file state (`projects/{id}.repo_state_ref`).

## Consequences
- The sandbox is a disposable compute surface; losing one is not a data-loss event.
- `sandbox/lifecycle.py` and `workers/sandbox_reaper.py` (an arq scheduled job) own this state
  machine — it is not duplicated in `sandbox_service.py` or anywhere else.
- "Preview" (the live sandbox) and "production" (a promoted container, see ADR 0004) are naturally
  decoupled: the sandbox never needs to live forever just because something was deployed from it.

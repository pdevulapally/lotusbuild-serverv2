# 0004: Preview vs. production deploy split

## Status
Accepted

## Context
Users need to see their app running while the agent builds it, and separately need to be able to
"publish" a stable version. Serving both the same way (e.g. always from the live sandbox) ties
production uptime to sandbox lifecycle (ADR 0003), which is deliberately ephemeral.

## Decision
Split the two concerns:
- **Preview** = the live e2b sandbox itself, reachable while the agent is actively building. No
  separate infrastructure.
- **Production** = a Docker image, built from a snapshot of the sandbox's filesystem, run on the
  VPS container fleet behind a reverse proxy with per-project subdomain routing. Triggered only by
  an explicit "Deploy" action, and built asynchronously (see ADR 0006 / the task queue) rather than
  inline in the request.

## Consequences
- Production availability no longer depends on a sandbox staying alive.
- A separate `deployments/{id}` record tracks production rollout state independent of
  `sandbox_instances/{id}`.
- Redeploy rebuilds from the current snapshot; rollback simply repoints the proxy to a prior image
  tag without rebuilding anything.

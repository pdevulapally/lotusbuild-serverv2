# 0006: Redis for both the task queue and the event bus, from day one

## Status
Accepted

## Context
Two separate needs came up in review: (1) background jobs (Stripe webhook processing, usage
aggregation, sandbox reaping, image builds) need to survive a process crash/restart, which rules
out pure in-process `asyncio` tasks; (2) the real-time event bus for streaming agent output (§9 of
docs/ARCHITECTURE.md) was originally planned as in-process `asyncio` pub/sub, deferred to Redis
only if/when the app ever runs as more than one instance.

## Decision
Introduce Redis now, for both needs, rather than introducing it later for the queue and later
still (on a separate migration) for the event bus:
- `arq` (a Redis-backed async task queue) runs the durable background jobs.
- `core/events.py` uses Redis pub/sub for the event bus from day one, instead of starting
  in-process.

## Consequences
- One new piece of infrastructure (Redis) instead of two future migrations (introduce Redis for
  the queue later, then migrate the event bus to Redis even later when multi-instance scaling is
  needed).
- The in-process-pub/sub-now, Redis-later plan that appeared in an earlier draft of
  docs/ARCHITECTURE.md was dropped — there is no "Phase X: migrate the event bus to Redis" step
  anymore, because it never left Redis in the first place.
- Redis becomes a dependency the VPS must run (`docker-compose.yml`) from Phase 0 onward, not a
  later addition.

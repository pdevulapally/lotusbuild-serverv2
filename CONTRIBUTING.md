# Contributing

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first. The rules below exist to keep the things
documented there true as the codebase grows — they're not style preferences.

## Hard rules

- **Never query Firestore outside `app/repositories/`.** If a service needs new data access,
  add/extend a repository method — don't reach for the Firestore client from a service, route, or
  worker directly.
- **Never duplicate business logic across transports.** REST (`app/api/`) and WebSocket
  (`app/ws/`) handlers must both call into `app/services/` — a handler contains no logic beyond
  parsing the request and calling a service.
- **Never hardcode a fallback/if-else chain where behavior should vary by config or plan.** LLM
  provider selection, tool selection, and entitlement checks are registries keyed by data
  (`agent/providers/registry.py`, `agent/tools/registry.py`, `domain/entitlements.py`), not
  `if provider == "x": ... elif ...`.
- **Never read `os.environ` outside `app/config.py`.** Add a field to `Settings` instead.
- **Never make an external call without going through `core/resilience.py`.** LLM providers, e2b,
  Stripe, and Firestore calls all need a timeout, retry/backoff, and a circuit breaker — wrap new
  external clients with `with_resilience(...)` rather than writing a bare SDK call.
- **Never add a mutating endpoint that matters if duplicated without idempotency.** Starting an
  agent turn, triggering a deploy, and purchasing credits all require `Idempotency-Key` support via
  `core/idempotency.py`.
- **Never guess at an ambiguous requirement.** If a task is underspecified, say so and ask rather
  than picking a default silently — see the project's own ground rules in docs/ARCHITECTURE.md.

## Adding a new LLM provider

1. Implement `agent/providers/base.py`'s `ModelProvider` interface in a new
   `agent/providers/<name>_provider.py`.
2. Register it in `agent/providers/registry.py`.
3. Add its allowed models to the relevant `plans/{planId}.allowed_models` entries (data, not code).

No other file should need to change.

## Adding a new agent tool

1. Implement `agent/tools/base.py`'s `Tool` interface in `agent/tools/<name>.py`.
2. Register it in `agent/tools/registry.py`.

## Recording a judgment call

If a change makes a non-obvious decision — something that isn't forced by the requirements alone
— add a short ADR under `docs/adr/` (see the existing ones for the format) and link it from
`docs/adr/README.md` and the relevant section of `docs/ARCHITECTURE.md`.

## PR checklist

- [ ] Business logic lives in `services/`, not in `api/`/`ws/`.
- [ ] Any new Firestore access goes through `repositories/`, tenant-scoped.
- [ ] Any new external call is wrapped via `core/resilience.py`.
- [ ] Any new mutating endpoint that matters if duplicated supports `Idempotency-Key`.
- [ ] Any non-obvious decision has an ADR.
- [ ] `ruff check .`, `mypy app`, and `pytest` all pass locally.

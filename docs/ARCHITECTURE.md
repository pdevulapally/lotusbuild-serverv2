# Lotusbuild Backend — Architecture

This is the canonical design reference for this repository. If a future change conflicts with
something documented here, update this file in the same change — this document, not tribal
knowledge, is the source of truth for why the codebase is shaped the way it is. Individual
judgment calls also have their own short write-up under `docs/adr/`.

## Context

Lotusbuild is an AI software-builder web app (Devin / v0.dev / Codex-style): a user describes
software in a chat interface and an AI agent builds it — writing code, running it, iterating live.
This repo is the backend only; the frontend is a separate, out-of-scope concern.

Hard constraints on *how* this gets built, not just *what*, set at the start of the project and
still binding on every change: no guessed/hallucinated decisions (flag and ask instead), no
duplicated business logic, no rigid if/else fallback chains (use config/data-driven registries),
security-first, and a repo structured so both human contributors and future AI coding agents can
onboard without re-deriving context or re-implementing existing logic.

Confirmed product requirements:
- **Full platform from day one**: agent build loop + team/workspace collaboration + hosted
  deployment of built apps.
- **Multi-tenant SaaS with Stripe billing from day one**, usage metering (LLM tokens, e2b compute
  minutes) tied to plan quotas.
- **Multi-model AI agent, gated by subscription tier** — a custom, provider-agnostic agent loop
  (not a single-vendor SDK), since multiple LLM providers must be interchangeable.
- **Real-time streaming** — the frontend watches the agent work live (token output, file changes,
  terminal output) via WebSocket/SSE, not polling.
- **Firebase**: Auth + Firestore as the *only* database (no separate relational DB).
- **Single FastAPI instance at launch** (no horizontal scaling requirement yet).
- **Production deploys generically containerize whatever stack the agent produces** — no fixed
  framework allowlist.
- **VPS fleet for published apps uses plain Docker + a custom lightweight scheduler**, not
  Kubernetes/Nomad, at this stage.

Two technical questions were resolved against e2b's actual docs instead of guessed:
- e2b supports native per-sandbox egress rules (`allowOut`/`denyOut`, IP/CIDR/domain, plus an
  `allowInternetAccess` switch, updatable at runtime) — so sandbox network containment uses e2b's
  own feature, no custom egress proxy needed. ([docs.e2b.dev/network/internet-access](https://docs.e2b.dev/network/internet-access))
- e2b has no native "warm pool"; it has **snapshots** (point-in-time filesystem+memory capture that
  many sandboxes can restore from) — the sandbox lifecycle design uses snapshot-based restore, not
  a literal warm pool. ([docs.e2b.dev/sandbox/snapshots](https://docs.e2b.dev/sandbox/snapshots))

A follow-up pass covered production-readiness concerns the first pass under-specified (rate
limiting, TLS/bot detection, idempotency, caching, circuit breakers/retries/timeouts, message
queues, and the real billing/overage model):
- **Edge security**: a managed edge provider (e.g. Cloudflare) sits in front of the VPS for TLS
  fingerprinting, bot detection, DDoS protection, and IP-level rate limiting — not hand-rolled.
- **Task queue**: Redis + a durable task queue (`arq`) is added from day one — it also becomes the
  real-time event bus backend (§9), consolidating two future migrations into one piece of infra.
- **Overage billing**: hard cutoff at plan quota, with **purchasable prepaid credit top-ups** (same
  model as Anthropic/OpenAI API credits) rather than continuous Stripe metered billing.

A second follow-up pass corrected the dev/test environment assumption — there is no local
emulation:
- **No Firestore emulator.** Dev/testing uses the **same real Firebase project as production** —
  acceptable for now since there are no real users yet.
- **The VPS already in hand is — or will become — the production server.** No separate
  dev/staging VPS exists. FastAPI, Redis, and the arq worker all run **on that VPS**, in
  development and production alike.
- **The coding loop runs on the VPS**, not on a local machine — code is pushed/synced to the VPS
  and run/checked there, not run locally against remote services.
- **Safety net**: daily automated Firestore backups, and any destructive script requires explicit
  interactive confirmation — never runs unattended. No deeper isolation yet.
- **Explicit upgrade trigger**: introduce a separate staging Firebase project and VPS **before**
  the first real paying customer or production launch — not before.

---

## 1. High-Level Architecture

```
                         Internet
                            │
                            ▼
              ┌─────────────────────────┐
              │ Managed edge (Cloudflare) │  TLS fingerprinting, bot/DDoS detection,
              │ or equivalent              │  IP-level rate limiting, static caching
              └────────────┬─────────────┘
                            │ HTTPS (REST) + WSS (streaming)
                            ▼
              ┌─────────────────────────┐
              │ Reverse proxy (Traefik/   │  TLS termination to origin, routes by
              │ Caddy) on the VPS          │  hostname: api.* → FastAPI, *.apps.* → containers
              └────────────┬─────────────┘
                            ▼
Frontend (out of scope)
   │
   ▼
FastAPI server (single instance, VPS)
 ├─ api/   (REST routers)  ─┐
 ├─ ws/    (WS handlers)   ─┼─► services/ (ALL business logic lives here)
 └─ core/security (auth+RBAC, single enforcement point)
                              │
         ┌────────────────────┼─────────────────────┐
         ▼                    ▼                      ▼
  repositories/         agent/ (provider-agnostic   sandbox/ (e2b client +
  (ONLY Firestore        loop, provider registry,    lifecycle: snapshot,
  access point)           tool registry)              suspend, restore)
         │                    │                      │
         ▼                    ▼                      ▼
    Firestore          Anthropic/OpenAI/...     e2b sandboxes
    (system of         (wrapped by                    │ on "Deploy"
     record)            core/resilience.py:             ▼
                         retry+backoff,         deploy/ (image build →
                         circuit breaker,        VPS Docker fleet →
                         timeout)                proxy_registrar)

billing/ (Stripe client + plans + credits) ◄── services/usage_service.py ──► repositories/usage_repo.py
core/idempotency.py: Idempotency-Key / Stripe event-id dedupe for every mutating endpoint & webhook
Redis: (a) arq durable task queue — webhook processing, usage aggregation, image builds
       (b) pub/sub backend for core/events.py — agent/sandbox publish, ws/ subscribes
```

Key decisions baked in:
- FastAPI is the **only** process that talks to Firestore/Stripe/e2b/VPS fabric directly — the
  frontend never touches Firestore directly, so tenant-scoping stays server-side and auditable
  (not relying on Firestore security rules as the isolation boundary).
- Firebase Auth is **identity-only**; FastAPI resolves authorization (role, plan) from Firestore on
  each request via a short-TTL in-process cache — avoids custom-claims propagation staleness
  (a demoted admin keeps old claims until next token refresh).
- The control-plane FastAPI server and the VPS fleet hosting *published user apps* are separate
  deployable units/failure domains from day one — arbitrary user containers never share a failure
  domain with the control plane.
- Every external network call (LLM providers, e2b, Stripe, Firestore) goes through
  `core/resilience.py` — never a bare SDK call with no timeout/retry/circuit-breaker.
- Every mutating endpoint and the Stripe webhook handler goes through `core/idempotency.py` —
  retries and duplicate webhook deliveries never double-process.

## 2. Directory Structure

Principle: **transport code (`api/`, `ws/`) is thin; business logic lives in `services/`; Firestore
access lives only in `repositories/`.** This is the mechanical anti-duplication device — e.g. REST
and WebSocket handlers for agent sessions both call `services/agent_service.py`; neither
re-implements orchestration.

```
lotusbuildbackendv2/
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml
├── .env.example
├── Dockerfile
├── docker-compose.yml           # runs ON THE VPS: FastAPI, Redis, arq worker —
│                                   the dev AND prod stack, no separate local/emulated setup
├── docs/
│   ├── ARCHITECTURE.md          # this file
│   └── adr/                     # one record per judgment call
├── app/
│   ├── main.py                  # app factory, router registration, lifespan
│   ├── config.py                # pydantic Settings — the ONLY env/secret read point
│   ├── api/
│   │   ├── deps.py              # shared Depends: get_tenant_context, require_role, idempotency_key, etc.
│   │   └── v1/                  # orgs.py, projects.py, agent_sessions.py, deployments.py,
│   │                               billing.py, webhooks.py (Stripe, signature-verified)
│   ├── ws/
│   │   ├── connection_manager.py # per-session connection registry, same auth deps as REST
│   │   └── agent_stream.py       # thin subscriber over core/events.py, zero business logic
│   ├── core/
│   │   ├── security/
│   │   │   ├── firebase_token.py # verify_id_token — single implementation
│   │   │   ├── tenant_context.py # builds TenantContext from verified token + membership lookup
│   │   │   └── rbac.py           # require_role()/require_permission() — THE enforcement point
│   │   ├── errors.py             # domain exceptions → HTTP/WS error mapping
│   │   ├── events.py             # Redis-backed pub/sub (per session/project topic)
│   │   ├── resilience.py         # tenacity retry/backoff + pybreaker circuit breaker + timeout
│   │   │                           wrappers, applied uniformly to every external client
│   │   ├── idempotency.py        # Idempotency-Key handling + Stripe event-id dedupe, one impl
│   │   └── redis_client.py       # single Redis connection factory (queue + pub/sub + caches use it)
│   ├── domain/
│   │   ├── models/               # pydantic domain models
│   │   ├── entitlements.py       # plan+credits → capability resolution (data-driven, not if/else)
│   │   └── rbac_policy.py        # role → permission matrix (data, not hardcoded per route)
│   ├── repositories/              # base.py = generic tenant-scoped CRUD; one file per entity
│   │   └── idempotency_repo.py     # stores processed idempotency keys/results with TTL
│   ├── services/                  # business logic, called by both api/ and ws/
│   │   ├── auth_service.py, org_service.py, project_service.py, agent_service.py,
│   │   ├── sandbox_service.py, deployment_service.py, billing_service.py,
│   │   └── usage_service.py, audit_service.py   # single entry points for metering/audit writes
│   ├── agent/                      # the custom provider-agnostic orchestration core
│   │   ├── loop.py                 # plan → call model → execute tool → repeat
│   │   ├── providers/               # base.py (ModelProvider interface) + one adapter per provider
│   │   │   └── registry.py          # provider_id → adapter, config-driven (no if/elif chain)
│   │   ├── tools/                   # base.py (Tool interface) + file_ops.py, shell_exec.py
│   │   │   └── registry.py          # tool_name → implementation
│   │   └── entitlement_gate.py      # checks domain/entitlements.py before any model call
│   ├── sandbox/
│   │   ├── e2b_client.py            # thin e2b SDK wrapper, calls wrapped via core/resilience.py
│   │   └── lifecycle.py             # snapshot/suspend/restore policy (see §6)
│   ├── deploy/
│   │   ├── image_builder.py          # sandbox snapshot → Docker image (see §7), runs as an arq job
│   │   ├── container_runtime.py       # talks to Docker on VPS fleet nodes
│   │   └── proxy_registrar.py         # registers subdomain with reverse proxy
│   ├── billing/
│   │   ├── stripe_client.py          # calls wrapped via core/resilience.py
│   │   ├── plans.py                   # plan catalog as data, not code
│   │   └── credits_service.py         # prepaid credit top-up ledger (see §8)
│   └── workers/                        # arq task definitions, run by a separate arq worker process
│       ├── worker_settings.py           # arq WorkerSettings — registers the functions below
│       ├── sandbox_reaper.py            # suspends/tears down idle sandboxes
│       ├── usage_aggregator.py           # rolls usage_records into billing-period totals
│       ├── stripe_webhook_processor.py    # async-processes verified webhook events, idempotent
│       └── image_build_job.py             # the actual Docker image build, run off-request
└── tests/
    ├── unit/
    └── integration/
```

## 3. Core Domain Model → Firestore

Multi-tenant scoping is enforced in **one place**: `repositories/base.py` requires a
`TenantContext` on every call and bakes `.where("org_id", "==", tenant.org_id)` into the generic
query helper, so no individual repo file can omit the filter. `TenantContext` is only constructible
from a verified Firebase token + a live Firestore membership lookup — never from a client-supplied
`org_id`.

Top-level collections (not subcollections per org) with a mandatory `org_id` field + composite
index — chosen over `/orgs/{orgId}/...` subcollections because cross-org admin/ops queries and
usage aggregation need collection-group queries, and enforcement already lives in the
repository/service layer rather than Firestore security rules, so the subcollection isolation
benefit doesn't apply here. (See `docs/adr/0002`.)

| Entity | Collection | Key fields |
|---|---|---|
| User | `users/{uid}` | uid (Firebase UID), email, display_name |
| Organization (tenant) | `organizations/{orgId}` | name, owner_uid, plan_id, stripe_customer_id |
| Membership | `memberships/{id}` | org_id, uid, role, **project_id (nullable)**, status |
| Project | `projects/{id}` | org_id, name, created_by, repo_state_ref, current_deployment_id |
| AgentSession | `agent_sessions/{id}` | org_id, project_id, status, model_provider, model_id |
| SessionTurn | `agent_sessions/{id}/turns/{id}` | role, content_ref, tool_calls, token_usage |
| SandboxInstance | `sandbox_instances/{id}` | org_id, project_id, e2b_sandbox_id, state, last_active_at |
| Deployment | `deployments/{id}` | org_id, project_id, type (preview/production), image_tag, subdomain, status |
| Subscription | `subscriptions/{orgId}` | plan_id, stripe_subscription_id, status, current_period_end, **credits_balance** |
| Plan (catalog) | `plans/{planId}` | allowed_providers[], allowed_models[], quota_tokens, quota_e2b_minutes |
| CreditPurchase | `credit_purchases/{id}` | org_id, stripe_checkout_session_id, credit_type, quantity, purchased_at (append-only) |
| UsageRecord | `usage_records/{id}` | org_id, project_id, type, quantity, source (quota\|credit), recorded_at (append-only) |
| AuditLogEntry | `audit_log/{id}` | org_id, actor_uid, action, resource, metadata, at (append-only, no update/delete methods exist) |
| IdempotencyKey | `idempotency_keys/{key}` | org_id, endpoint, request_hash, response_snapshot, created_at (TTL-expired) |

**Membership scope**: org-wide roles + optional per-project override (`project_id` nullable on
`memberships`) — see `docs/adr/0007`.

## 4. AuthN / AuthZ

1. Frontend authenticates via Firebase Auth client SDK (out of scope), gets an ID token.
2. `core/security/firebase_token.py::verify_id_token` (Admin SDK) → `(uid, email)`.
3. `core/security/tenant_context.py::get_tenant_context(uid, requested_org_id)` — `requested_org_id`
   is only a hint; looks up the real membership/role via `memberships_repo`, 403s if none exists.
   Short-TTL in-process cache keyed by `(uid, org_id)` to bound the per-request Firestore read cost.
4. `core/security/rbac.py::require_role(min_role)` — a dependency factory checked against the
   data-driven `domain/rbac_policy.py` matrix. **Single central enforcement point**, used
   declaratively on routes, never reimplemented per route.
5. WebSocket handlers run the identical two functions at `on_connect` (not reimplemented) — see
   `ws/connection_manager.py`.

## 5. Agent Orchestration Layer

- `agent/providers/base.py`: `ModelProvider` interface — `stream_completion(messages, tools,
  model_id) -> AsyncIterator[ProviderEvent]`, `count_tokens`, `supported_models`. One adapter per
  provider; adding a provider = one new file + one registry entry, zero changes elsewhere. Every
  provider call is wrapped by `core/resilience.py` (timeout + retry/backoff + circuit breaker) —
  a provider outage degrades to fast failures, not hanging requests.
- `agent/entitlement_gate.py`: called once, from `agent_service.py`, before any model call — checks
  `TenantContext.plan_id` against `plans/{planId}.allowed_models`, and checks remaining
  quota/credits via `usage_service` (see §8). Single gating point for both REST and WS paths,
  because both call the same service method.
- `agent/tools/base.py` + `registry.py`: tool name → implementation, dispatched by `agent/loop.py`
  from normalized tool-call events regardless of which provider emitted them — file ops and shell
  exec against the sandbox are written exactly once.
- Starting an agent turn is an idempotent operation keyed by a client-supplied `Idempotency-Key`
  (double-submit from a flaky connection must not start two sandboxes/charge usage twice) — see §11.
- Token-by-token output is published to `core/events.py`, not written directly to a socket (see §9).

## 6. Sandbox Lifecycle

**Hybrid: ephemeral-per-session + snapshot-based restore**, not persistent-per-project, not a
literal warm pool (e2b doesn't offer one natively — see `docs/adr/0003`).

- A sandbox provisions when an agent session becomes active; `sandbox/lifecycle.py` +
  `workers/sandbox_reaper.py` (an arq scheduled job) suspend/snapshot it after a config-driven idle
  window.
- Before suspension, the sandbox state is captured via **e2b snapshot** (filesystem + memory) and
  referenced from `projects/{id}.repo_state_ref` — the sandbox is a disposable compute surface;
  the snapshot is the durable source of truth for project file state.
- On next activity, a sandbox restores from that snapshot rather than a cold rebuild.
- All e2b API calls go through `sandbox/e2b_client.py`, wrapped by `core/resilience.py`.
- This directly feeds §7: "preview" is just the currently-live sandbox; "production" is a
  separately promoted container, so the sandbox never needs to live forever because something
  got deployed.

## 7. Deployment Pipeline (Preview vs. Production)

- **Preview** = the live e2b sandbox, reachable while the agent is actively building. No separate
  infra — inherent to §6.
- **Production**, triggered by an explicit "Deploy" action (`services/deployment_service.py`),
  runs as an **async arq job** (`workers/image_build_job.py`), not inline in the request/response
  cycle — image builds can take long enough that they must not hold an HTTP request open, and must
  survive a worker restart mid-build:
  1. `deploy/image_builder.py` snapshots current sandbox state and builds a Docker image. Since
     deploys support **fully generic stacks** (no fixed framework list), the build step is: the
     agent's own tool-output includes a Dockerfile as a standard build artifact, with **Cloud
     Native Buildpacks** (Paketo) as a fallback when no Dockerfile is present. See `docs/adr/0005`.
  2. Image pushed to a registry; `deploy/container_runtime.py` schedules it onto a VPS fleet node
     via a simple custom scheduler (plain Docker — no Kubernetes/Nomad at this stage).
  3. `deploy/proxy_registrar.py` registers a subdomain with the Traefik/Caddy reverse proxy
     (dynamic, label/API-driven — no manual config edits per deploy).
  4. `deployments/{id}` tracks status; redeploy rebuilds from current snapshot, rollback repoints
     the proxy to a prior image tag without rebuilding. Retention of old images is plan-tier-driven
     data (`plans` collection), not hardcoded.
- The "Deploy" API call itself is idempotent on `Idempotency-Key` — retrying a timed-out deploy
  request returns the existing job's status rather than starting a second build.

## 8. Billing & Usage Metering

**Model: hard quota cutoff + purchasable prepaid credit top-ups** (same shape as Anthropic/OpenAI
API credits), not continuous Stripe metered/usage-based billing. See `docs/adr/0008`.

- `billing/stripe_client.py` wraps Checkout/Billing Portal sessions (subscription plan changes)
  **and** one-time Checkout sessions for credit-pack purchases — card data never touches our
  server (PCI scope avoidance). All calls wrapped by `core/resilience.py`.
- `api/v1/webhooks.py` verifies Stripe signatures, then **enqueues** the event onto the arq queue
  (`workers/stripe_webhook_processor.py`) instead of processing inline — Stripe's own retry
  behavior plus our idempotency layer (deduping by Stripe event ID, see §11) means a slow or
  duplicate webhook delivery can never double-apply a credit or double-activate a plan change.
  `services/billing_service.py` is the only writer of `subscriptions/{orgId}`.
- `billing/credits_service.py` is the only writer of `subscriptions/{orgId}.credits_balance`:
  incremented when a `CreditPurchase` webhook confirms payment, decremented by `usage_service` once
  the plan's base quota is exhausted for the period.
- **Single metering entry point**: `services/usage_service.py::record_usage(tenant, type, quantity,
  metadata)` — called by the agent loop (after each provider call, for tokens) and by sandbox
  lifecycle (on suspend/teardown, for compute minutes). Internally it checks
  `plans/{planId}.quota_*` first; once exhausted it draws down `credits_balance`; once both are
  exhausted it raises a domain error that `entitlement_gate.py` turns into a 402-style rejection
  with a "purchase more credits" signal — hard cutoff, never silent overage.
- `workers/usage_aggregator.py` (arq scheduled job) rolls `usage_records` into per-period totals
  for reporting/invoicing visibility; the real-time gating decision happens synchronously in
  `usage_service` on the hot path, not in the aggregator.
- Plan quotas/capabilities and credit-pack prices are Firestore data (`plans` collection) —
  changing a quota or adding a credit-pack SKU is a data edit, not a deploy.

## 9. Real-Time Streaming

- `core/events.py`: **Redis-backed pub/sub**, per session/project topic — using Redis from day one
  rather than starting in-process and migrating later, since Redis is already required for the
  task queue (§12). See `docs/adr/0006`.
- `agent/loop.py` and `sandbox/lifecycle.py` publish events tagged by `session_id`/`project_id`;
  they don't know or care whether anything is subscribed.
- `ws/agent_stream.py` subscribes after the same auth/tenant/RBAC checks as REST and forwards
  events — it contains no business logic, so there's nothing to duplicate.
- REST still serves session history (via `sessions_repo`) for non-WS clients; the live experience
  is push-based.

## 10. Edge, Reverse Proxy & Resilience

- **Edge layer**: a managed provider (Cloudflare or equivalent) sits in front of the VPS and owns
  TLS fingerprinting/bot detection, DDoS mitigation, and IP-level rate limiting. See
  `docs/adr/0009`.
- **Reverse proxy**: Traefik or Caddy runs on the VPS behind the edge layer, terminates TLS to the
  origin, and routes by hostname — `api.*` to the FastAPI control plane, `*.apps.*` to the deployed
  container fleet (§7).
- **Resilience (`core/resilience.py`)**: every external client (LLM provider adapters, `e2b_client`,
  `stripe_client`, the Firestore client) is wrapped once, here, with:
  - **Timeouts** — explicit, configured via `config.py` settings per external system, never a bare
    SDK default.
  - **Retry + exponential backoff** — via `tenacity`, applied to transient failures.
  - **Circuit breaker** — via `pybreaker`, so a degraded provider fails fast instead of piling up
    hanging requests once it's clearly down.
  - This is one implementation reused by every client module, not reimplemented per integration.
- **Rate limiting split**: IP/bot-level abuse protection lives at the edge (Cloudflare); billing
  quota enforcement is the entitlement gate (§5/§8) — deliberately not merged into one mechanism.
  Per-tenant *throughput* limiting beyond what quotas already bound is not built now (YAGNI).
- **Caching**: the short-TTL in-process cache already used for `TenantContext`/membership lookups
  (§4) is the general pattern for hot, rarely-changing reads. No separate caching layer beyond
  this and Redis (§12).

## 11. Idempotency

- `core/idempotency.py` + `repositories/idempotency_repo.py`: every mutating endpoint that matters
  if duplicated (starting an agent turn, triggering a deploy, purchasing credits) accepts an
  `Idempotency-Key` header. On first use, the key + a hash of the request + the eventual response
  are stored in `idempotency_keys` (TTL-expired); a repeated request with the same key
  short-circuits to the stored response. One implementation, used as a FastAPI dependency.
- **Stripe webhooks** are deduped by Stripe's own event ID through the same mechanism before being
  enqueued to the arq worker (§8/§12).
- This directly protects the billing/credits model (§8) and the deploy pipeline (§7) from
  double-charging or double-building on retry.

## 12. Task Queue (Redis + arq)

- Redis is introduced from day one because in-process-only background tasks lose in-flight work on
  a crash/restart, which is not acceptable for billing-adjacent and build operations. The same
  Redis instance is reused for the event bus (§9).
- `arq` runs these as durable, retryable jobs instead of in-process `asyncio` tasks:
  - `workers/stripe_webhook_processor.py` — processes verified webhook events asynchronously.
  - `workers/usage_aggregator.py` — periodic rollup of usage records.
  - `workers/sandbox_reaper.py` — periodic idle-sandbox snapshot/suspend sweep.
  - `workers/image_build_job.py` — Docker image builds for production deploys.
- The arq worker runs as a separate process from the FastAPI server (same VPS at this scale).

## 13. Security

- **Tenant isolation**: enforced exclusively via `TenantContext` + `repositories/base.py` — the
  single point of failure for isolation, and the file with the heaviest test coverage in the repo.
- **Sandbox containment**: e2b's own sandbox isolation is the primary boundary; on top, e2b's
  **native** `denyOut`/`allowOut` egress rules deny private/internal IP ranges and block SSRF to
  internal infra/metadata endpoints. Resource/time caps via e2b sandbox templates.
- **Edge/network security**: TLS fingerprinting, bot detection, and DDoS/rate-limit protection are
  handled by the managed edge layer (§10) — not application code.
- **Resilience as a security property**: timeouts and circuit breakers (§10) bound the blast radius
  of a slow/compromised external dependency.
- **Idempotency as a correctness/security property**: prevents duplicate-charge and
  duplicate-resource-creation abuse via retried or replayed requests (§11).
- **Secrets**: all provider/Stripe/e2b/Firebase/Redis credentials read through `config.py` only.
- **Audit logging**: `services/audit_service.py::record(...)` is the single write path to
  `audit_log`; no update/delete repo methods exist for it at all.
- **Compliance posture**: centralized tenant scoping + centralized audit log + no raw card data +
  isolated secrets + explicit RBAC matrix + edge-layer bot/DDoS protection means a future SOC2
  effort mainly needs process controls rather than a data-flow re-architecture.

## 14. Documentation & Contributor-Friendliness

- `README.md`: architecture summary + VPS setup instructions + a pointer to this document.
- `CONTRIBUTING.md`: conventions (never query Firestore outside `repositories/`, how to add a
  provider/tool, how to add an idempotent endpoint), PR checklist.
- `docs/adr/`: one file per judgment call — see the index there.
- Naming convention is the discoverability mechanism: `*_service.py` = business logic, `*_repo.py`
  = Firestore access, `*_provider.py` = LLM adapter. Docstrings only at package `__init__.py`
  boundaries, skipped elsewhere per the no-boilerplate rule.

## 15. Phased Build Plan

| Phase | Creates | Deliverable |
|---|---|---|
| 0 — Scaffolding | `main.py`, `config.py`, `pyproject.toml`, `docker-compose.yml`, `core/errors.py`, `core/resilience.py`, `core/redis_client.py`, CI, daily Firestore backup schedule | App runs on the VPS against the real Firebase project; lint/unit tests run in CI |
| 1 — Auth & Tenancy | `security/*`, `rbac_policy.py`, `repositories/base.py`, users/orgs/memberships repos, `auth_service.py`, `org_service.py`, `api/v1/orgs.py` | User signs in, creates/joins an org, every route enforces tenant+role |
| 2 — Core Data Layer | `domain/models/*`, remaining repos, `project_service.py`, `audit_service.py`, `core/idempotency.py` + `idempotency_repo.py` | Projects CRUD, scoped; audit trail exists; idempotency available |
| 3 — Agent Core | `agent/providers/*`, `agent/tools/*` (mocked sandbox), `agent/loop.py`, `entitlement_gate.py`, `agent_service.py`, `api/v1/agent_sessions.py` (idempotent) | Scripted agent turn runs end-to-end, gated by plan, safe under retry |
| 4 — Sandbox Integration | `sandbox/e2b_client.py`, `sandbox/lifecycle.py`, `sandbox_service.py`, `workers/sandbox_reaper.py`; wire real tools | Agent executes real code in a real e2b sandbox, reaper runs as a durable job |
| 5 — Real-Time Streaming | `core/events.py` (Redis pub/sub), `ws/*` | Live streaming over Redis, reusing earlier services untouched |
| 6 — Billing & Metering | `billing/*`, `usage_service.py`, `workers/usage_aggregator.py`, `workers/stripe_webhook_processor.py`, `api/v1/billing.py`, `api/v1/webhooks.py` | Plans enforced live, hard-cutoff + credit top-ups working, webhooks idempotent |
| 7 — Deployment Pipeline | `deploy/*`, `workers/image_build_job.py`, `deployment_service.py`, `api/v1/deployments.py` | Preview→production promotion, generic containerization, durable async builds |
| 8 — Edge, Hardening & Docs | Cloudflare setup, Traefik/Caddy config, e2b egress tuning, remaining ADRs, cross-tenant-leak test suite | Edge security live, security posture finalized, repo fully documented |

## Verification

- Phase 0: `uvicorn app.main:app` runs on the VPS against the real Firebase project and the VPS's
  own Redis; CI runs lint + unit tests (mocked dependencies, Redis via a CI service container —
  no live Firestore) on push.
- Phase 1: integration test, run on the VPS — mismatched `org_id` header rejected (403),
  role-gated routes reject under-privileged roles. Use a dedicated test org — never a real
  customer's.
- Phase 2: a repeated request with the same `Idempotency-Key` returns the original response
  without re-executing the operation.
- Phase 3/4/6: a forced provider/e2b/Stripe failure (mocked) trips the circuit breaker after the
  configured threshold; retry/backoff is observed in test, not just asserted.
- Phase 6: usage past plan quota draws from `credits_balance`; usage past both is rejected.
- Ongoing: every `repositories/*.py` method gets a cross-tenant-leak test (two orgs, assert org A
  can never read org B's documents).

## Critical Files

- `app/repositories/base.py` — tenant-scoping enforcement point.
- `app/core/security/tenant_context.py` — single source of truth for who-is-allowed-what.
- `app/core/resilience.py` — the only place timeouts/retry/circuit-breaking are implemented.
- `app/core/idempotency.py` — the only place duplicate-request/webhook protection is implemented.
- `app/agent/loop.py` — the custom provider-agnostic orchestration core.
- `app/services/agent_service.py` — shared service both REST and WS call.
- `app/sandbox/lifecycle.py` — the hybrid sandbox lifecycle.
- `app/services/usage_service.py` — the hard-cutoff + prepaid-credits billing model.
- `app/deploy/image_builder.py` — the generic-containerization approach.

# Architecture Decision Records

Each file here records one non-obvious judgment call: the context that forced a decision, what was
decided, and what it costs. Add a new one whenever a change makes a call that isn't forced by the
requirements alone — future contributors (human or agent) should be able to tell *why* something
is shaped the way it is without re-deriving it or asking.

| ADR | Title |
|---|---|
| [0001](0001-firestore-as-only-database.md) | Firestore as the only database |
| [0002](0002-top-level-collections-vs-subcollections.md) | Top-level collections over per-org subcollections |
| [0003](0003-sandbox-hybrid-lifecycle.md) | Hybrid ephemeral/snapshot sandbox lifecycle |
| [0004](0004-preview-production-deploy-split.md) | Preview vs. production deploy split |
| [0005](0005-generic-containerization.md) | Generic containerization via agent-emitted Dockerfile |
| [0006](0006-redis-from-day-one.md) | Redis for both the task queue and the event bus, from day one |
| [0007](0007-membership-scope.md) | Org-wide + per-project membership scope |
| [0008](0008-hard-cutoff-prepaid-credits.md) | Hard cutoff + prepaid credit top-ups for billing |
| [0009](0009-managed-edge-provider.md) | Managed edge provider for TLS/bot/DDoS protection |
| [0010](0010-shared-dev-prod-environment.md) | Shared Firebase project and VPS for dev and production |

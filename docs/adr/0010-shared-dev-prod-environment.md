# 0010: Shared Firebase project and VPS for dev and production

## Status
Accepted for now — explicit trigger to revisit below

## Context
A typical setup isolates development/testing from production: a separate Firebase project, a
separate server. This project does not have that: there is one Firebase project and one VPS,
used for both development and (eventually) production, and the coding loop runs on that VPS
directly rather than on a local machine with emulated services.

This was a deliberate choice, confirmed directly, not a gap the planning process missed:
there are no real users yet, so the isolation risk this setup normally guards against is
currently near zero.

## Decision
- No Firestore emulator; dev/testing uses the real, shared Firebase project.
- No separate dev/staging VPS; the one VPS in hand is or will become the production server.
- Two cheap mitigations apply regardless of the lack of isolation:
  - Daily automated Firestore backups (managed export).
  - Any destructive script (bulk delete, data reset) requires an explicit interactive
    confirmation and never runs unattended.

## Consequences
- A bug in a migration, seed script, or test run has no isolation layer between it and real data
  once real data exists — mitigated only by the backup + confirmation-gate rules above, not by
  structural separation.
- **Explicit upgrade trigger, so this is not silently forgotten**: introduce a separate staging
  Firebase project and a separate staging VPS *before* the first real paying customer or
  production launch. This ADR should be marked superseded once that happens.

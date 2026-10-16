# 0001: Firestore as the only database

## Status
Accepted

## Context
The product needs a backing store for users, orgs, projects, agent sessions, usage, and billing
records. A common pattern would pair Firestore (for auth-adjacent and real-time-ish data) with a
relational database (for billing/usage, where transactional integrity matters most).

## Decision
Firestore is the *only* database. No separate relational database is introduced.

This was a direct product requirement, not a judgment call — but it has a real consequence
documented here so it isn't rediscovered the hard way: Firestore has no multi-document ACID joins
across collections the way a relational database does. Anywhere that would normally reach for a
SQL transaction (e.g. decrementing `credits_balance` while writing a `usage_record`), the code must
use Firestore's own transaction API explicitly, and the resulting write pattern should be kept to a
single, shared implementation (`services/usage_service.py`) rather than re-derived per call site.

## Consequences
- No relational DB to operate, back up, or migrate — one less moving part.
- Firestore transactions must be reached for deliberately wherever multiple documents need to
  change together; this is not automatic the way it would be in a relational engine.
- Collection-group queries and composite indexes do the work a SQL `JOIN`/`WHERE` would — see
  ADR 0002 for how this shapes the schema.

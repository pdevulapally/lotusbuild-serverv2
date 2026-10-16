# 0002: Top-level collections over per-org subcollections

## Status
Accepted

## Context
Firestore supports two natural shapes for multi-tenant data: nesting everything under
`/organizations/{orgId}/projects/{projectId}/...` (subcollections), or flat top-level collections
(`projects/{id}`) carrying an `org_id` field. Subcollections give Firestore-native isolation —
a query scoped to a subcollection physically cannot see another org's documents. Top-level
collections need every query to explicitly filter by `org_id`.

## Decision
Use top-level collections with a mandatory `org_id` field and a composite index, not subcollections.

Two reasons:
1. Cross-org admin/ops queries and usage aggregation (`workers/usage_aggregator.py`) need
   collection-group-style queries across all orgs, which are far more natural over flat top-level
   collections than nested subcollections.
2. Tenant isolation is already enforced centrally in `repositories/base.py` (every query goes
   through a helper that injects the `org_id` filter), not left to Firestore's structural
   boundaries or security rules. Since the isolation guarantee doesn't come from the schema shape
   anyway, the subcollection's main benefit doesn't apply here.

## Consequences
- `repositories/base.py` is the single point of failure for tenant isolation — it needs the
  heaviest test coverage in the repo (a cross-tenant-leak test per repository method).
- Composite indexes (`org_id` + whatever else a query filters/sorts on) must be declared for every
  query shape the app uses — Firestore will refuse un-indexed composite queries at request time,
  not silently scan.

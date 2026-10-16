# 0007: Org-wide + per-project membership scope

## Status
Accepted — flagged for the product owner to revisit if it doesn't match intent

## Context
The product requires "team/workspace collaboration" (multi-user projects with roles), but it was
left open whether a membership/role is always org-wide, or can also be scoped to a single project
(e.g. an external collaborator added to one project only, without full org access). The person
setting requirements was not sure and asked for a recommendation rather than specifying one.

## Decision
Support both: `memberships/{id}` carries an org-wide role plus an optional, nullable `project_id`.
When `project_id` is null, the membership is org-wide; when set, it scopes that membership to one
project.

Reasoning: the confirmed "team/workspace collaboration" requirement already implies project-level
collaboration is a realistic need (an external collaborator scoped to one project is a common
real-world case for this kind of product), and the schema cost of supporting it now — one nullable
field — is negligible compared to retrofitting it onto `memberships` after data already exists.

## Consequences
- `core/security/rbac.py` and `tenant_context.py` need to resolve "does this membership apply to
  this request" by checking both the org-wide and project-scoped memberships for a user, not just
  one lookup.
- Because this was a judgment call rather than a stated requirement, it should be revisited with
  the product owner once real usage patterns exist — if project-scoped membership never gets used,
  it can be simplified away; if it turns out to need more structure (e.g. project-scoped
  permissions beyond role), that's a bigger schema change best made early rather than late.

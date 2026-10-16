# 0008: Hard cutoff + prepaid credit top-ups for billing

## Status
Accepted

## Context
When a tenant exceeds their plan's usage quota (LLM tokens, e2b compute minutes), something has to
happen. Two shapes were considered: continuous Stripe metered/usage-based billing (usage keeps
flowing, an overage line item is billed automatically), or a hard cutoff with the option to buy
more.

## Decision
Hard cutoff by default; the tenant can purchase prepaid credit top-ups (one-time Stripe Checkout
purchases, like Anthropic/OpenAI API credits) to keep going past the base plan quota. Not
continuous metered billing.

## Consequences
- `subscriptions/{orgId}.credits_balance` is a prepaid ledger: incremented by confirmed
  `CreditPurchase` webhooks, decremented by `usage_service` once the base plan quota is exhausted.
- Billing integration stays simpler: one-time Checkout sessions, not Stripe's usage-based/metered
  billing API, no end-of-period true-up invoicing to reconcile.
- `services/usage_service.py::record_usage` is the single place quota-then-credits math happens —
  it must never be reimplemented per caller (the agent loop and sandbox lifecycle both call it).
- There is no soft overage: once quota and credits are both exhausted, usage stops (a 402-style
  rejection with a "purchase more credits" signal) rather than continuing and billing later.

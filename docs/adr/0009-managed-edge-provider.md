# 0009: Managed edge provider for TLS/bot/DDoS protection

## Status
Accepted

## Context
The backend needs protection against bots and abusive traffic, including TLS-fingerprint-level
detection (JA3/JA4) to distinguish real browsers from scripted clients, plus DDoS mitigation and
IP-level rate limiting. Building this in-house on the VPS was considered and rejected.

## Decision
A managed edge provider (Cloudflare, or an equivalent) sits in front of the VPS and owns TLS
fingerprinting, bot scoring, DDoS mitigation, and IP-level rate limiting. The VPS's own reverse
proxy (Traefik/Caddy) handles TLS termination to the origin and hostname-based routing behind it,
but does not attempt bot/fingerprint detection itself.

Reasoning: replicating JA3/JA4 fingerprinting and bot-scoring well is a losing effort compared to
a provider whose entire business is keeping that detection current against an evolving adversary.

## Consequences
- An external dependency (and its cost/configuration) is added to the production stack — this is
  infrastructure, not application code, and is not something `core/resilience.py` wraps or retries
  around; it's a different layer entirely.
- Billing/quota enforcement (ADR 0008) and edge-level rate limiting are two separate mechanisms by
  design, not merged — the edge handles abuse/bot traffic, the entitlement gate handles paid usage
  limits.
- This decision does not block self-hosting later if requirements change; it is captured here so
  the reasoning isn't lost if someone later asks "why Cloudflare."

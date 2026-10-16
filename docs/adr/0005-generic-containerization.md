# 0005: Generic containerization via agent-emitted Dockerfile

## Status
Accepted

## Context
Production deploys (ADR 0004) must support whatever stack the agent built — there is no fixed,
officially-supported framework list. The image builder (`deploy/image_builder.py`) therefore needs
some way to turn arbitrary agent output into a runnable container. Two options: build a
stack-detection heuristic ourselves (inspect files, guess the framework, pick a build strategy), or
let something else decide.

## Decision
The agent's own tool-output includes a Dockerfile as a standard build artifact — the agent already
wrote the code and already knows what stack it chose, so it is the natural place for that decision
to live, not a second heuristic layer guessing at it after the fact. **Cloud Native Buildpacks**
(Paketo) is the fallback when no Dockerfile is present, rather than a hand-rolled detector.

## Consequences
- No separate "what stack is this" detection logic exists anywhere in the backend — avoiding the
  exact kind of duplicated logic the project's engineering rules forbid.
- The agent's tool/prompt design (Phase 3+) must treat "produce a Dockerfile" as a standard part of
  finishing a build, not an optional nicety — this is a dependency from `deploy/` back onto
  `agent/`, worth keeping in mind when the agent's system prompt/tools are written.
- Buildpacks add one more moving part (the Paketo builder image/toolchain) but it is a fallback
  path, not the primary one.

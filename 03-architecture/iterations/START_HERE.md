# Start here — Sycamore model handoff

Current task: **Iteration 1.1.1 — Baseline the system**.
Planning revision: 2. No implementation gate has passed merely because these
documents exist. See REGISTER.md for current state if it changes later.

Read in this order:

1. [Roadmap](../../01-strategy/INTELLIGENCE_PLATFORM_ROADMAP.md)
2. [Implementation specification](../INTELLIGENCE_IMPLEMENTATION_SPEC.md)
   and [exact Part 1 wire shapes](../INTELLIGENCE_WIRE_SHAPES.md)
3. [Execution protocol](README.md)
4. [Task register](REGISTER.md)
5. [Baseline brief](1.1.1-baseline.md)
6. [Commercial validation](../../01-strategy/MONETIZATION_PLAN.md)

Copyable prompt for the implementing model:

> Work in /home/yams/operations/project-sycamore. Read
> 03-architecture/iterations/START_HERE.md and its linked instructions.
> Execute only iteration 1.1.1-baseline.md. Preserve existing changes and the
> working application. Use fixtures/temp directories for ingestion measurements.
> Do not fetch live feeds, change a service, alter public schemas, install a
> database or deploy. Collect real evidence; label missing/blocked checks.
> Update the brief and REGISTER.md with exact results and the next task. Do not
> mark complete unless every acceptance gate passes. If interrupted, save an
> exact resume checkpoint. Do not implement the whole roadmap in one pass.

The next two briefs are prewritten for continuity, but remain dependency-blocked:

- [1.1.2 — Contracts](1.1.2-contracts.md)
- [1.2.1 — Archive shadow](1.2.1-archive-shadow.md)

Later task cards are in REGISTER.md. Expand each into a detailed brief before
coding; do not invent decisions it explicitly leaves pending.

# Agent Network

Durable project conversations among existing Hermes specialists.

## Language
**Specialist**: An existing Hermes Profile enrolled for network execution, retaining its own identity and capabilities.
_Avoid_: AG2 model agent, temporary subagent

**Project channel**: A persistent two-specialist discussion within one project.
_Avoid_: one-shot consultation, global shared chat

**Channel session**: The Hermes conversation owned by one specialist for one project channel, including its continuation lineage.
_Avoid_: session per message

**Network operation**: One explicitly identified communication request whose delivery and execution are tracked independently of retries.
_Avoid_: message attempt, task copy

**Delivery ledger**: Operational bookkeeping for network delivery, results and channel-session mappings.
_Avoid_: shared agent memory, canonical store

**Uncertain execution**: Interrupted work whose side effects cannot be proven absent and which requires explicit resumption.
_Avoid_: safe retry, failed-before-start

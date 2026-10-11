# Hermes Profiles over AG2 Network

## Problem Statement
Existing specialist Hermes Profiles cannot yet conduct durable autonomous conversations through AG2. Profiles must remain real Hermes runtimes with isolated persona, skills, tools and memory; a network must not replace them with AG2 model agents or ephemeral subagents.

## Solution
A separately installable bridge connects discovered and explicitly enrolled Hermes Profiles to native AG2 identities and persistent two-party conversation channels. Hermes network tools let specialists initiate consultations and continue a channel. The bridge submits only new messages to authenticated Hermes Runs using durable profile-owned sessions. Hub and bridge are optional user services; ordinary Hermes works without them.

## User Stories
1. As an owner, I want my existing profiles discovered, so that I do not rewrite the bridge when adding a specialist.
2. As a specialist, I want peers with their specialization descriptions, so that I can select the correct collaborator.
3. As an owner, I want stable profile-to-agent identities, so that reconnects preserve relationships.
4. As a specialist, I want to open a permanent project channel, so that later consultations continue the discussion.
5. As a specialist, I want to send a message, so that I can communicate asynchronously.
6. As a specialist, I want to ask and await a correlated answer, so that I can continue my own work.
7. As a recipient, I want my own real Hermes runtime to execute a request, so that my profile capabilities remain available.
8. As a specialist, I want channel history on demand, so that I can inspect prior exchanges without loading it into every turn.
9. As an owner, I want one Hermes session per profile/project/channel, so that repeated messages are not isolated one-shots.
10. As an owner, I want session lineage to follow native compaction/rotation, so that continuation does not fork stale history.
11. As an owner, I want two projects isolated, so that their dialogue and results cannot bleed across channels.
12. As an owner, I want network restoration after process restart, so that identities, channels and sessions remain stable.
13. As an owner, I want duplicate delivery suppressed, so that one operation does not launch multiple Hermes runs.
14. As an owner, I want uncertain interrupted work held for explicit resumption, so that a crash cannot automatically repeat side effects.
15. As a specialist, I want artifact references and images, so that collaboration includes verifiable results rather than only prose.
16. As an owner, I want large files represented by links and metadata, so that network messages do not inflate context unnecessarily.
17. As a specialist, I want verification reports and Git references, so that another agent can verify my conclusions.
18. As an owner, I want authentication and per-project peer allowlists, so that a caller cannot impersonate a different profile.
19. As an owner, I want depth/turn/concurrency budgets and deadlines, so that agents cannot enter infinite reply loops.
20. As an owner, I want each profile to retain its actual configured memory backend, so that integration cannot silently migrate or replace memory.
21. As an owner, I want private memory excluded from network discovery/history, so that sharing a result does not share a profile database.
22. As an owner, I want startup/stop/status through systemd user services, so that no terminal must remain open.
23. As an owner, I want disablement and rollback without breaking Hermes, so that the integration is a two-way door.
24. As an owner, I want live Coding/Architect E2E receipts, so that success is proven with genuine tools and models.
25. As a maintainer, I want a pinned compatible AG2 dependency and unchanged Hermes regressions, so that upgrades cannot quietly change the contract.

## Implementation Decisions
- AG2 owns registration, typed channel protocol, invitations, transports and channel WAL. Use AG2 1.1.2; no AG2 LLM/model configuration, memory harness or separate compactor.
- External Hermes identities use native custom envelope handlers. Disable the AG2 context/tool plugin and default model handler. If a public external-registration seam requires a minimal identity shim, document the exact tested limitation rather than claim a nonexistent external API.
- Use conversation channels for persistent two-party dialogue; ask is correlation/await adaptation over native send, not a fictional Channel.ask method.
- Separate Hub and bridge processes. Authenticated native AG2 transport, plus a loopback authenticated bridge interface for Hermes tools. Every caller is bound to one profile; peer/project permissions are checked before execution.
- A delivery ledger stores operation metadata, mapping and results; it is transport bookkeeping, not a long-term memory provider. Preserve exact payload and idempotency key on retry.
- Hermes execution uses authenticated profile-prefixed Sessions/Runs interfaces. Stable create IDs prevent duplicate sessions; Runs idempotency and reconciliation prevent duplicate launches. Do not resend AG2 history, alter existing sessions, or rely on in-memory agent/KV state.
- Follow native resume tip after each terminal run via supported session-message interface with zero messages requested. Origin and current IDs are recorded.
- Distinguish request/reply/status envelopes. Replies do not automatically cause another request; an explicit network action is required. Track causal ancestry, interaction budget and pending waits through nested calls. A visited-profile guard must prevent deadlocking recursive calls into an active session.
- Serialize a profile's incoming runs where required by Hermes memory/runtime constraints; allow independent projects' transport work concurrently under a bounded global cap. No promise that one profile can run concurrent memory writers safely.
- New profiles are discovered automatically, but execution eligibility/credentials remain explicit enrollment; discovery does not grant access.
- Artifact metadata is typed and allowlisted. Local files require approved roots/project grants; images use existing Hermes image input when authorized. No implicit traversal into another profile's private home.
- Coding and Architect currently have legacy file memory; default and Design have SQLite V2. Preserve these actual settings. Verify V2 behavior with isolated fixtures rather than silently switching live profiles.
- Standalone optional native plugin supplies agent_network.send/ask/open/history/peers (provider-safe tool names if dots are unsupported). It uses public plugin registration, preserves existing enabled plugins, and changes no SOUL/Skills/MCP/model/memory settings.
- User explicitly authorized API credentials, network-plugin enrollment for Coding/Architect, and controlled idle-only Gateway restart. Secrets go only into protected secret storage, never source, issues, logs or AG2 messages.
- User accepted no automatic replay of uncertain interrupted execution, the six-slice task graph and the agent_network test seam. User authorized publishing this spec/tickets to the configured GitHub tracker, not git push or main changes.

## Testing Decisions
- Test externally observable behavior through the agent_network interface. Prefer native Hub/transport/disk plus controlled executor fixtures for deterministic fault tests; use real Hermes for end-to-end acceptance.
- Each slice follows red-green tests one behavior at a time. No source-reading tests or implementation-specific call-count assertions substituted for observable behavior.
- Live acceptance: Coding explicitly consults Architect, receives useful advice and continues; second consultation resumes both relevant sessions; Hub/bridge restart; another consultation keeps identity/session/history; two projects remain isolated.
- Fault acceptance: duplicate operation, concurrent retry, unauthorized peer/project, history access, missing profile/API, timeout, interrupted run, nested-cycle rejection, max-depth/budget limits, corrupted/incomplete input and lost connection.
- Context acceptance: only new message/metadata/artifact references submitted; idle services produce no model calls; no automatic reply ping-pong.
- Memory acceptance: independent profile-owned backend/store, no network copies of private memory, deterministic SQLite V2 fixture isolation and unchanged backend flags in live profiles. Live memory writes, if tested, are performed only by each owning runtime in newly created network sessions.
- Hermes baseline already executed with canonical runner: five relevant existing files, 286 passed, zero failed, three Windows-only skips on Linux. Re-run relevant regressions after changes and attempt complete suite; distinguish pre-existing environment failures from integration regressions.
- Final two-axis Matt Pocock review: Standards and Spec. Every criterion requires a verifiable receipt; incomplete criteria remain open.

## Out of Scope
Profile migration to AG2, another coordination framework, replacement long-term memory, new compaction, required Kanban, modifying existing user sessions, copying AG2 source into Hermes, git push, merging into main, automatic retry of uncertain side effects.

## Further Notes
Current checkout and live Hermes memory implementation differ; the bridge calls the live HTTP runtime instead of executing worktree code against live homes. Native AG2 disk persistence is not transactional crash-safe exactly-once; one Hub owns each store and the bridge reconciles its own delivery ledger. Hermes public Runs does not expose per-session cwd/project binding; project IDs must not be misrepresented as automatic filesystem sandboxing. Document this limitation and require project-approved artifacts/workspace actions.

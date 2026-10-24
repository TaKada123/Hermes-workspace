# Fast, verified ticket delivery

## Acceptance-first

1. Map every acceptance criterion to its production seam, invariant test, and required evidence before the first substantial edit. Mark implemented, missing, or unverified; green tests prove only their covered scenarios. Completion: all criteria have an explicit verification path.
2. For concurrent/distributed execution, inspect the whole lifecycle together: pre-submit admission, lost acknowledgement, still-running work after caller timeout, nested branching budgets, shared/global bounds, restart/replay, terminal release, and private-store isolation. Distinguish execution limits from transport/queue limits. Completion: relevant failure transitions and scope are accounted for, not discovered one criterion per review round.
3. Fix related design gaps in one coherent implementation pass. Write deterministic RED regressions at the real seam; use controlled events rather than timing guesses. Keep conservative uncertain-execution protection even when it reduces availability.

## Bounded delegation

- Give the implementer a small self-contained packet: exact worktree/branch/base, ticket/spec paths, relevant area rules, current dirty-file scope, all known blockers, verified interpreter/runner commands, permissions, and acceptance map. Send relevant facts, not an entire conversation.
- Keep one implementer across related repair rounds when the runtime permits resuming it. If a new agent is required, pass a concise verified handoff so it need not rediscover setup and already settled decisions.
- Parallelize independent inspection and independent checks; serialize code changes that touch the same ownership boundary. Use one full Standards/Spec review after the coherent pass, then delta reviews for fixes and affected invariants.
- After roughly ten minutes of delegated work, inspect progress at the next user turn or tool boundary and steer when repeated exploration or irrelevant baseline repair is consuming time. This is a soft checkpoint, not a reason to poll or interrupt correct work. Give a concrete progress update; do not call a repair final before verification.

## Tight verification

- Discover the canonical runner, explicit owning/core fixture interpreter, and lint/type commands once. Include them in every handoff. Reuse isolated environments; do not substitute bare pytest when the repository requires its runner.
- During edits run the smallest relevant regression slice. After the coherent pass run the complete ticket suite and relevant core regressions; repeat a full suite only when later changes affect its coverage. Batch independent commands and preserve logs.
- Separate baseline violations from newly introduced ones using the fixed base. Record unrelated failures and limitations; repair them only when they block the agreed deliverable, not as unrequested architecture work.
- Before commit, stage the exact intended files and check the staged snapshot, including new files. Working-tree checks alone do not validate an older index.
- Publish only with authorization. Verify remote SHA, CI terminal result, and exact target readback before closing. A green ticket suite is not a claim that the entire monorepo or every platform was tested.

## Completion receipt

Report the artifact/commit, acceptance evidence, exact tested SHA, review disposition, remaining explicit limitations, and live-runtime/merge status. Never replace a missing receipt with confident wording.

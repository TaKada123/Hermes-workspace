# Bounded repair review

1. Take the previous findings, reviewed base/snapshot, exact repair diff, and updated verification receipts as inputs. Include staged, unstaged, and new files that belong to the change; a cached diff alone may be stale.
2. Recheck every unresolved finding plus dependencies and invariants affected by its repair. For concurrency fixes, follow reservation, nesting, uncertainty, replay, and release end to end. A narrow diff does not justify skipping connected safety paths.
3. Report each prior finding as resolved, unresolved, or evidence missing, with a concrete code/test reference. Raise new blockers when introduced or newly exposed by the repair; provide a reproducible scenario and consequence.
4. Classify baseline defects separately from new regressions. Do not repeatedly demand unrelated architecture relocation or broader platform/distribution support unless the ticket actually requires it.
5. Reuse verified runner/interpreter commands from the handoff. Rerun the relevant regression slice; use the full ticket suite when repair impact is broad or final acceptance requires it. Label inherited receipts versus independently rerun results.
6. Finish with PASS or specific remaining blockers and evidence gaps. Independent review is not satisfied by implementer self-report; reduced repeated reading must not reduce acceptance coverage.

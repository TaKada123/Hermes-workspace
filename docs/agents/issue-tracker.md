# Issue tracker: GitHub

Issues and specifications for this repository live in GitHub Issues at `TaKada123/Hermes-workspace`. Use the `gh` CLI for all operations.

## Conventions

- Create an issue: `gh issue create --title "..." --body "..."`.
- Read an issue: `gh issue view <number> --json number,title,body,labels,comments`.
- List issues: `gh issue list --state open --json number,title,body,labels,comments` with appropriate label and state filters.
- Make an issue a sub-issue of a parent: `gh issue create --parent <parent> ...`, or `gh issue edit <parent> --add-sub-issue <child>` afterwards (`gh` 2.94+).
- Comment: `gh issue comment <number> --body "..."`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`.
- Close: `gh issue close <number> --comment "..."`.

Infer the repository from `git remote -v`; `gh` does this automatically when run inside this clone.

## Pull requests as a triage surface

**PRs as a request surface: no.**

GitHub shares one number space across issues and pull requests. Resolve an ambiguous `#42` with `gh pr view 42`, then fall back to `gh issue view 42`.

## Skill terminology

- When a skill says "publish to the issue tracker", create a GitHub issue.
- When a skill says "fetch the relevant ticket", read the corresponding GitHub issue.

## Wayfinding operations

Used by `/wayfinder`. The map is a single issue with child issues as tickets.

- Map: one issue labelled `wayfinder:map`, containing Notes, Decisions-so-far, and Fog.
- Child ticket: a GitHub sub-issue of the map. If sub-issues are unavailable, add `Part of #<map>` and link it from a task list in the map.
- Blocking: use GitHub native issue dependencies. Where unavailable, use a `Blocked by: #<n>` line at the top of the child issue.
- Frontier: open children without open blockers or an assignee, in map order.
- Claim: assign the issue to the current user; this is the session's first write.
- Resolve: comment with the answer, close the child, then append a context pointer to Decisions-so-far in the map.

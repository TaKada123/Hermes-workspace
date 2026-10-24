# HERMES GITHUB TOOL ROUTER

**Version:** 1.0.0

## Purpose

Use GitHub's native capabilities deliberately during coding work, especially to run long-running test suites near the end of a ticket. This is a routing policy, not a claim that every GitHub feature is enabled or available in every repository.

## Always-on trigger

When a coding task involves a GitHub repository, branch, issue/ticket, pull request, CI run, release, or repository security/settings, consult this policy. For ordinary implementation, use only the relevant section; do not load or execute unrelated GitHub features.

## Ticket completion: tests and CI

1. At task start, identify the repository, current branch, remotes, relevant ticket/PR, available workflows and their trigger conditions. Check authentication and permissions with `gh auth status` and read-only GitHub queries before acting.
2. During implementation, run the fastest relevant local checks (focused tests, lint/type checks) for quick feedback. Do not send every tight edit loop to Actions.
3. Near the end of a ticket, before calling it complete, inspect the workflow that covers the project's long/slow tests. Prefer the existing canonical full-suite workflow; do not invent a weaker substitute or trigger unrelated deploy workflows.
4. Ensure the tested commit is the ticket's latest intended commit. GitHub Actions cannot test uncommitted local changes. Use an existing remote branch/ref; do not push code unless the user has authorized that push. If no suitable remote ref or workflow trigger exists, report the blocker and ask only for the required approval/action.
5. Trigger or observe the long test workflow on the relevant branch/PR using `gh workflow run`, `gh run list`, and `gh run watch`/`gh run view` as appropriate. Poll until it reaches a terminal state; inspect failed logs when it fails. Do not report success based only on enqueueing or a green local run.
6. Verify the run's repository, workflow, branch/ref, commit SHA, conclusion, and any required artifacts/status checks using a fresh GitHub read. Report the run URL/ID, exact tested SHA, and result. If failure, summarize the failing job and next useful action; do not mark the ticket complete as verified.
7. For Actions triggered automatically by push/PR, still read the resulting run and verify it corresponds to the ticket's current SHA. If no run appears, diagnose the workflow triggers rather than assuming CI ran.

## GitHub capability routing

Choose the smallest relevant capability, only after confirming it exists, is enabled, and the current account/repository permits its use:

- Actions: CI and test workflows; inspect run status and logs.
- Matrix: parallel independent test/build jobs when the workflow supports it and parallelism is appropriate.
- Cache: speed up repeat builds when cache keys/invalidation are safe; do not cache secrets or mutable outputs unsafely.
- CodeQL: code security analysis when configured/available.
- Copilot Autofix: remediate a confirmed CodeQL alert; review the diff and rerun relevant tests.
- Dependabot: dependency update monitoring and PRs; do not merge updates without review and checks.
- Codespaces: cloud development environment only when local setup is insufficient or user requests it.
- Agentic Workflows: use only when explicitly available, reviewed, and appropriately permissioned; treat generated workflow changes as code to review.
- Branch Protection: inspect/configure only when requested or clearly required; do not relax protections.
- Secret Scanning: inspect alerts and remediation; never expose secret values in output.
- Releases: publish only with explicit user authorization; verify release/tag after creation.
- Packages: publish only with explicit user authorization; verify published version.
- Pages: deploy/publish only with explicit user authorization; verify published URL/state.

## Safety, permissions, and cost

- First inspect current repo settings/workflows and the exact target/ref. Prefer read-only inspection.
- Confirm required permissions before mutation. Do not request or print tokens/secrets.
- Never start a paid service or incur a charge without explicit user approval. Free Actions runs can still consume concurrency/quota: use the existing intended workflow, avoid redundant dispatches, and do not cancel or rerun runs without reason.
- Pushes, merges, releases, publishing, settings changes, branch-protection changes, and secret modifications require the authorization specified by the active `PERMISSIONS.md`; this policy grants no additional permission.
- After every external state change, read the exact target back from GitHub and verify the effect.

## Available interfaces

Use the installed `gh` CLI for GitHub operations where it supports the task. Use `gh api` only for endpoints not covered by the CLI. A documented GitHub feature is not automatically an available Hermes tool or an enabled repository feature; verify before use. Load the `github` skill's matching reference for nontrivial issue, PR, repository, release, or authentication workflows.

# Inert upstream workflow contracts

`workflows/` contains **unmodified Git blobs**, not workflows enabled in this fork.
GitHub only discovers workflow definitions under the repository's top-level
`.github/workflows/`. Do not copy these inputs there, or rewrite their triggers,
permissions, reusable-workflow references, or publication steps to make a test pass.

## Provenance

The snapshot is from NousResearch/hermes-agent commit
`6590f13a1ba21b18224a0f53ef2ead004b5fa7d6`, the source of fork import
`bf81d7069df141137c44c32e2a0cf9cb743d5fdf`. The complete `agent/`, `scripts/`,
and `tests/` Git tree IDs match that import, not just selected workflow tests.
`manifest.json` records the revision, original directory, Git blob IDs, and SHA-256
of every definition. The integrity test detects missing, extra, or edited inputs.

The importer deliberately excluded upstream workflows in `7bb450ef` to avoid
activating upstream Actions in the fork. It also imported release scripts and
their contract tests. Those contracts still matter: they execute admission,
confinement, artifact, signing, and publication logic against mocked external
services and temporary repositories. `tests.ci.workflow_sources` separates those
upstream caller inputs from the fork's live Actions; the generic job-graph tests
cover **both** trees. No publication Actions are enabled by this archive.

## Refresh

Use a separate local clone checked out at the exact upstream source revision:

```sh
python3 scripts/ci/snapshot_upstream_workflows.py /path/to/upstream /path/to/new-snapshot
```

The output directory must not exist. Review the generated manifest and workflow
diff together with upstream source changes, then replace the tracked snapshot as
one unit and run:

```sh
scripts/run_tests.sh tests/ci tests/scripts/test_release_artifacts.py \
  tests/scripts/test_termux_build_driver.py tests/scripts/test_dispatch_log.py
```

The snapshotter reads committed Git objects, never dirty/untracked checkout files.

Refresh is intentionally manual. The unchanged source-import workflow remains a
wholesale `rsync --delete` source replacement, **not** a merge of fork changes.
Do not dispatch it as an incremental update: it does not preserve fork contract
adapters or this archive. A future upstream update requires an explicit rebase /
reviewed port of fork changes and a newly reviewed snapshot. This repair does not
claim to make that importer safe for preserving the fork.

Nix packaging was separately removed from this fork. The classifier no longer
advertises nonexistent flake paths or treats retired paths as Python-irrelevant;
unknown paths fail open. Its exported Nix lane and surviving manifest inputs stay
compatible with the upstream contract data.

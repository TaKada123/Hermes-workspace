# Inert upstream workflow fixtures

`upstream-workflows/` contains the official repository's GitHub Actions YAML as test inputs. The importer refreshes this directory from the shallow upstream clone while continuing to exclude `.github/workflows/` from the workspace, so none of these foreign workflows become executable by GitHub Actions here.

Tests that inspect upstream workflow definitions must resolve them through `tests.ci.workflow_fixtures.workflow_path`; only tests of this repository's own active workflows should read `.github/workflows/` directly.

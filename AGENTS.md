# Repository Guidelines

## Project Structure & Module Organization
This repository provides reusable Bazel macros, repo rules, and infrastructure helpers for other Svetoch projects. Core Starlark code lives in `tools/` (`macros/`, `rules/`, `repo_rules/`, `lint/`, `utils/`). Python support libraries live in `libs/py/` with packages such as `tf/`, `gcp/`, `helpers/`, and `utils/`. Dependency definitions are under `deps/` (`py/`, `deb/`, and image definitions). Provisioning and deployment entrypoints live in `scripts/init/` and `scripts/deploy/`. Terraform-related templates live in `terraform/`.

## Build, Test, and Development Commands
Use Bazel for all routine work:

- `bazel test //...` runs the full CI-equivalent test suite; this is what `.github/workflows/pr.yaml` executes.
- `bazel build //...` verifies targets build across the repository.
- `bazel run //:lint_fix_all` runs all registered formatters.
- `bazel run //deps/py:requirements_3_11.update` refreshes `deps/py/requirements_lock_3_11.txt` after editing `requirements.in`.

Run commands from the repository root so workspace-relative paths resolve correctly.

## Coding Style & Naming Conventions
Follow existing Bazel and Python patterns rather than introducing new layouts. Use 4 spaces in Python and keep Starlark files consistent with `buildifier`. Python formatting is enforced with Black through Bazel lint targets; Bazel files and `.bzl` files are checked with `buildifier`. Name Python tests as `test_*.py` when they target a single module, or `tests.py` for package-level coverage. Keep Bazel target names straightforward: `tests`, `lint`, and `lint_fix_*` are the established conventions.

## Testing Guidelines
Add or update tests in the same package as the code they cover, for example `libs/py/tf/test_state.py` with `libs/py/tf/BUILD.bazel`. Each Python package should expose a `py_test(name = "tests", ...)` target. Prefer focused unit tests that can run under `bazel test //...` without extra manual setup. If a change affects generated files or Terraform helpers, include representative test data in Bazel `data` attributes.

## Commit & Pull Request Guidelines
Recent commits use short, imperative subjects with an optional scope first, such as `Tfvars apply (#20)` or `Deps image + deb (#22)`. Keep commit titles concise and descriptive. Pull requests should explain the change, note any dependency or Terraform implications, and confirm `bazel test //...` passes. Link the related issue or PR number when applicable.

## Configuration Notes
Treat `terraform.tfvars.json` and related provisioning inputs as sensitive operational data. Do not commit secrets, and update lockfiles together with their source manifests.

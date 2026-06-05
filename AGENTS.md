# Repository Guidelines

## Overview

`svetoch_bazel_lib` is a reusable Bazel library that provides infrastructure provisioning macros, container image tooling, deployment automation, and Python runtime libraries for the **Rod** framework. It is consumed as a Bazel module (`bazel_dep`) by downstream Svetoch projects. The framework supports multi-cloud deployments on **GCP** and **Yandex Cloud (YC)**.

- **Bazel version**: 8.1.0 (pinned in `.bazeliskrc`)
- **Python version**: 3.11
- **Module system**: Bzlmod only (WORKSPACE is empty)

## Architecture

```
terraform.tfvars.json          ← Single source of truth (SSOT) for all environments
        │
        ▼
tools/extensions.bzl           ← Module extension: loads tfvars JSON into Starlark
        │
        ├──► tools/macros/tf.bzl       ← Terraform targets per environment/state
        ├──► tools/macros/img.bzl      ← Container image build + push per env
        ├──► tools/macros/deploy.bzl   ← CD: ArgoCD YAML update / Cloud Run deploy
        ├──► tools/macros/py_layers.bzl ← Layered Python images (3-layer)
        ├──► tools/macros/deb_packages.bzl ← Flatten .deb packages into tar
        │
        ▼
rod/libs/py/                   ← Python libraries (settings, helpers, tf models, gcp, yc, bazel)
        │
        ▼
rod/scripts/init/              ← Infrastructure provisioning pipeline (prepare → apply → images)
rod/scripts/deploy/            ← CD deployment scripts (ArgoCD, CloudRun, git push)
```

### Configuration Flow

1. `terraform.tfvars.json` is the SSOT. It defines company info, CI config, repo config, and all environments.
2. `tools/extensions.bzl` + `tools/repo_rules/load_json_file.bzl` read this JSON and expose it as a Starlark variable (`@svetoch_bazel_lib_tfvars//:json.bzl`).
3. `tools/utils/format.bzl` resolves template placeholders like `{env.cloud.location.region}` from tfvars values.
4. `tools/utils/common.bzl` builds env attribute dicts (`build_envs()`, `app_envs()`) used by image push and deploy macros.
5. All macros iterate over environments and create per-env targets (push_dev, push_prd, deploy_dev, etc.).

### Environment Model

- **`internal`**: Exactly one internal environment per project (infrastructure, shared services). Applied first during init.
- **`product`**: Deployment environments (development, staging, production, etc.). Copied from `terraform/environments/product/` template.
- **`initial_start`**: Boolean flag for bootstrapping — resources that depend on other TF modules are skipped when `true`. Set to `True` during init, then `False` after first apply pass.

## CI

- **Platform**: GitHub Actions
- **Trigger**: Pull requests to `master`
- **Concurrency**: Cancel in-progress runs for the same PR
- **Runner**: Custom container `europe-north1-docker.pkg.dev/svetochdev-internal/containers/bazelisk:v1.28.1-1`
- **Command**: `bazel test //...`
- **Config**: `.github/workflows/pr.yaml`

## Modules

### `tools/` — Bazel/Starlark Infrastructure

| Path | Purpose |
|---|---|
| `tools/extensions.bzl` | Module extension exposing `load_file.json()` tag class |
| `tools/repo_rules/load_json_file.bzl` | Repository rule: reads JSON file → generates `.bzl` with Starlark variable |
| `tools/macros/tf.bzl` | `tf()` macro: creates init, validate, lint, plan, apply, output, tf binary targets |
| `tools/macros/img.bzl` | `img_build()` / `img_push()`: OCI image build + per-env push targets |
| `tools/macros/deploy.bzl` | `deploy()`: ArgoCD (YAML update) or CloudRun deployment per env |
| `tools/macros/py_layers.bzl` | `py_layers()`: 3-layer Python images (interpreter / packages / app) |
| `tools/macros/deb_packages.bzl` | `deb_packages()`: flatten multiple .deb into one compressed tar |
| `tools/rules/json_gen.bzl` | Rule: writes string to JSON file |
| `tools/utils/format.bzl` | `format_dict()`, `formatted_tfvars()`: template placeholder resolution |
| `tools/utils/common.bzl` | `build_envs()`, `app_envs()`: env attribute dicts from tfvars |
| `tools/lint/bazel/buildifier.bzl` | `bazel_lint()` / `bazel_lint_fix()`: buildifier check + fix |
| `tools/lint/py/black.py` | Black formatter runner script |
| `tools/stamping/BUILD.bazel` | `stamp_img`: generates tagged file with `{{GIT_COMMIT}}` substitution |

### `rod/libs/py/` — Python Libraries

| Package | Purpose | Key Exports |
|---|---|---|
| `settings/` | Pydantic-settings models | `BazelSettings`, `YcSettings`, `AWSSettings`, `LogSettings`, `InitSettings` |
| `utils/` | Logging utilities | `BaseLogger`, `CliLogger`, `JsonLogger`, `RootLogger` |
| `helpers/` | Utility functions | `run_command`, `dict_to_dot_notation`, `replace_dotted_placeholders`, `create_dir`, `create_file`, `switch_index`, `find_value`, `unmask_tf` |
| `tf/` | Terraform support | `TfVars`, `Env`, `Cloud`, `App` models; `tfvars()`, `formatted_tfvars()`, `update_tfvars()`, `apply_env()`, `env_network_settings()` |
| `gcp/` | Google Cloud helpers | `cloudrun.py` (Cloud Run CRUD), `api.py` (enable GCP APIs) |
| `yc/` | Yandex Cloud helpers | `client.py` (SDK init), `sa.py` (service accounts), `bucket.py` (S3 buckets), `registry.py` (container registry) |
| `bazel/` | Bazel config utilities | `rc.py` (.bazelrc parse/serialize) |

### `rod/scripts/` — Operational Scripts

| Path | Purpose |
|---|---|
| `init/prepare.py` | Prepares `terraform.tfvars.json` for a new project (cloud choice, env config, CIDR allocation) |
| `init/poststeps.py` | Cleanup after init (remove template dirs, test dirs, .git) |
| `init/tf/prepare/` | Cloud-specific TF prep: enable GCP APIs, create YC SA + `.bazelrc.cloud` |
| `init/tf/apply/` | Apply TF modules in order (internal first, then products), two-pass with `initial_start` |
| `init/tf/secrets/` | Import Kubernetes secrets into TF state |
| `init/tf/state/` | Create GCS or YC S3 buckets for TF state |
| `init/tf/poststeps/` | Post-apply: update YC registry URLs in tfvars |
| `init/images/prepare/` | Set up `.docker/config.json` with cred helpers for registries |
| `init/images/build/` | Query and run all `push_*` Bazel targets |
| `deploy/change_yaml.py` | Update ArgoCD Helm values YAML with new image tags |
| `deploy/cloudrun.py` | Deploy to GCP Cloud Run |
| `deploy/push_commit.py` | Git commit + push for CD automation |
| `helm/apps/init.py` | Update Helm chart dependencies |

### `deps/` — Dependency Definitions

| Path | Purpose |
|---|---|
| `deps/py/` | Python requirements (`requirements.in` + lock file) |
| `deps/deb/` | Ubuntu Noble deb packages (`noble.yaml` + lock) |
| `deps/images/base/` | Ubuntu Noble base image from .deb packages |
| `deps/images/bazelisk/` | CI runner image with bazelisk + docker-credential-gcr |
| `deps/images/postgres/exporter/` | Custom postgres-exporter |
| `deps/images/postgres/spilo/17/` | Spilo 17 PostgreSQL with custom clone script |

### `terraform/` — Terraform Templates

| Path | Purpose |
|---|---|
| `terraform/tf_variables.tf.tpl` | Full Terraform variable schema template with validation rules |

## Key Patterns

### Multi-Cloud Support
- Cloud type determined by `env.cloud.name`: `"gcp"` or `"yc"`
- Registry types: `"gar"` (Google Artifact Registry) or `"ycr"` (Yandex Container Registry)
- DNS types: `"gcp"` or `"yc"`
- TF backend types: `"gcs"` (GCP) or `"s3"` (YC)
- Cloud-specific code paths in `rod/scripts/init/tf/prepare/` and `rod/libs/py/{gcp,yc}/`

### Terraform Macro Pattern (`tools/macros/tf.bzl`)
1. Reads tfvars for the environment via `formatted_tfvars(state_name)`
2. Renders `main.tf` from `main.tf.tpl` with cloud/backend/type substitutions
3. Generates `terraform.tfvars.json` and `tf_variables.tf` from templates
4. Creates targets: `srcs`, `srcs_lint`, `srcs_init`, `validate`, `lint`, `init`, `init_for_tests`, `plan`, `apply`, `output`, `tf` (binary), `lint_fix_tf`
5. Environment and state names are auto-detected from `native.package_name()` path segments

### Container Image Pattern
1. Base images built from `.deb` packages via `deb_packages()` macro
2. `img_build()` creates `oci_image` + `oci_load` targets
3. `img_push()` creates `oci_push` per-env with stamped tags (`{{GIT_COMMIT}}`)
4. Python images use `py_layers()` for 3-layer optimization: interpreter (rarely changes) → packages (sometimes) → app (often)

### Deploy Pattern
- **ArgoCD**: `deploy(type="argocd")` updates Helm `values.yaml` files with stamped image tags via `change_yaml.py`
- **CloudRun**: `deploy(type="cloudrun")` updates GCP Cloud Run service image via `cloudrun.py`

### Init Pipeline (Provisioning Order)
1. `prepare` — Prepare tfvars (cloud choice, envs, CIDRs)
2. `tf/prepare` — Cloud-specific prep (GCP APIs, YC SA + bazelrc)
3. `tf/copy_from_template` — Copy product template to per-env dirs
4. `tf/state_create` — Create remote state backends
5. `tf/apply` — Two-pass TF apply (initial_start=True → False)
6. `tf/import_secrets` — Import k8s secrets into TF state
7. `tf/poststeps/update_tfvars` — Resolve dynamic values (YC registry URLs)
8. `images/prepare` — Set up docker cred helpers
9. `images/build` — Build and push all images

## Build, Test, and Development Commands

- `bazel test //...` — Full CI test suite
- `bazel build //...` — Verify all targets build
- `bazel run //:lint_fix_all` — Run all formatters (buildifier + black)
- `bazel run //deps/py:requirements_3_11.update` — Refresh Python lock file after editing `requirements.in`
- `bazel run @svetoch_bazel_lib_noble//:lock` — Refresh deb packages lock file after editing `deps/deb/noble.yaml`

Run all commands from the repository root.

## Coding Style & Naming Conventions

- **Python**: 4-space indent, enforced with **Black** via `bazel run //:lint_fix_all`
- **Starlark/Bazel**: Enforced with **buildifier**
- **Test naming**: `test_*.py` for module-specific tests, `tests.py` for package-level coverage
- **Bazel targets**: `tests`, `lint`, `lint_fix_*`, `push_<env>`, `deploy_<env>`, `apply`, `plan`, `output`
- **Python packages**: Each has `py_test(name = "tests", ...)` and `py_lint()` macro
- **No comments** unless explicitly requested — code should be self-documenting

## Testing Guidelines

- Tests live in the same package as the code they cover
- Test data included via Bazel `data` attributes (e.g., `terraform.tfvars.json`)
- `tf_validate_test` and `tf_fmt_test` validate Terraform configs
- All tests must pass under `bazel test //...` without manual setup

## Commit & PR Guidelines

- Short, imperative subjects with optional scope: `Tfvars apply (#20)`, `Deps image + deb (#22)`
- PRs must confirm `bazel test //...` passes
- Link related issue/PR numbers

## External Dependencies (MODULE.bazel)

| Dependency | Version | Purpose |
|---|---|---|
| `rules_python` | 1.2.0 | Python toolchain + pip |
| `aspect_rules_py` | 1.3.2 | Python build rules |
| `rules_oci` | 2.3.0 | Container image rules |
| `rules_distroless` | 0.6.2 | .deb package handling |
| `rules_tf` | git override | Terraform rules (forked) |
| `rules_multirun` | 0.10.0 | Multi-command execution |
| `aspect_bazel_lib` | 2.22.5 | Tar utilities, expand_template |
| `buildifier_prebuilt` | 8.5.1 | Bazel file linting |
| `rules_bin_tools` | git override | Binary tool downloads (helm) |

## Configuration Notes

- `terraform.tfvars.json` is the SSOT — treat as sensitive operational data
- Template placeholders (`{env.cloud.location.region}`, etc.) are resolved at build time by `tools/utils/format.bzl`
- Do not commit secrets. `.bazelrc.cloud` (YC credentials) is gitignored
- Update lockfiles together with their source manifests (`requirements.in` → lock, `noble.yaml` → lock)

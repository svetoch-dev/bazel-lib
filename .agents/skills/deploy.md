# Skill: Deployment (ArgoCD & Cloud Run)

## Scope
Continuous deployment via Bazel targets: ArgoCD Helm values updates and GCP Cloud Run service updates.

## Key Files
- `tools/macros/deploy.bzl` — `deploy()` macro
- `rod/scripts/deploy/change_yaml.py` — ArgoCD YAML updater
- `rod/scripts/deploy/cloudrun.py` — Cloud Run deployer
- `rod/scripts/deploy/push_commit.py` — Git commit + push
- `tools/stamping/BUILD.bazel` — Stamped image tag file

## How deploy() Macro Works

### ArgoCD Deployment (type="argocd")
1. Creates `command()` target named `deploy_<env>` using `rules_multirun`
2. Runs `change_yaml.py` with args: `<values_file_pattern>`, `<service_name>`, `<tag_file>`
3. Values file pattern: `argocd/environments/*-<env>/<app>/values.yaml`
4. Reads stamped tag from `@svetoch_bazel_lib//tools/stamping:stamp_img`
5. Updates `data[service_name].image.tag` in values.yaml
6. Depends on `:push_<env>` target (ensures image is pushed first)

### Cloud Run Deployment (type="cloudrun")
1. Creates `command()` target named `deploy_<env>`
2. Runs `cloudrun.py` with args: `<project_id>`, `<region>`, `<service_name>`, `<image_url>`, `<tag_file>`
3. Updates Cloud Run service to use new image
4. Depends on `:push_<env>` target

### Both Types
- Iterate `build_envs()` and create targets only for listed envs
- Include `:push_<env>` in `data` to ensure build dependency chain is correct

## Steps to Add Deployment to a Service

1. In the service BUILD.bazel, ensure `img_push()` targets exist
2. Load and call deploy:
   ```python
   load("@svetoch_bazel_lib//tools/macros:deploy.bzl", "deploy")

   deploy(
       service_name = "my-service",
       envs = ["dev", "prd"],
       type = "argocd",
       app_name = "my-app",
   )
   ```
3. For Cloud Run:
   ```python
   deploy(
       service_name = "my-service",
       envs = ["dev"],
       type = "cloudrun",
   )
   ```

## Commands
- `bazel run //<package>:deploy_<env>` — Deploy service to environment
- Depends on `:push_<env>` automatically

## Conventions
- Deploy target naming: `deploy_<env_short_name>`
- ArgoCD values files follow pattern: `argocd/environments/*-<env>/<app>/values.yaml`
- The `change_yaml.py` preserves YAML formatting with custom Dumper
- Git commit + push (`push_commit.py`) is a separate step for CD pipelines

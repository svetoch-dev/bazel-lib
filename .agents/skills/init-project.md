# Skill: Project Initialization Pipeline

## Scope
The full infrastructure provisioning pipeline from project creation to running services. Covers `rod/scripts/init/` and all its sub-steps.

## Key Files
- `rod/scripts/init/prepare.py` — tfvars preparation
- `rod/scripts/init/poststeps.py` — Post-init cleanup
- `rod/scripts/init/tf/prepare/prepare.py` — Cloud-specific TF prep orchestrator
- `rod/scripts/init/tf/prepare/gcp.py` — GCP: enable APIs
- `rod/scripts/init/tf/prepare/yc.py` — YC: create SA, generate `.bazelrc.cloud`
- `rod/scripts/init/tf/apply/apply.py` — Two-pass TF apply
- `rod/scripts/init/tf/secrets/secrets.py` — Import k8s secrets
- `rod/scripts/init/tf/state/create.py` — Create remote state backends
- `rod/scripts/init/tf/poststeps/update_tfvars.py` — Post-apply tfvars updates
- `rod/scripts/init/images/prepare/prepare.py` — Docker cred helpers setup
- `rod/scripts/init/images/build/build.py` — Build + push all images

## Pipeline Steps (In Order)

### Phase 1: Configuration
1. **prepare** (`rod/scripts/init:prepare`)
   - Interactive: choose cloud (gcp/yc), choose envs
   - Allocates non-overlapping CIDR blocks
   - Fills cloud-specific defaults (tf_backend, registry, dns, location)
   - Sets `initial_start: true` on all envs
   - Writes updated `terraform.tfvars.json`

### Phase 2: Cloud Preparation
2. **tf/prepare** (`rod/scripts/init/tf/prepare:prepare`)
   - GCP: enables required APIs (compute, etc.)
   - YC: creates service account for TF state, generates `.bazelrc.cloud` with AWS credentials
   - Only runs for `internal` env type on YC (credentials are shared)

### Phase 3: Terraform Apply
3. **tf/apply** (`rod/scripts/init/tf/apply:apply`)
   - Two-pass apply strategy:
     - Pass 1: `initial_start=True` — creates base infra, skips dependent resources
     - Writes `terraform.tfvars.json` with `initial_start=False`
     - Pass 2: `initial_start=False` — creates all resources
   - Internal env is applied first
   - Secrets targets excluded from main apply (separate step)
   - Apply order: cloud → k8s → ... → secrets (last)

### Phase 4: Post-Apply
4. **tf/secrets** — Import existing k8s secrets into TF state
5. **tf/poststeps/update_tfvars** — Resolve dynamic values:
   - YC registry URLs derived from actual registry IDs
   - Writes final `terraform.tfvars.json`

### Phase 5: Images
6. **images/prepare** — Creates `~/.docker/config.json` with cred helpers:
   - GCP: `gcloud` cred helper for GAR
   - YC: `yc` cred helper for YCR
7. **images/build** — Queries all `push_*` targets under `deps/images/`, runs them sequentially

### Phase 6: Cleanup
8. **poststeps** — Removes product template dir, test dirs, `.git`

## Key Environment Variables

| Variable | Purpose |
|---|---|
| `BUILD_WORKSPACE_DIRECTORY` | Bazel workspace root (set by `bazel run`) |
| `YC_TOKEN` | Yandex Cloud IAM token |
| `YC_METADATA_ADDR` | YC metadata endpoint (default: 169.254.169.254) |
| `USER` | Used for logging who triggered operations |
| `AWS_ENDPOINT_URL_S3` | S3 endpoint for YC TF state |
| `ROD_INIT_TEST` | Test mode flag |

## Commands
- `bazel run //rod/scripts/init:prepare -- gcp --envs dev,prd` — Prepare tfvars
- `bazel run //rod/scripts/init/tf/prepare:prepare` — Cloud prep
- `bazel run //rod/scripts/init/tf/apply:apply` — Apply TF
- `bazel run //rod/scripts/init/images/prepare:prepare` — Docker cred setup
- `bazel run //rod/scripts/init/images/build:build` — Build+push images

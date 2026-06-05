# Skill: Yandex Cloud Operations

## Scope
All Yandex Cloud (YC) integration: authentication, service accounts, S3 buckets, container registry, and TF state backend.

## Key Files
- `rod/libs/py/yc/client.py` — SDK initialization + auth
- `rod/libs/py/yc/sa.py` — Service account management
- `rod/libs/py/yc/bucket.py` — S3 bucket operations
- `rod/libs/py/yc/registry.py` — Container registry operations
- `rod/scripts/init/tf/prepare/yc.py` — YC cloud prep (SA + bazelrc)
- `rod/scripts/init/tf/poststeps/update_tfvars.py` — YC registry URL resolution

## Authentication (client.py)

### Auth Methods (Priority Order)
1. Explicit IAM token passed to `sdk_get(token=...)`
2. `YC_TOKEN` environment variable
3. Instance metadata endpoint (`http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token`)

### Usage
```python
from rod.libs.py.yc.client import sdk_get
sdk = sdk_get()  # Raises AuthError if no auth available
```

### YcSettings (from rod/libs/py/settings/)
- `tf_state_sa` — Service account name for TF state (default: "tf-state")
- `caller` — From `$USER` env var

## Service Accounts (sa.py)
- `YcServiceAccount(folder_id, name)` — Create/manage service accounts
- `create_access_key(description)` — Create static access key (AWS-compatible) for S3 backend
- Used in `rod/scripts/init/tf/prepare/yc.py` to bootstrap TF state credentials

## S3 Buckets (bucket.py)
- `YcBucket(folder_id, name, create_if_missing)` — Create/manage YC Object Storage buckets
- `YcBucketObject(bucket, key, content)` — Put objects into buckets
- Used for TF state backend (S3-compatible)

## Container Registry (registry.py)
- `YcRegistry(folder_id, name, create_if_missing)` — Create/manage YC Container Registry
- `endpoint` property — Returns full registry URL from registry ID
- Used in `update_tfvars.py` to resolve registry URLs after TF apply

## TF State Backend Setup (prepare/yc.py)

1. Check if `.bazelrc.cloud` already exists (skip if present)
2. Create YC service account for TF state
3. Create static access key (access_key_id + secret_key)
4. Parse `.bazelrc.cloud.yc` template
5. Replace `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` placeholders
6. Write `.bazelrc.cloud`

### .bazelrc.cloud Template
Contains `build --action_env` and `run --//run_env` entries for AWS credentials that Bazel passes to TF for S3 backend authentication.

## Steps to Add a New YC Operation

1. Add function to appropriate module in `rod/libs/py/yc/`
2. Use `sdk_get()` to get authenticated SDK
3. Follow existing patterns: Pydantic models for settings, `CliLogger` for logging
4. Add tests in `tests.py` within the same package

## Commands
- `bazel test //rod/libs/py/yc:tests` — Test YC library
- `bazel run //rod/scripts/init/tf/prepare:prepare` — Run YC prep (auto-detects cloud from tfvars)

## Conventions
- YC folder_id is required for all operations
- Registry URL is empty initially, resolved after TF apply via `update_tfvars.py`
- `.bazelrc.cloud` is gitignored (contains credentials)

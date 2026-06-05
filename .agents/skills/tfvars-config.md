# Skill: Terraform.tfvars.json Configuration

## Scope
Managing the `terraform.tfvars.json` file — the single source of truth for all environments, cloud config, apps, and infrastructure settings.

## Key Files
- `terraform.tfvars.json` (repo root) — The configuration file
- `rod/libs/py/tf/tfvars.py` — Pydantic models validating the schema
- `terraform/tf_variables.tf.tpl` — Terraform variable definitions template
- `tools/utils/format.bzl` — Starlark-side template resolution
- `rod/libs/py/helpers/__init__.py` — `dict_to_dot_notation`, `replace_dotted_placeholders`
- `rod/scripts/init/prepare.py` — Interactive tfvars preparation

## Schema (Pydantic Models)

### Top Level: TfVars
- `company: Company` — name, domain
- `repo: Repo` — name, type (github/gitlab), group
- `ci: Ci` — type (gl/gha), bazelisk_img_version
- `envs: dict[str, Env]` — environment definitions

### Env
- `name` — Full environment name (e.g., "development")
- `short_name` — Short name (e.g., "dev")
- `type` — `"internal"` (exactly one) or `"product"`
- `test` — Test environment flag
- `initial_start` — Bootstrap flag (skip dependent resources)
- `users: dict[str, User]` — name + roles
- `apps: dict[str, App]` — Application definitions
- `import_secrets: dict[str, ImportSecret]` — Secrets to import into TF
- `registry: Registry` — type (ycr/gar), url
- `dns: Dns` — domain, type (gcp/yc)
- `tf_backend: TfBackend` — type (gcs/s3), configs
- `cloud: Cloud` — name (gcp/yc), id, folder_id, location, network, buckets
- `kubernetes: Kubernetes` — enabled, regional, node_locations, auth_group

### Cloud
- `name` — "gcp" or "yc"
- `id` — GCP project ID or YC cloud ID
- `folder_id` — Required for YC
- `location: Location` — region, default_zone, multi_region
- `network: Network` — vm_cidr, k8s_pod_cidr, k8s_service_cidr
- `buckets: Buckets` — multi_regional, deletion_protection

### App
- `name`, `postgres`, `redis`, `rabbitmq`
- `access_roles: AppAccessRoles` — port_forward scope
- `repo: AppRepo` — name, group
- `cd: AppCD` — branch, file, tag_path

## Template Placeholders

Placeholders like `{env.cloud.location.region}` are resolved by `formatted_tfvars()`:

| Placeholder | Source |
|---|---|
| `{company.domain}` | `tfvars.company.domain` |
| `{company.name}` | `tfvars.company.name` |
| `{env.cloud.location.region}` | Per-env cloud region |
| `{env.cloud.id}` | Per-env cloud project/cloud ID |
| `{env.registry.url}` | Per-env registry URL |
| `{env.dns.domain}` | Per-env DNS domain |
| `{env.short_name}` | Per-env short name |
| `{tf_backend.state_name}` | State name (from path) |
| `{tf_backend.type}` | Per-env backend type |

## Steps to Prepare tfvars for a New Project

1. Run `bazel run //rod/scripts/init:prepare -- <cloud> [--envs dev,prd]`
2. Cloud must be `gcp` or `yc`
3. Allowed env short names: `dev`, `stg`, `prd`, `pre`, `sandbox`
4. This fills in cloud-specific defaults, allocates CIDRs, sets `initial_start: true`
5. Manually fill `CHANGE_ME` placeholders with actual values

## CIDR Allocation
- `env_network_settings()` divides `10.0.0.0/8` into `/14` subnets
- Each env gets two adjacent `/14`s: one for VM+service (`/20` each), one for pods
- Existing env CIDRs are excluded from allocation

## Validation Rules
- Exactly one env must be `type: "internal"`
- `cloud.name` must be `"gcp"` or `"yc"`
- `dns.type` must be `"gcp"` or `"yc"`
- `registry.type` must be `"ycr"` or `"gar"`
- `folder_id` is required when `cloud.name == "yc"`

## Commands
- `bazel run //rod/scripts/init:prepare -- gcp --envs dev,prd` — Prepare GCP tfvars
- `bazel run //rod/scripts/init:prepare -- yc --envs dev,prd` — Prepare YC tfvars

# v0.18.0

This release adds an explicit environment classification to
`terraform.tfvars.json` and renames the Terraform product template directory
setting. Agents upgrading a downstream project should treat this as both a data
schema migration and a source-code reference migration.

## Agent Upgrade Checklist

1. Update the `svetoch_bazel_lib` `git_override` commit in `MODULE.bazel` to
   the commit which target release git tag is pointing to.
2. Open the downstream project's root `terraform.tfvars.json`.
3. For every object under `envs`, add the required top-level `type` string:
   - Use `"internal"` for the infrastructure/internal environment.
   - Use `"product"` for environments that should receive product Terraform
     templates and app deployment macros.
4. Do not infer internal environments from `short_name == "int"` anymore.
   Search downstream code, tests, and docs for these patterns and update them:
   - `short_name == "int"`
   - `short_name != "int"`
   - env key/name checks such as `env_name != "int"` when the intent is to
     skip internal environments.
   Replace those checks with `env.type == "internal"` or
   `env.type == "product"` depending on the intent.
5. Rename Terraform product template paths:
   - Rename `terraform/environments/template` to
     `terraform/environments/product` if that directory exists.
   - Update references to `bazel_settings.tf_template_dir` to
     `bazel_settings.tf_product_dir`.
   - Update references to `tf_template_dir_override` or
     `TF_TEMPLATE_DIR_OVERRIDE` to `tf_product_dir_override` or
     `TF_PRODUCT_DIR_OVERRIDE`.
6. Update tests and fixtures that construct `Env` objects or inline
   `terraform.tfvars.json` data. Every environment fixture now needs
   `type = "internal"` or `type = "product"`.
7. Run a text search after editing. No downstream source should still reference:
   - `tf_template_dir`
   - `tf_template_dir_override`
   - `TF_TEMPLATE_DIR_OVERRIDE`
   - `short_name == "int"` for environment classification.
8. Run `bazel test //...` from the downstream repository root. If that is too
   broad for the context, run at least the Terraform init/apply/prepare targets,
   lint targets, and any tests that parse `terraform.tfvars.json`.

## terraform.tfvars.json Migration

Old shape:

```json
{
  "envs": {
    "internal": {
      "name": "internal",
      "short_name": "int"
    },
    "production": {
      "name": "production",
      "short_name": "prd"
    }
  }
}
```

New shape:

```json
{
  "envs": {
    "internal": {
      "name": "internal",
      "short_name": "int",
      "type": "internal"
    },
    "production": {
      "name": "production",
      "short_name": "prd",
      "type": "product"
    }
  }
}
```

The valid values are exactly `"internal"` and `"product"`. Terraform validation
and the Python tfvars model reject any other value.

## Product Template Directory Migration

The default product-template directory is now:

```text
terraform/environments/product
```

instead of:

```text
terraform/environments/template
```

Agents should rename the directory, then update any scripts, BUILD targets,
README files, CI configuration, or tests that refer to the old path. Product
environment directories are copied from `terraform/environments/product`;
internal environments are skipped based on `envs[*].type == "internal"`.

## Common Agent Pitfalls

- Do not add `type` under `cloud`, `registry`, or `dns`; it belongs directly
  under each `envs[*]` object.
- Do not set `type` to stage names such as `dev`, `prod`, `prd`, or `staging`.
  Use only `internal` or `product`.
- Do not keep using `short_name == "int"` as the source of truth. In this
  release an internal environment can have any short name.
- Do not leave `terraform/environments/template` in place if the project relies
  on the library's prepare/copy or poststep clean scripts. Rename it to
  `terraform/environments/product`.
- Do not update production-like environments only. Every environment entry,
  including tests and examples, must include `type`.

# v0.17.0

This release changes the `terraform.tfvars.json` schema consumed by
`svetoch_bazel_lib`. Agents upgrading a downstream project should edit the
project's root `terraform.tfvars.json` and any generated examples, tests, or
documentation that duplicate that schema.

## Agent Upgrade Checklist

1. Update the `svetoch_bazel_lib` `git_override` commit in `MODULE.bazel` to
   the commit which target release git tag is pointing to.
2. Open the downstream project's `terraform.tfvars.json`.
3. For every object under `envs`, migrate the environment schema:
   - Move `cloud.region`, `cloud.default_zone`, and `cloud.multi_region` into
     `cloud.location`.
   - Move `cloud.registry` out of `cloud` and replace it with top-level
     environment object `registry`.
   - Add top-level environment object `dns`.
4. Replace old placeholder paths in tfvars strings and templates:
   - Use `{env.cloud.location.region}` instead of `{env.cloud.region}`.
   - Use `{env.registry.url}` instead of `{env.cloud.registry}` when a registry
     URL is needed.
   - Use `{env.dns.domain}` or `{env.dns.type}` when DNS data is needed.
5. Normalize enum-like values to the new allowed strings:
   - `ci.type`: `gl` or `gha`.
   - `repo.type`: `gitlab` or `github`.
   - `envs[*].cloud.name`: `gcp` or `yc`.
   - `envs[*].dns.type`: `gcp` or `yc`.
   - `envs[*].registry.type`: `gar` or `ycr`.
6. If `envs[*].cloud.name` is `yc`, ensure `envs[*].cloud.folder_id` is set to
   a non-empty string.
7. Run `bazel test //...` from the downstream repository root. If that is too
   broad for the context, run at least the init/Terraform-related test targets
   and the targets that read `terraform.tfvars.json`.

## terraform.tfvars.json Migration

Old shape:

```json
{
  "envs": {
    "production": {
      "cloud": {
        "name": "gcp",
        "id": "example-production",
        "region": "europe-west2",
        "default_zone": "europe-west2-c",
        "multi_region": "EU",
        "registry": "{env.cloud.region}-docker.pkg.dev/{env.cloud.id}/containers"
      }
    }
  }
}
```

New shape:

```json
{
  "envs": {
    "production": {
      "registry": {
        "type": "gar",
        "url": "{env.cloud.location.region}-docker.pkg.dev/{env.cloud.id}/containers"
      },
      "dns": {
        "domain": "{env.short_name}.{company.domain}",
        "type": "gcp"
      },
      "cloud": {
        "name": "gcp",
        "id": "example-production",
        "location": {
          "region": "europe-west2",
          "default_zone": "europe-west2-c",
          "multi_region": "EU"
        }
      }
    }
  }
}
```

For Yandex Cloud environments, use this pattern:

```json
{
  "registry": {
    "type": "ycr",
    "url": "cr.yandex/<registry-id>"
  },
  "dns": {
    "domain": "{env.short_name}.{company.domain}",
    "type": "yc"
  },
  "cloud": {
    "name": "yc",
    "id": "<cloud-id>",
    "folder_id": "<folder-id>",
    "location": {
      "region": "ru-central1",
      "default_zone": "ru-central1-a"
    }
  }
}
```

## Common Agent Pitfalls

- Do not leave `registry` inside `cloud`; consumers now read
  `env.registry.url`.
- Do not leave location fields directly under `cloud`; consumers now read
  `env.cloud.location.region`.
- Do not use provider names interchangeably: `repo.type` is `github` or
  `gitlab`, while `ci.type` is `gha` or `gl`.
- Do not omit `dns`; it is now required for each environment.
- Do not use `yc` as a registry type. Use `ycr` for Yandex Container Registry.
- For `yc` cloud environments, do not rely on `cloud.id` alone; set
  `cloud.folder_id`.

# v0.16.0

Update `git_override` commit for `svetoch_bazel_lib` to commit that `v0.16.0` tag points to eg

```
module(name = "<module_name>")

###########
# Bazel
###########

....
bazel_dep(name = "svetoch_bazel_lib")

git_override(
    module_name = "svetoch_bazel_lib",
    commit = "<commit>",
    remote = "https://github.com/svetoch-dev/bazel-lib",
)
...
```

## Python files

Instead of:
```
import libs.py.settings
```
Use:
```
import rod.libs.py.settings
```

## BUILD.bazel

Instead of 
```
@svetoch_bazel_lib//libs/py/...
@svetoch_bazel_lib//scripts/...
```
use
```
@svetoch_bazel_lib//rod/libs/py/...
@svetoch_bazel_lib//rod/scripts/...
```

# v0.30.0

## Bazel 9 and Python Rules Migration for AI Agents

Use these instructions to upgrade a downstream repository that depends on
`svetoch_bazel_lib`. Read that repository's `AGENTS.md`, inspect its current
configuration, and preserve existing user changes before editing. Apply only
steps relevant to the consumer. Keep all earlier versioned guides below for
projects upgrading across multiple releases.

### Upgrade Scope and Discovery

1. Inspect `git status --short`, the dependency pin for `svetoch_bazel_lib`,
   Bazelisk configuration, `.bazelrc`, Python rules, and any direct apt usage.
   Start with:

   ```bash
   rg -n --hidden --glob '!.git/**' --glob '!MODULE.bazel.lock' \
     'svetoch_bazel_lib|USE_BAZEL_VERSION|rules_python|aspect_rules_py|legacy_create_init|apt\.install|apt\.sources_list|trixie\.yaml' .
   ```

2. Resolve the requested library release tag to its commit and update the
   downstream `git_override` to that full SHA. Do not substitute a moving branch
   for an immutable pin. Inspect the target release's `MODULE.bazel` and
   `.bazeliskrc`; do not assume versions from model memory are current.
3. This release uses Bazel 9.3.1, `rules_python` 2.4.5, and
   `aspect_rules_py` 2.0.0-alpha.10. The Aspect prerelease is intentional in this
   release; do not silently replace it with an older stable version. Reconcile
   downstream direct dependencies with the selected library release and their
   compatibility requirements.
4. If the user instead requests the latest versions, verify official releases
   and Bazel Central Registry metadata at task time. Exclude yanked versions
   and do not introduce prereleases merely because they sort above stable
   releases. Keep unrelated tool, image, Debian snapshot, and Python package
   updates outside the requested migration.

### Bazel Configuration

1. Update the consumer's existing Bazel pin. This library uses `.bazeliskrc`:

   ```text
   USE_BAZEL_VERSION=9.3.1
   ```

   Consumers using `.bazelversion` should update that file instead. Avoid
   conflicting pins. Run `bazel --version` and investigate environment overrides
   if the selected version differs. Ensure CI launches through Bazelisk as well.
2. Bazel 9 removes `WORKSPACE` dependency evaluation. Migrate remaining
   dependencies to Bzlmod and load language rules explicitly from their
   rulesets. Inspect custom `.bzl` files and third-party dependencies as well as
   `BUILD.bazel` files. Read the official Bazel migration notes before replacing
   removed APIs or flags.
3. Repository rules no longer inherit `--action_env` settings in Bazel 9.
   Inspect download/proxy configuration and use `--repo_env` where repository
   evaluation needs an explicit value. Preserve existing proxy and cache setup.
4. If the consumer combines Aspect Python targets with tools that require
   `rules_python` providers, preserve the compatibility setting used here:

   ```text
   common --@aspect_rules_py//py:emit_rules_python_providers
   ```

   Check that the selected Aspect version supports the flag before adding it.
   Do not remove it solely to silence an error without checking provider
   compatibility in the affected targets.

### Python Targets

1. Keep the intended runtime version explicit and aligned across
   `python.defaults`, `python.toolchain`, `pip.parse`, versioned rule loads, and
   requirements files. This release retains Python 3.11; a Bazel or ruleset
   upgrade must not silently upgrade the application's Python runtime.
2. For targets in the downstream module, opt out of implicit `__init__.py`
   generation in its own `MODULE.bazel`:

   ```starlark
   rules_python_config = use_extension("@rules_python//python/extensions:config.bzl", "config")
   rules_python_config.explicit_init_py(default = True)
   ```

   Reuse an existing extension binding if present. Include real `__init__.py`
   files in `srcs` or dependencies when regular packages require them. Namespace
   packages do not need empty files just to suppress warnings. A dependency's
   module setting does not configure the consumer's module.
3. Inspect Python entrypoints shared across Bazel packages. Use an explicit
   `main` label for such files and expose them with appropriate source-file
   visibility. The library's lint macros already do this; migrate downstream
   equivalents if analysis reports missing or invisible entrypoints.
4. Classify remaining warnings by their owning module. A warning from
   `@rules_multirun` is separate from a warning in the application's targets.
   Do not disable checks globally to hide a dependency warning.
5. If Python requirements themselves change, regenerate their lockfile using
   the consumer's Bazel update target. In this library the command is:

   ```bash
   bazel run //deps/py:requirements_3_11.update
   ```

   Include source manifests and generated locks together. Do not refresh Python
   packages solely because the Bazel version changed.

### Direct Debian/Apt Consumers

Apply this section only if the downstream project declares apt dependencies
itself. Consumers that only reference the library's image targets do not need to
copy its apt setup.

- Replace old `apt.install(name = ..., manifest = ..., lock = ...)` declarations
  with `apt.sources_list(...)` and
  `apt.install(dependency_set = ..., packages = [...])` using the selected
  `rules_distroless` API. Preserve the repository name through `dependency_set`
  and the corresponding `use_repo` declaration where supported.
- Transfer source URLs, suites, components, architectures, package lists, and
  every package explanation from the YAML manifest. Preserve base-image and
  tooling groups. Use `# buildifier: disable=unsorted-list` inside a package list
  when needed to preserve its documented order.
- Keep Debian snapshot dates unchanged during the API migration. Updating the
  snapshot also upgrades OS packages and needs separate review and validation.
- Under this Bazel 9 setup, snapshot index facts are stored in
  `MODULE.bazel.lock`. Retire obsolete YAML manifests and version 1 apt locks
  only after removing their consumers. Do not retain obsolete
  `bazel run @<apt_repository>//:lock` instructions.

### Lockfiles, Validation, and Completion

1. Let Bazel regenerate `MODULE.bazel.lock` and include it with dependency
   changes. Do not hand-edit hashes or delete the lockfile to conceal a
   resolution failure. Inspect generated metadata for sensitive provisioning
   inputs; do not expose `terraform.tfvars.json` contents in logs or docs.
2. Preserve entries for other host systems. One lockfile can contain Linux and
   macOS ARM extension results. Adding a platform should not normally replace
   another platform's entries. Investigate repeated churn for differing Bazel
   versions, environment inputs, or extension behavior. Report only platforms
   actually tested.
3. Use the consumer's formatter and full Bazel test suite. In this library:

   ```bash
   bazel run //:lint_fix_bzl
   bazel test //...
   git diff --check
   ```

   Review formatter changes for scope. Run focused tests while diagnosing
   failures, then rerun the full suite after final code/configuration changes.
   Use `bazel build //...` additionally if changed output groups or target
   coverage require it. Do not run Terraform apply, deployment, or image
   publishing as migration validation.
4. If Gentoo host detection fails, inspect `ldd --version` and the selected
   ruleset's parser. Older Aspect versions failed on Gentoo's banner and nested
   parentheses. Verify whether an upstream fix applies before adding a patch;
   do not reintroduce a historical workaround automatically.
5. Summarize changed pins, compatibility fixes, actual test results, remaining
   warnings, and untested platforms or runtime behavior. Building images does
   not prove their tools run correctly. Distinguish cached test passes from
   tests executed during the migration.

References for agents to verify against the selected versions:

- [Bazel 9 migration notes](https://github.com/bazelbuild/bazel/releases/tag/9.0.0)
- [Bazel Central Registry](https://registry.bazel.build/)
- [Bazel lockfile behavior](https://bazel.build/external/lockfile)

# v0.29.0

## Python tfvars Enum Migration for AI Agents

The Python tfvars models now expose `Env.type`, `Ci.type`, `Repo.type`, and
`Registry.type` as string-backed enum members, following the existing
`CloudTypeEnum` and `DnsTypeEnum` pattern. Apply the following migration to
downstream Python consumers, including scripts, tests, mocks, and fixtures.

### Field and Value Mapping

Import these enums from `rod.libs.py.tf.tfvars`:

| Python field | Enum | Members and serialized values |
| --- | --- | --- |
| `Env.type` | `EnvTypeEnum` | `internal = "internal"`, `product = "product"` |
| `Ci.type` | `CiTypeEnum` | `gl = "gl"`, `gha = "gha"` |
| `Repo.type` | `RepoTypeEnum` | `github = "github"`, `gitlab = "gitlab"` |
| `Registry.type` | `RegistryTypeEnum` | `ycr = "ycr"`, `gar = "gar"` |

### Agent Upgrade Checklist

1. Update the downstream `svetoch_bazel_lib` dependency pin in `MODULE.bazel`
   to the commit referenced by the target release tag.
2. Search Python consumers before editing. Start with:

   ```bash
   rg -n --glob '*.py' 'Env\(|Ci\(|Repo\(|Registry\(|\.type\b|model_dump\(|model_dump_json\(' .
   ```

   Inspect aliases, dictionary fixtures, assignments, and `SimpleNamespace` or
   mock objects as well as direct model construction. Classify each match by
   the model it represents; `.type` alone is not enough to choose an enum.
3. Add imports for the relevant enum classes and replace Python literals in
   comparisons, assignments, constructors, and typed test fixtures with the
   matching members from the table. For example:

   ```python
   from rod.libs.py.tf.tfvars import (
       Ci,
       CiTypeEnum,
       EnvTypeEnum,
       Registry,
       RegistryTypeEnum,
       Repo,
       RepoTypeEnum,
   )

   ci = Ci(type=CiTypeEnum.gha)
   repo = Repo(name="app", group="team", type=RepoTypeEnum.github)
   registry = Registry(type=RegistryTypeEnum.gar, url="registry.example.com")

   if env.type == EnvTypeEnum.internal:
       prepare_internal(env)
   if env.registry.type == RegistryTypeEnum.ycr:
       refresh_registry(env)
   ```

4. Preserve strings at data boundaries. Existing valid strings are still
   accepted by Pydantic and converted into enum members. Keep string-input
   parsing tests and invalid-value validation tests. `terraform.tfvars.json`,
   Terraform templates, and Starlark code reading JSON continue to use the
   strings in the table; their values and placeholder paths do not change.
5. Audit serialization and interpolation. Plain `model_dump()` retains enum
   members. Use `model_dump(mode="json")` when producing a dictionary for
   placeholder replacement or external data, and `model_dump_json()` when
   producing JSON text. Use `.value` when interpolating an individual enum
   into a string; `str(member)` and f-strings can produce names such as
   `RegistryTypeEnum.gar` instead of `gar`. Existing `formatted_tfvars()` and
   `update_tfvars()` already handle enum serialization.
6. Update tests to assert enum identity after validation, for example
   `assert ci.type is CiTypeEnum.gha`. Verify each supported string and enum
   input, invalid-value rejection, JSON round trips, and any downstream
   placeholder rendering involving these fields.
7. Repeat the search and review remaining literals by context. Do not replace
   unrelated `.type` fields such as `TfBackend.type`, or provider values used
   by other APIs. Do not interchange `RepoTypeEnum.gitlab` and `CiTypeEnum.gl`,
   or `CloudTypeEnum.yc` and `RegistryTypeEnum.ycr`.
8. Run `bazel test //...` from the downstream repository root. Report the
   command and outcome, distinguishing migration failures from unrelated
   failures. If the full suite cannot run, report that limitation and run
   the affected Python tests and lint targets available in the project.

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

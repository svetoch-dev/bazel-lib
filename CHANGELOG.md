# v0.22.0

Features:
* `rod/libs/py/tf/output` get something from tf output functions
* `macros/{tf.bzl,tfvars_update.py}` script that gets registries from output and updates tfvars
* `rod/scripts/init/tf/poststeps` update_tfvars script
* `rod/libs/py/yc/registry` YcRegistry


Enhancements:
* `rod/scripts/init/{prepare,poststeps,tf/poststeps}.py` do not do anything if `ROD_INIT_TEST=true`

# v0.21.0

Features:
* `rod/libs/py/yc/bucket` YcBucketObject class
* `rod/scripts/init/tf/state` create empty statefile for secrets root module

Enhancements:
* `rod/scripts/init/tf/state` run yande related code only if type is s3 and s3_endpoint is `https://storage.yandexcloud.net`

# v0.20.0

Features:
* `rod/libs/py/settings`
  * YcSettings class
  * BazelSettings new `rc_cloud*` properties that are strings with paths to bazelrc files
* `rod/libs/py/yc/sa`
  * `YcServiceAccount` class for interacting with yc service accounts
  * `YcBucket` yc bucket class
* `rod/scripts/init/tf/prepare/yc` yandex cloud prepare script that
  * creates yandex sa for tf state bucket access
  * creates access key for yandex sa
  * creates `.bazelrc.cloud` file with to populate `AWS_*` env vars needed for accessing tf state
* `tools/macros/tf`
  * add `tf_output` to tf macro
* `rod/libs/py/tf/apply` `rapply` -> `mapply` 
* `rod/libs/py/bazel/rc` functions that serialize bazelrc files to objects and desrilize bazelrc objects to bazelrc files

Fixes:
* `rod/libs/py/tf/tfvars`
  * `AppRepo|AppCD` are None by default
* `tools/utils/format` dont cast to `str` use `json.encode` instead


# v0.19.0

Braking changes:
* `ci.group` attributes are moved to `...app.repo.group`

Features:
* `tools/macros/tf.bzl` can render variable `ci.type`
* `terraform/tf_variables.tf.tpl` new app attributes - `repo` and `cd`

# v0.18.0

Braking changes:
* `rod/lib/py/settings` `tf_template_dir` -> `tf_product_dir`

Features:
* `terraform.tfvars.json` new mandatory `var.envs[*].type` attribute
  * use env.type attribute to find internal env
* `libs/py/settings` add tests


# v0.17.0

## ⚠️ Breaking Changes:

### terrafrom.tfvars.json schema changes

* `env.cloud.registry` is moved to `env.registry` and type is changed to object
* `env.dns` new mandatory object variable
* `env.cloud.{region,default_zone,multi_region}` attributes are moved under `env.cloud.location`


Features:
* `terrafrom.tfvars.json` variables validation
* `.codex/rules/bazel.rules` codex rules that allow `bazel {build,test} *` commands

# v0.16.0

## ⚠️ Breaking Changes:

### Directory restructuring

All code under `libs/*` and `scripts/*` has been moved into the `rod/` directory.

**Why?**
When using Bazel modules, Python imports from `svetoch_bazel_lib` could conflict with local directories that have the same names (e.g., `libs/`). This leads to import resolution issues.

**Example**

Given the following `MODULE.bazel`:

```python
module(name = "some_company")

###########
# Bazel
###########
bazel_dep(name = "svetoch_bazel_lib")

git_override(
    module_name = "svetoch_bazel_lib",
    commit = "ab53043175e4e61d0f7f39b8c6295a3c5f816734",
    remote = "https://github.com/svetoch-dev/bazel-lib",
)
```

And a local library:

```
# libs/some_cool_lib
load("@aspect_rules_py//py:defs.bzl", "py_library")

py_library(
    name = "some_cool_lib",
    srcs = glob(["*.py"]),
    visibility = ["//visibility:public"],
    deps = [
        "@svetoch_bazel_lib//libs/py/settings",
    ],
)
```

Trying to import:

```
import libs.py.settings
```

will fail with a `ModuleNotFoundError`.

**Root cause**

The local `libs/` directory shadows the `libs/` directory inside `@svetoch_bazel_lib`, so Python resolves imports against the local path instead of the external module.

**Solution**

All `svetoch_bazel_lib` Python modules are now namespaced under a unique top-level directory: `rod/`.

Instead of:

```
import libs.py.settings
```

Use:

```
import rod.libs.py.settings
```

This avoids naming collisions and ensures imports from external Bazel modules work correctly.

# v0.15.0
Features:
* New tf CI variable:
  * `bazelisk_img_version` to specify `version of bazelisk image`

# v0.14.0
Features:
* `deps/images/bazelisk` add docker-credentials-gcr

# v0.13.0
Features:
* `deps/images` base/bazelisk and postgres images
* `deps/deb` deb packages needed for images

Enhancements:
* `aspect_bazel_lib` update to 2.22.5
* `rules_oci` update to 2.3.0
* `rules_distroless` update to 0.6.2
* `buildifier_prebuiltr` update to 8.5.1

# v0.12.0

Features:
* `scripts/init` enable prepare and poststeps
* `scripts/init/tf/secrets` use tfvars models to import secrets
* `scripts/init/tf/poststeps` adjust clean.py to the new rod modules
* `libs/py/tf` `import_secrets` function
* `libs/py/tf/tfvars` `env_key` function

Enhancements:
* `scripts/init/tf/apply` tests for apply function
* `scripts/init/tf/state` move `create_gcs_tf_state` `create_yc_s3_tf_state` functions to `libs/py/tf/state`
* `scripts/init/tf/apply` move `apply_env` `apply_env_targets` functions to `libs/py/tf/apply`


# v0.11.0

Features:
* `scripts/init/tf/apply` refactor code using python tfvars models
* `scripts/init/tf/prepare` copy script that copies template dir to real env dir
* `libs/py/helpers` switch_index function that switches index of an element
* `terraform/tf_variables.tf.tpl` new envs attribute - initial_start

Enhancements:
* `libs.py.tf.tfvars` formatted_tfvars tests

Fixes:
* `tools/macros/tf.bzl` use json.encode(...) generate terraform.tfvars.json for tf
* `libs/py/helpers` `run_command` fix descriptor deadlock issue when stderr buffer is used and your are waiting for stdout
* `libs/py/settings` BazelSettings tf dir vars use relative to repo root paths instead of full paths

# v0.10.0
Features:
* `scripts/init/tf/state` refactor code using python tfvars models

Enhancements:
* `scipts/init/tf/prepare` use single, global cloud object and set only needed attributes
* `libs.py.tf.tfvars` improve tests

# v0.9.0

Features:
* `scripts/init/tf/prepare` refactor code using python tfvars models
* `libs.py.utils.logger`
  * rename `_Logger` class to `BaseLogger` 
  * move common info/warning/error/debug methods to BaseLogger class
  * `propagate = False` is now false for all loggers
* `libs.py.helpers` create_dir, create_file use CliLogger for output messages instead of print 
* `libs.py.gcp` `enable_apis` function

Fixes:
* `scripts/init/images/prepare` fix bazel path for deps

# v0.8.1

Features:
* tools/macros/tf.bzl can render variable `repo.type`
* add `var.repo.name` attribute to tf_variables.tf.tpl


# v0.8.0

Features:
* `libs.py.tf.tfvars.formatted_tfvars` function that renders terraform.tfvars.json template and returns tf_variables objects based on it
* `libs.py.helpers.dict_to_dot_notation` function used in rendering process of terraform.tfvars.json
* `libs.py.helpers.replace_dotted_placeholders` function used in rendering process of terraform.tfvars.json
* `libs.py.helpers.create_dir` function
* `libs.py.helpers.create_file` function
* `scripts/init/images` scripts have there terraform.tfvars.json dependent logic moved to python instead of starlark


Enhancements:
* annotations to libs.py.helpers.run_command
* custom exceptions for black lint fix because `build` dirs are excluded by default



# v0.7.0

Features:
* use pydantic models for logging and bazel settings
* pydantic models for tfvars and parsing of terraform.tfvars.json 

Enhancements:
* pin python version for pyenv in `.python-version`
* venv to .gitignore
* move terraform.tfvars.json to root of repo
* move libs/py/utils/test_logger.py to libs/py/utils/tests.py to have the same test rules approach for all libs
* `terraform/tf_variables.tf.tpl` reconfigure defaults for `env.cloud.buckets` and `env.kubernetes`

# v0.6.0

Features:
* `terraform/tf_variables.tf.tpl`:
  * `var.env` users attribute
  * `var.env.apps` `access_roles` attr that states what roles can do 


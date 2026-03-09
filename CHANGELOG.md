# v0.10.0
Features:
* `scripts/init/tf/state` refactor code using python tfvars models

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


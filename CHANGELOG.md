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



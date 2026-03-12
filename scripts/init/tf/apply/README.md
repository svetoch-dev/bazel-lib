# 🚀 Apply Infrastructure

This process applies all Terraform states across the environments defined in `terraform.tfvars.json`.

## 🔄 Apply Order

To ensure proper dependency handling, Terraform states must be applied in the following order:

1. **Internal environment** (excluding secrets)
2. **Other environments** (e.g., `dev`, `prd`, `pre`, etc.)

## 🔒 Root module dependencies

Some resources in some root modules cant be applied because they depend on other root modules. So what we do is
1. Add logic in modules not to create them if initial_start = True
2. At the begining in terraform.tfvars.json, set initial_start = True
3. Apply everything
4. Dump a new version of terraform.tfvars.json with initial_start = False
5. Apply everything again

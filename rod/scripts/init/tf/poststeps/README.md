# Poststeps

Steps performed after tf apply

## Cleanup

Clean up and remove any unused Terraform state folders to maintain a tidy project structure.

## Update tfvars

Refresh generated values in `terraform.tfvars.json` after Terraform has run. For
Yandex Container Registry environments, this resolves the `containers` registry
and writes its `cr.yandex/<registry-id>` endpoint back to the registry URL.

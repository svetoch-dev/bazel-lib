#if you change variables set in
#this file you must also change
#them here rod/libs/py/tf/tfvars.py

locals {
  # Be carefull when changing this
  # This is rendered using bazel and
  # expand_template rule probably
  # everything will brake badly if
  # something goes wrong
  env = var.envs.{env.name}
}

variable "company" {
  description = "Company related info"
  type = object(
    {
      name   = string
      domain = string
    }
  )
}

variable "ci" {
  description = "ci related info"
  type = object(
    {
      type                 = string
      group                = string
      bazelisk_img_version = optional(string,"")
    }
  )

  validation {
    condition     = contains(["gl", "gha"], var.ci.type)
    error_message = "ci.type must be either \"gl\" or \"gha\"."
  }
}

variable "repo" {
  description = "git repository related info"
  type = object(
    {
      name  = string
      type  = string
      group = string
    }
  )

  validation {
    condition     = contains(["github", "gitlab"], var.repo.type)
    error_message = "repo.type must be either \"github\" or \"gitlab\"."
  }
}

variable "envs" {
  description = "Environments description"
  type = map(
    object(
      {
        name          = string
        short_name    = string
        type          = string
        initial_start = optional(bool, false)
        users = map(
          object(
            {
              name  = string
              roles = list(string)
            }
          )
        )
        apps       = map(
          object(
            {
              name         = string
              postgres     = optional(bool, false)
              redis        = optional(bool, false)
              rabbitmq     = optional(bool, false)
              access_roles = optional(
                object(
                  {
                    port_forward = optional(string, "dev")
                  }
                ),
                {
                  port_forward = "dev"
                }
              )
            }
          )
        )
       
        import_secrets = map(
          object(
            {
              name              = string
              k8s_enabled       = optional(bool, true)
              namespace         = optional(string)
              base64_secrets    = optional(bool, false)
              secrets_to_import = list(string)
            }
          )
        )
        registry = object(
          {
            type = string
            url  = string
          }
        )
        dns = object(
          {
            domain = string
            type   = string
          }
        )
        tf_backend = object(
          {
            type    = string
            configs = map(string)
          }
        )
        cloud = object(
          {
            name         = string
            id           = string
            folder_id    = optional(string)
            location     = object(
              {
                region       = string
                default_zone = string
                multi_region = optional(string, "")
              }
            )
            network = object(
              {
                vm_cidr          = string
                k8s_pod_cidr     = string
                k8s_service_cidr = string
              }
            )
            buckets = object(
              {
                deletion_protection = optional(bool, true)
                multi_regional      = bool
              }
            )
          }
        )
        kubernetes = object(
          {
            enabled             = bool
            regional            = optional(bool, false)
            node_locations      = optional(list(string), [])
            auth_group          = optional(string, "")
            deletion_protection = optional(bool, true)
          }
        )
      }
    )
  )

  validation {
    condition     = alltrue([for env_name, env_obj in var.envs : contains(["gcp", "yc"], env_obj.cloud.name)])
    error_message = "envs[*].cloud.name must be either \"gcp\" or \"yc\"."
  }

  validation {
    condition     = alltrue([for env_name, env_obj in var.envs : contains(["gcp", "yc"], env_obj.dns.type)])
    error_message = "envs[*].dns.type must be either \"gcp\" or \"yc\"."
  }

  validation {
    condition     = alltrue([for env_name, env_obj in var.envs : contains(["ycr", "gar"], env_obj.registry.type)])
    error_message = "envs[*].registry.type must be either \"ycr\" or \"gar\"."
  }

  validation {
    condition     = alltrue([for env_name, env_obj in var.envs : contains(["internal", "product"], env_obj.type)])
    error_message = "envs[*].type must be either \"internal\" or \"product\"."
  }

  validation {
    condition     = length([for env_name, env_obj in var.envs : env_name if env_obj.type == "internal"]) == 1
    error_message = "Exactly one envs[*].type must be \"internal\"."
  }

  validation {
    condition     = alltrue(
      concat(
        [
          for env_name, env_obj in var.envs:
          env_obj.cloud.folder_id != null && env_obj.cloud.folder_id != ""
          if env_obj.cloud.name == "yc"
        ],
        [
          for env_name, env_obj in var.envs:
          true
          if env_obj.cloud.name != "yc"
        ],
      )
    )
    error_message = "envs[*].cloud.folder_id must be set when cloud.name is \"yc\"."
  }
}

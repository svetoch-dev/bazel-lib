"""
Deploy macros
"""

load("@rules_multirun//:defs.bzl", "command")
load("@svetoch_bazel_lib//tools/utils:common.bzl", "build_envs")

def deploy(service_name, envs, type="argocd", app_name=None):
    """Macro for deploying services to specific envs

    Args:
      service_name: name of the service that is part of the app
      envs: list of strings representing short environment names (pre,prd,int,dev etc)
      type: what type of tool is used to deploy (argocd,cloudrun)
      app_name: app that needs to be updated
    """
    for env, _ in build_envs().items():
        if env in envs:
            if type == "argocd":
                command(
                    name = "deploy_" + env,
                    command = "@svetoch_bazel_lib//scripts/deploy:change_yaml",
                    data = [
                        "@svetoch_bazel_lib//tools/stamping:stamp_img",
                        #Adding this in order to include
                        #deploy_* jobs in dependency graph for service
                        #files
                        ":push_" + env,
                    ],
                    arguments = [
                        "argocd/environments/*-{}/{}/values.yaml".format(env, app_name),
                        service_name,
                        "$(rootpath @svetoch_bazel_lib//tools/stamping:stamp_img)",
                    ],
                )
            if type == "cloudrun":
                command(
                    name = "deploy_" + env,
                    command = "@svetoch_bazel_lib//scripts/deploy:cloudrun",
                    data = [
                        "@svetoch_bazel_lib//tools/stamping:stamp_img",
                        #Adding this in order to include
                        #deploy_* jobs in dependency graph for service
                        #files
                        ":push_" + env,
                    ],
                    arguments = [
                        env_dict["id"],
                        env_dict["region"],
                        service_name,
                        env_dict["registry"] + "/" + service_name,
                        "$(rootpath @svetoch_bazel_lib//tools/stamping:stamp_img)",
                    ],
                )

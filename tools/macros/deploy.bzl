"""
Deploy macros
"""

load("@rules_multirun//:defs.bzl", "command")
load("@svetoch_bazel_lib//tools/utils:common.bzl", "build_envs")

def deploy(service_name, app_name, envs):
    """Macro for deploying services to specific envs

    Args:
      service_name: name of the service that is part of the app
      app_name: app that needs to be updated
      envs: list of strings representing short environment names (pre,prd,int,dev etc)
    """
    for env, _ in build_envs().items():
        if env in envs:
            command(
                name = "deploy_" + env,
                command = "@@svetoch_bazel_lib//scripts/deploy:change_yaml",
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

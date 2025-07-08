"""Prepare steps for build images"""

load("@aspect_rules_py//py:defs.bzl", "py_binary")
load("@svetoch_bazel_lib_py_deps//:requirements.bzl", "requirement")
load("@svetoch_bazel_lib//tools/utils:format.bzl", "formatted_tfvars")
load("@svetoch_bazel_lib//tools/utils:common.bzl", "build_envs")
tfvars = formatted_tfvars()

def get_prepare_args():
    """Get prepare arguments from build_envs()

    Needed for running rules_multirun rules

    Returns:
      a list of container registries
    """
    container_registries = ""
    cloud_name = ""
    args = []

    for env_name, env_obj in tfvars["envs"].items():
        if env_name == "prd" or env_name == "production":
            cloud_name = env_obj["cloud"]["name"]

    for env_name, env_obj in build_envs().items():
        container_registries += "," + env_obj["registry"]

    args.append(
        container_registries.strip(","),
    )
    if cloud_name == "gcp":
        args.append("gcr")

    return args

def prepare():
    """Preparation steps before running images build
    """

    args = get_prepare_args()

    py_binary(
        name = "prepare",
        srcs = [
            "prepare.py",
            "config.py",
        ],
        visibility = ["//visibility:public"],
        args = args,
        deps = [
            requirement("click"),
        ],
    )

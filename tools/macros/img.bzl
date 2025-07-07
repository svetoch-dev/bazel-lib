"""
Build container images macros
"""

load("@rules_oci//oci:defs.bzl", "oci_image", "oci_load", "oci_push")
load("@svetoch_bazel_lib//tools/utils:common.bzl", "build_envs")

def img_build(
        name,
        base,
        cmd = None,
        tars = [],
        user = "1000",
        **kwargs):
    """Macro for building container images

    Args:
      name: name prefix of oci_image/oci_load targets
      cmd:  list to be used as the command & args of the container
      base: base image
      tars: list of tars to include in image
      user: control over which user the process run as
      **kwargs: other named arguments to oci_image
    """
    package_path = native.package_name()

    if not cmd:
        cmd = ["./" + name]

    oci_image(
        name = name + "_img",
        base = base,
        tars = tars,
        user = user,
        workdir = "/" + package_path,
        cmd = cmd,
        **kwargs
    )

    oci_load(
        name = name + "_docker",
        image = name + "_img",
        repo_tags = [
            name + ":latest",
        ],
    )

def img_push(
        service_name,
        image,
        envs,
        remote_tags = "@svetoch_bazel_lib//tools/stamping:stamp_img"):
    """Macro for pushing container images

    Args:
      service_name: service name
      image: name of the oci_image that needs to be pushed
      remote_tags: a text file containing tags, one per line
      envs: list of strings representing short environment names (pre,prd,int,dev etc)
    """
    for env, env_dict in build_envs().items():
        if env in envs:
            oci_push(
                name = "push_" + env,
                image = image,
                remote_tags = remote_tags,
                repository = "{}/{}".format(env_dict["registry"], service_name),
            )

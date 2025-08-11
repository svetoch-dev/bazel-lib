"""
Helm macros
"""
load("@aspect_rules_py//py:defs.bzl", "py_binary")
load("@svetoch_bazel_lib_py_deps//:requirements.bzl", "requirement")

def helm_app_init():
    """
    Init app helm charts
    """
    py_binary(
        name = "init",
        srcs = ["@svetoch_bazel_lib//scripts/helm/apps/init_services"],
        data = [
            "@helm_executable//:executable",
        ],
        env = {
            "HELM_EXECUTABLE": "$(rootpath @helm_executable//:executable)",
        },
        deps = [
            "@svetoch_bazel_lib//libs/py/helpers",
            requirement("click")
        ],
        visibility = ["//visibility:public"],
    )

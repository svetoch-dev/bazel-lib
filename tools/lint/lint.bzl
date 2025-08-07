"""
Common lint rules
"""

load("@aspect_rules_py//py:defs.bzl", "py_binary")

def global_lint_fix():
    """Fix all lint issues in repo
    """

    py_binary(
        name = "fix_lint",
        main = "fix.py",
        srcs = [
            "@svetoch_bazel_lib//tools/lint:fix_py",
        ],
        visibility = ["//visibility:public"],
        deps = [
            "@svetoch_bazel_lib//libs/py/helpers",
        ],
    )

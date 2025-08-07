"""
Common lint rules
"""

load("@aspect_rules_py//py:defs.bzl", "py_binary")

def all_lint_fix():
    """Fix all lint issues in repo
    """

    py_binary(
        name = "lint_fix_all",
        main = "fix_all.py",
        srcs = [
            "@svetoch_bazel_lib//tools/lint:fix_all",
        ],
        visibility = ["//visibility:public"],
        deps = [
            "@svetoch_bazel_lib//libs/py/helpers",
        ],
    )

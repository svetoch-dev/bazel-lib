"""
Buildifier macros
"""


load("@buildifier_prebuilt//:rules.bzl", "buildifier_test")

def bazel_lint():
    """Lint bazel files
    """
    buildifier_test(
        name = "lint",
        exclude_patterns = ["./.git/*"],
        lint_mode = "warn",
        no_sandbox = True,
        workspace = "//:MODULE.bazel",
        mode = "diff",
    )

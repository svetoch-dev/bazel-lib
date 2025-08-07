"""
Buildifier macros
"""
load("@buildifier_prebuilt//:rules.bzl", "buildifier", "buildifier_test")

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

def bazel_lint_fix():
    """Lint bazel files
    """
    buildifier(
        name = "lint_fix_bzl",
        exclude_patterns = ["./.git/*"],
        lint_mode = "fix",
        mode = "fix",
    )

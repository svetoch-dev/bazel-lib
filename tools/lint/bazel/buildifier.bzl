"""
Buildifier macros
"""

def bazel_lint(buildifier_test):
    """Lint bazel files

    Args:
        buildifier_test: The buildifier_test rule loaded from
                              the caller's context.
    """
    buildifier_test(
        name = "lint",
        exclude_patterns = ["./.git/*"],
        lint_mode = "warn",
        no_sandbox = True,
        workspace = "//:MODULE.bazel",
        mode = "diff",
    )

def bazel_lint_fix(buildifier):
    """Fix lint bazel files

    Args:
        buildifier: The buildifier rule loaded from the callers context

    """
    buildifier(
        name = "lint_fix_bzl",
        exclude_patterns = ["./.git/*"],
        lint_mode = "fix",
        mode = "fix",
    )

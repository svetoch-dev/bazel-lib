"""
Black linter macros
"""

load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_test")
load("@svetoch_bazel_lib_py_deps//:requirements.bzl", "requirement")

def py_lint():
    """
    Macro to test formatting for all *.py files of a module
    """
    py_test(
        name = "lint",
        srcs = ["@svetoch_bazel_lib//tools/lint/py:black"],
        data = native.glob(["**/*.py"]),
        args = [
            #All *.py files in WORKSPACE
            ".",
            #Only check
            "--check",
            #Exclude external dict
            #for python dependencies
            "--exclude",
            "external",
        ],
        deps = [
            requirement("black"),
        ],
    )

def py_lint_fix():
    """
    Macro to fix formatting for all *.py files of a module
    """

    py_binary(
        name = "lint_fix_py",
        srcs = ["@svetoch_bazel_lib//tools/lint/py:black"],
        main = "black.py",
        args = [
            #Fix all *.py files in WORKSPACE
            ".",
        ],
        deps = [
            requirement("black"),
        ],
    )

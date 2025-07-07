"""
module extensions
"""

load("@svetoch_bazel_lib//tools/repo_rules:load_json_file.bzl", "load_json_file")

def _impl(ctx):
    for module in ctx.modules:
        for index, tag in enumerate(module.tags.json):  # buildifier: disable=unused-variable
            load_json_file(
                name = tag.name,
                src = tag.src,
                variable_name = tag.variable_name,
            )

_load_json = tag_class(
    attrs = {
        "name": attr.string(mandatory = True),
        "src": attr.label(allow_single_file = True, mandatory = True),
        "variable_name": attr.string(mandatory = True),
    },
)

load_file = module_extension(
    implementation = _impl,
    tag_classes = {
        "json": _load_json,
    },
    os_dependent = True,
    arch_dependent = True,
)

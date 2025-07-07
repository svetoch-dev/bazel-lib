# bazel lib

Bazel libraries, macros and infrastructure scripts used in https://github.com/svetoch-dev/rod 

## How to use

Add this code to your `MODULE.bazel` file


```
bazel_dep(name = "svetoch_bazel_lib")
git_override(
    module_name = "svetoch_bazel_lib",
    commit = "...",
    remote = "https://github.com/svetoch-dev/bazel-lib",
)

....

#To use python infrastructure scripts
bazel_dep(name = "rules_python", version = "1.2.0")

python = use_extension("@rules_python//python/extensions:python.bzl", "python")
python.toolchain(
    python_version = "3.11",
)
use_repo(python, python = "python_versions")

svetoch_bazel_lib_pip = use_extension("@rules_python//python/extensions:pip.bzl", "pip")
use_repo(svetoch_bazel_lib_pip, "svetoch_bazel_lib_py_deps")

#To use tf macro


```
load_file = use_extension("@svetoch_bazel_lib//tools:extensions.bzl", "load_file")
load_file.json(
    name = "tfvars",
    src = "//:terraform/terraform.tfvars.json",
    variable_name = "tfvars",
)
use_repo(load_file, "tfvars")

override_repo(
    load_file,
    svetoch_bazel_lib_tfvars = "tfvars",
)


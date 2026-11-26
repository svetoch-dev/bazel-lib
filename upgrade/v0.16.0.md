# v0.16.0

Update `git_override` commit for `svetoch_bazel_lib` to commit that `v0.16.0` tag points to eg

```
module(name = "<module_name>")

###########
# Bazel
###########

....
bazel_dep(name = "svetoch_bazel_lib")

git_override(
    module_name = "svetoch_bazel_lib",
    commit = "<commit>",
    remote = "https://github.com/svetoch-dev/bazel-lib",
)
...
```

## Python files

Instead of:
```
import libs.py.settings
```
Use:
```
import rod.libs.py.settings
```

## BUILD.bazel

Instead of 
```
@svetoch_bazel_lib//libs/py/...
@svetoch_bazel_lib//scripts/...
```
use
```
@svetoch_bazel_lib//rod/libs/py/...
@svetoch_bazel_lib//rod/scripts/...
```

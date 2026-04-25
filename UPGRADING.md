# v0.16.0

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

# Skill: Python Layered Container Images

## Scope
Creating optimized 3-layer container images for Python services using `py_layers.bzl`.

## Key Files
- `tools/macros/py_layers.bzl` — `py_layers()` macro
- `deps/images/base/BUILD.bazel` — Base Ubuntu Noble image
- `deps/py/` — Python dependencies

## How It Works

### Three Layers
1. **interpreter** — Python runtime from `rules_python` (changes rarely)
2. **packages** — Third-party pip packages from `site-packages` (changes sometimes)
3. **app** — Application code (changes frequently)

### Layer Separation
- Uses `mtree_spec()` to generate file manifest from `py_binary` target
- `mtree_mutate()` changes file ownership to uid 1000
- Regex-based grep splits manifest into three `.spec` files:
  - Interpreter: matches `\.runfiles/.*python.*-.*` but NOT site-packages
  - Packages: matches `\.runfiles/.*/site-packages`
  - App: everything else (neither interpreter nor packages)
- Each layer is a separate `tar()` target

### Why 3 Layers?
Docker layer caching: only changed layers are pushed. Since the app changes most frequently, only the small app layer needs re-pushing on most builds.

## Steps to Create a Layered Python Image

1. Define `py_binary(name = "my_service", ...)` in your BUILD.bazel
2. Load and call `py_layers`:
   ```python
   load("@svetoch_bazel_lib//tools/macros:py_layers.bzl", "py_layers")
   load("@svetoch_bazel_lib//tools/macros:img.bzl", "img_build", "img_push")

   py_layers(name = "my_service_layers", binary = ":my_service")

   img_build(
       name = "my_service",
       base = "@svetoch_bazel_lib//deps/images/base:ubuntu_noble",
       tars = py_layers(name = "my_service_layers", binary = ":my_service"),
       cmd = ["./my_service"],
   )

   img_push(service_name = "my-service", image = ":my_service_img", envs = ["dev", "prd"])
   ```

## Customization
- `layers` parameter: subset of `["interpreter", "packages", "app"]` if not all layers needed
- `mutate_mtree` parameter: custom `mtree_mutate` rule if different ownership needed
- Default ownership: uid/gid 1000

## Regex Patterns
- `PY_INTERPRETER_REGEX = "\\.runfiles/.*python.*-.*"`
- `SITE_PACKAGES_REGEX = "\\.runfiles/.*/site-packages"`

## Commands
- `bazel build //<package>:<name>_docker` — Build layered image
- `bazel run //<package>:push_<env>` — Push to registry

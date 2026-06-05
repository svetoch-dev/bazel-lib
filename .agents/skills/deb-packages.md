# Skill: Debian Package Management for Container Images

## Scope
Managing `.deb` packages used to build container base images. Covers `deps/deb/`, the `deb_packages()` macro, and the `rules_distroless` integration.

## Key Files
- `deps/deb/noble.yaml` — Package manifest (Ubuntu Noble/24.04)
- `deps/deb/noble.lock.json` — Pinned versions lock file
- `tools/macros/deb_packages.bzl` — `deb_packages()` macro
- `deps/images/base/BUILD.bazel` — Base image using deb packages
- `deps/images/bazelisk/BUILD.bazel` — CI image extending base

## How It Works

### Package Definition (noble.yaml)
- Lists Ubuntu Noble packages to install in container images
- Format: `rules_distroless` apt manifest format
- Example packages in base image: `ncurses-base`, `bash`, `coreutils`, `dpkg`, `grep`, `apt`, `perl`, `sed`, `mawk`, `tzdata`

### Lock File (noble.lock.json)
- Pinned versions of all packages and their dependencies
- Must be regenerated after changing `noble.yaml`

### deb_packages() Macro
1. Accepts list of package labels (e.g., `@svetoch_bazel_lib_noble//bash`)
2. Formats each as `<package>/amd64`
3. Creates `dpkg_status` target from all package control files
4. Uses `flatten()` to merge all packages into single uncompressed tar
5. Compresses with `zstd --format=gzip` into `packages.tar.gz`
6. Returns label name for use in `oci_image.tars`

### Base Image Construction
1. `cacerts` — CA certificates from `ca-certificates` .deb
2. `passwd` — User entries (root, _apt, ubuntu)
3. `group` — Group entries (root, _apt, ubuntu)
4. `sh_homedir` — Symlinks (sh→bash, awk→mawk) + `/home/ubuntu/` directory
5. `packages.tar.gz` — All deb packages flattened
6. `oci_image` combines all tars with `SSL_CERT_FILE` env var

## Steps to Add a Package to Base Image

1. Edit `deps/deb/noble.yaml` — add package name
2. Run `bazel run @svetoch_bazel_lib_noble//:lock` — regenerate lock file
3. Add the package label to `PACKAGES` list in `deps/images/base/BUILD.bazel`
4. Verify: `bazel build //deps/images/base:ubuntu_noble_tarball`
5. Test locally: `bazel run //deps/images/base:ubuntu_noble_tarball && docker run --rm -it ubuntu_noble:latest`

## Steps to Create a Derived Image

1. Create new directory under `deps/images/<name>/`
2. Reference base: `base = "@svetoch_bazel_lib//deps/images/base:ubuntu_noble"`
3. Add additional tars (binaries, configs)
4. Use `img_build()` or direct `oci_image`

## Commands
- `bazel run @svetoch_bazel_lib_noble//:lock` — Regenerate deb lock file
- `bazel build //deps/images/base:ubuntu_noble` — Build base image
- `bazel run //deps/images/base:ubuntu_noble_tarball` — Load into Docker

## Conventions
- All base packages are `amd64` architecture
- Base image uses uid 1000 (ubuntu user) as default
- `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` is set in all images
- Symlinks: `/usr/bin/sh → /usr/bin/bash`, `/usr/bin/awk → /usr/bin/mawk`

# CI images

These images contain command-line tools only. CI systems provide source checkout,
credentials, workspace mounts, and registry configuration at runtime.

* ci_deploy_img contains Git, OpenSSH, curl, and yq for CI jobs that
  update deployment values. SSH credentials and trusted host keys are provided
  at runtime.

The image targets Linux AMD64 and runs as UID/GID 1000, using the existing
`debian` user and group from the base image. CI supplies the mounted workspace.

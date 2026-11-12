# CI images

`ci_deploy_img` contains Git, OpenSSH, yq, and the executable
`/usr/local/bin/ci-update-image-tag.sh`. The image targets Linux AMD64 and runs as
the `runner` user with UID/GID 1001.

CI supplies the writable workspace and SSH credentials/trusted host keys.
For custom SSH paths, provide `GIT_SSH_COMMAND`. The script does not depend on
GitHub, GitLab, or Jenkins variables.

Run `ci-update-image-tag.sh` with these environment variables:

| Variable | Meaning |
| --- | --- |
| `INFRA_REPO_URL` | Infrastructure repository clone URL. |
| `INFRA_BRANCH` | Branch to clone, rebase, and push. |
| `INFRA_WORKDIR` | Checkout directory relative to the initial working directory. |
| `VALUES_FILE` | YAML file relative to the repository root. |
| `TAG_PATH` | yq assignment path, such as `.global.image.tag`. |
| `IMAGE_TAG` | Image tag to write as a YAML string. |
| `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL` | Git commit author identity. |
| `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` | Git committer identity. |

All variables above are supplied by CI. SSH authentication is configured by the
runner. No commit is created when the values file has no changes. The script
rebases before pushing; rebase conflicts or push failures fail the job.

After changing the script, rebuild and publish the image and update the image
reference used by CI consumers.

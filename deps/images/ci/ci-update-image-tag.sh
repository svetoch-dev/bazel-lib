#!/bin/sh

set -eu
git clone --branch "$INFRA_BRANCH" --single-branch "$INFRA_REPO_URL" "$INFRA_WORKDIR"
cd "$INFRA_WORKDIR"
yq -i "$TAG_PATH = strenv(IMAGE_TAG)" "$VALUES_FILE"
git add "$VALUES_FILE"
if git diff --cached --quiet; then
  exit 0
fi
git commit -m "CI/CD: update image tag"
git pull --rebase origin "$INFRA_BRANCH"
git push origin "$INFRA_BRANCH"

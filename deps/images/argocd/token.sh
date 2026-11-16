#!/bin/bash


yc_create_token() {
    export HOME=/tmp/yc-home
    mkdir -p $HOME
    chmod 700 $HOME
    yc config profile create default
    yc config set endpoint api.cloud.yandex.net:443
    exec yc k8s create-token --format json
}

gcp_create_token() {
    exec argocd-k8s-auth gcp
}

if [[ "${CLOUD:-}" == "yc" ]]; then
    yc_create_token
fi

if [[ "${CLOUD:-}" == "gcp" ]]; then
    gcp_create_token
fi

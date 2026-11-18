#!/bin/bash


yc_create_token() {
    yc config set instance-service-account true > /dev/null
    yc config set endpoint api.cloud.yandex.net:443
    exec yc k8s create-token --format json
}

gcp_create_token() {
    exec argocd-k8s-auth gcp
}

case "${CLOUD:-}" in
    yc)
        yc_create_token
        ;;
    gcp)
        gcp_create_token
        ;;
    *)
        exit 1
        ;;
esac

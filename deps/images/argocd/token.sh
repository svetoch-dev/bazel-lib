#!/bin/bash

export HOME=/tmp/yc-home
mkdir -p $HOME
chmod 700 $HOME

yc config profile create default
yc config set endpoint api.cloud.yandex.net:443
exec yc k8s create-token --format json

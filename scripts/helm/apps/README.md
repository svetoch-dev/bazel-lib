# Helm for apps

Helper scripts related to operations with app charts 

## helm_app_init

Update dependencies of a helm chart

### Installation

Add this to your BUILD.bazel file

```
load("@svetoch_bazel_lib//scripts/helm/apps:apps.bzl", "helm_app_init")

helm_app_init()
```

### Usage

```
bazel run //scripts/helm/apps:init --  '<chart name>' --app_chart_path '<app chart path>'
```

Where
* `<chart name>` - chart name in app dir or `all`. When `all` is used all charts are being initialized
* `<app chart path>` - path to folder where charts are being stored DEFAULT:  argocd/charts/app


### Examples

```
bazel run  //scripts/helm/apps:init somechart
bazel run //scripts/helm/apps:init all
bazel run //scripts/helm/apps:init -- somechart2 --app_chart_path /some/other/path
```

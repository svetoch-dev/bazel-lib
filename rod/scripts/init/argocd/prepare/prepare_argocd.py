import os
import tempfile
import sys

from rod.libs.py.k8s.manifests import apply_manifests
from rod.libs.py.k8s.exceptions import K8sApiException
from rod.libs.py.settings import common_paths
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.helpers import run_command, CommandException

HELM_EXECUTABLE = os.environ["HELM_EXECUTABLE"]


def prepare_argocd():
    """
    Bootstrap Argo CD and its root environment applications.

    Applies Argo CD CRDs to the internal cluster, updates chart dependencies,
    and renders and applies the Argo CD and environment charts. Uses the
    configured environment values, image tag, registry, and Terraform variables.

    Raises:
        SystemExit: A Helm command fails, or applying CRDs or the Argo CD
            chart raises K8sApiException.
        K8sApiException: Applying the rendered environment chart fails.
    """
    logger = CliLogger("rod.scripts.init.argocd.prepare.prepare_argocd")
    tfvars = formatted_tfvars()
    int_env = next((e for e in tfvars.envs.values() if e.type == "internal"), None)
    argocd_crds_dir = common_paths.argocd_crds_dir + "/argocd"

    try:
        apply_manifests(int_env, dir_path=argocd_crds_dir)
    except K8sApiException as e:
        logger.error(f"Failed to apply crd manifests.{str(e)}")
        sys.exit(1)

    cloud_short_name = f"{int_env.cloud.name.value}-{int_env.short_name}"
    argocd_envs_folder = common_paths.argocd_environments_dir
    argocd_folder = common_paths.argocd_dir
    argocd_charts = common_paths.argocd_chart_dir
    with open(f"{common_paths.deps_images_dir}/argocd/image_tag.txt") as f:
        image_tag = f.readline().strip()

    # fmt: off
    helm_argocd_dependecy_update = [
       f"{HELM_EXECUTABLE}",
       "dependency", "update",
       f"{argocd_charts}/argocd/",
    ]

    helm_argocd_init_cmd = [
       f"{HELM_EXECUTABLE}",
       "template",
       f"argocd-{cloud_short_name}",
       f"{argocd_charts}/argocd/",
       "--set", "redis.enabled=false",
       "--values", f"{argocd_envs_folder}/{cloud_short_name}/argocd/values.yaml",
       "--values", f"{argocd_charts}/globals.yaml",
       "--namespace", "argocd",
       "--set", "argocd.enabled=true",
       "--set", "argocd.redis.enabled=true",
       "--set-string", "argocd.externalRedis.host=",
       "--set-string", f"argocd.global.image.repository={int_env.registry.url}/argocd",
       "--set-string", f"argocd.global.image.tag={image_tag}",
       "--set", "probes.enabled=false",
       "--set", "prometheus-rules.enabled=false",
       "--set", "global.env.name=internal",
       "--set", "global.env.short_name=int",
       "--set", f"global.env.cloud_short_name={cloud_short_name}",
       "--set-string", f"global.env.dns.domain={int_env.dns.domain.strip('.')}"
    ]

    helm_environments_init_cmd = [
       f"{HELM_EXECUTABLE}",
       "template",
       "root",
       f"{argocd_charts}/environments/",
       "--values", f"{argocd_folder}/envs.yaml",
       "--values", f"{argocd_charts}/globals.yaml",
       "--set-file", f"tfvars={common_paths.tfvars_file}",
       "--namespace", "argocd",
    ]
    # fmt: on
    try:
        _, _, out = run_command(
            helm_argocd_dependecy_update, print_stdout=False, raise_exception=True
        )
        _, _, out = run_command(
            helm_argocd_init_cmd, print_stdout=False, raise_exception=True
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
            f.write("\n".join(out))
            f.flush()
            apply_manifests(int_env, file_path=f.name)

    except CommandException as e:
        logger.error(f"helm argocd init failed.{str(e)}")
        sys.exit(1)
    except K8sApiException as e:
        logger.error(f"Failed to apply helm manifests.{str(e)}")
        sys.exit(1)

    try:
        _, _, out = run_command(
            helm_environments_init_cmd, print_stdout=False, raise_exception=True
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
            f.write("\n".join(out))
            f.flush()
            apply_manifests(int_env, file_path=f.name)
    except CommandException as e:
        logger.error(f"helm environments init failed.{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    prepare_argocd()

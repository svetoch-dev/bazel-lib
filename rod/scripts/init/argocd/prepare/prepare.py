import os

from rod.libs.py.k8s.manifests import apply_manifests
from rod.libs.py.settings import bazel_settings
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.helpers import run_command, CommandException

HELM_EXECUTABLE = os.environ["HELM_EXECUTABLE"]


def prepare_argocd():
    logger = CliLogger("rod.scripts.init.argocd.prepare.prepare_argocd")
    tfvars = formatted_tfvars()
    int_env = next((e for e in tfvars.envs.values() if e.type == "internal"), None)
    argocd_crds_dir = bazel_settings.argocd_crds_dir + "/argocd"

    # try:
    #     apply_manifests(int_env, dir_path=argocd_crds_dir)
    # except Exception as e:
    #     logger.error(f"Failed to apply crd manifests.{str(e)}")
    #     return

    cloud_short_name = f"{int_env.cloud.name.value}-{int_env.short_name}"
    argocd_folder = bazel_settings.argocd_dir
    argocd_charts = bazel_settings.argocd_chart_dir
    with open(f"{bazel_settings.deps_images_dir}/argocd/image_tag.txt") as f:
        image_tag = f.readline().strip()

    # fmt: off
    helm_argocd_init_cmd = [
       f"{HELM_EXECUTABLE}",
       "template",
       f"argocd-{cloud_short_name}",
       f"{argocd_charts}/argocd/",
       "--set", "redis.enabled=false",
       "--values", f"{argocd_folder}/environments/{cloud_short_name}/argocd/values.yaml",
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
       "--set-string", f"global.env.dns.domain={int_env.dns.domain}"
    ]
    # fmt: on
    try:
        _, _, out = run_command(
            helm_argocd_init_cmd, print_stdout=False, raise_exception=True
        )
        print(out)
    except CommandException as e:
        logger.error(f"helm argocd init failed.{str(e)}")


if __name__ == "__main__":
    prepare_argocd()

# from rod.libs.py.settings import bazel_settings
from rod.libs.py.k8s.client import kube_config_factory, k8s_client_get
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.utils.logger import CliLogger


def update_kube_config() -> bool:
    logger = CliLogger("rod.libs.py.tf.poststeps.update_kube_config")
    tfvars = formatted_tfvars()

    logger.info("Adding kuberenetes clusters to ~/.kube/config")
    for env_obj in tfvars.envs.values():
        config = kube_config_factory(
            env_obj, company_name=tfvars.company.name, use_exec=True
        )
        print(config.model_dump_json(indent=2))

    return True


if __name__ == "__main__":
    update_kube_config()

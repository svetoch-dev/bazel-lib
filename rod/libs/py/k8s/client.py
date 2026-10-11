from kubernetes import client

from rod.libs.py.tf.tfvars import Env, CloudTypeEnum


class K8sClient:
    def __init__(self, v1: client.CoreV1Api, custom: client.CustomObjectsApi):
        self.v1 = v1
        self.custom = custom

    def __getattr__(self, name):
        for obj in (self.v1, self.custom):
            try:
                return getattr(obj, name)
            except AttributeError:
                pass

        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


# def k8s_client(env: Env) -> K8sClient:
#    client.CoreV1Api()
#    return K8sClient()


def k8s_config_factory(env: Env, use_cli: bool = False) -> client.Configuration:
    if env.cloud.name == CloudTypeEnum.gcp:
        pass
    return client.Configuration()

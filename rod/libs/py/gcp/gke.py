from google.cloud import container_v1

from rod.libs.py.settings import K8sClusterSettings


def gke_cluster_settings(
    project_id: str,
    location: str,
    cluster_name: str,
) -> K8sClusterSettings:
    client = container_v1.ClusterManagerClient()

    cluster = client.get_cluster(
        name=f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
    )

    settings = K8sClusterSettings(
        endpoint=f"https://{cluster.endpoint}",
        ca_cert=cluster.master_auth.cluster_ca_certificate,
    )

    return settings

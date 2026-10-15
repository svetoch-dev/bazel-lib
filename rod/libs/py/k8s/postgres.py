from kubernetes import client

from rod.libs.py.k8s.api import KubernetesApi


POSTGRES_GROUP = "acid.zalan.do"
POSTGRES_VERSION = "v1"
POSTGRES_PLURAL = "postgresqls"


class KubernetesPostgresApi(KubernetesApi):
    """Kubernetes operations for PostgreSQL custom resources and PVCs."""

    def list_postgresql_clusters(self, namespace: str | None) -> list[dict]:
        if namespace:
            result = self.api.list_namespaced_custom_object(
                POSTGRES_GROUP, POSTGRES_VERSION, namespace, POSTGRES_PLURAL
            )
        else:
            result = self.api.list_cluster_custom_object(
                POSTGRES_GROUP, POSTGRES_VERSION, POSTGRES_PLURAL
            )
        return result["items"]

    def get_postgresql(self, namespace: str, name: str) -> dict:
        return self.api.get_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            name,
        )

    def create_postgresql(self, namespace: str, resource: dict) -> None:
        self.api.create_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            resource,
        )

    def delete_postgresqls(self, namespace: str, selector: str) -> None:
        self.api.delete_collection_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            label_selector=selector,
        )

    def delete_persistentvolumeclaims(self, namespace: str, selector: str) -> None:
        self.api.delete_collection_namespaced_persistent_volume_claim(
            namespace,
            label_selector=selector,
            body=client.V1DeleteOptions(),
        )

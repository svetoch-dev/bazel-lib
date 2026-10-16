from rod.libs.py.k8s.api import KubernetesApi


POSTGRES_GROUP = "acid.zalan.do"
POSTGRES_VERSION = "v1"
POSTGRES_PLURAL = "postgresqls"


class KubernetesPostgresApi(KubernetesApi):
    """Kubernetes operations for PostgreSQL custom resources."""

    def list_postgresql_clusters(self, namespace: str | None) -> list[dict]:
        """List PostgreSQL custom resources.

        Args:
            namespace: Namespace to search, or None to search all namespaces.

        Returns:
            PostgreSQL resource dictionaries.
        """
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
        """Read a PostgreSQL custom resource by its exact name.

        Args:
            namespace: Namespace containing the resource.
            name: PostgreSQL resource name.

        Returns:
            PostgreSQL resource dictionary.
        """
        return self.api.get_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            name,
        )

    def create_postgresql(self, namespace: str, resource: dict) -> None:
        """Create a PostgreSQL custom resource.

        Args:
            namespace: Namespace where the resource is created.
            resource: PostgreSQL resource manifest.
        """
        self.api.create_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            resource,
        )

    def delete_postgresqls(self, namespace: str, selector: str) -> None:
        """Request deletion of PostgreSQL resources matching a label selector.

        Args:
            namespace: Namespace containing the resources.
            selector: Kubernetes label selector identifying resources to delete.
        """
        self.api.delete_collection_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            label_selector=selector,
        )

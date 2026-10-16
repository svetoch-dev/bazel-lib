class K8sClusterNotFound(Exception):
    """The requested Kubernetes cluster does not exist."""


class K8sClusterPermissionsDenied(Exception):
    """The caller does not have permissions on requested Kubernetes cluster."""


class K8sApiException(Exception):
    """
    Indicate that one or more Kubernetes manifest operations failed.
    """

    def __init__(self, errors: list[Exception] | Exception):
        self.errors = errors if isinstance(errors, list) else [errors]
        super().__init__(self.errors)

    def __str__(self):
        return "\n".join(str(error) for error in self.errors)

class K8sClusterNotFound(Exception):
    """The requested Kubernetes cluster does not exist."""


class K8sClusterPermissionsDenied(Exception):
    """The caller does not have permissions on requested Kubernetes cluster."""


class K8sApiException(Exception):
    """Api exception"""

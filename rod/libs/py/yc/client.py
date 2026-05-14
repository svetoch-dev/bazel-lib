import os

import requests
from yandexcloud import SDK


class AuthError(Exception):
    """Raised when no Yandex Cloud authentication method is available."""

    pass


class YcSettings:
    """Authentication settings discovered from the local environment."""

    @property
    def token(self) -> str | None:
        """Return an IAM token from YC_TOKEN or instance metadata."""
        token = os.getenv("YC_TOKEN", None)
        if token:
            return token

        if self.metadata_available():
            return self.metadata_token

        return None

    @property
    def metadata(self) -> str:
        """Metadata endpoint used to request instance service account tokens."""
        m_address = os.getenv("YC_METADATA_ADDR", "169.254.169.254")
        return f"http://{m_address}/computeMetadata/v1/instance/service-accounts/default/token"

    def metadata_available(self, timeout: float = 1) -> bool:
        """Return True when the default instance service account token is reachable."""
        try:
            r = requests.get(
                self.metadata,
                headers={"Metadata-Flavor": "Google"},
                timeout=(timeout, timeout),
            )
            # 200 means metadata exists and a service account token is available.
            # 403/404 may mean metadata is reachable but no/default SA token is unavailable.
            return r.status_code == 200
        except requests.RequestException:
            return False

    @property
    def metadata_token(self) -> str:
        """Fetch an IAM token from the instance metadata endpoint."""
        response = requests.get(
            self.metadata,
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        response.raise_for_status()
        return response.json()["access_token"]


def sdk_get(token: str = None) -> SDK:
    """Create a Yandex Cloud SDK with the first available auth method.

    Authentication is selected in this order: explicit IAM token, ``YC_TOKEN``
    from the environment, then an IAM token fetched from the default instance
    service account metadata endpoint.

    Args:
        token: Optional IAM token that takes precedence over environment auth.

    Returns:
        An authenticated Yandex Cloud SDK instance.

    Raises:
        AuthError: No explicit token, environment token, or metadata token is available.
    """
    settings = YcSettings()
    if token:
        return SDK(iam_token=token)
    settings_token = settings.token
    if settings_token:
        return SDK(iam_token=settings_token)

    raise AuthError("no auth methods found")

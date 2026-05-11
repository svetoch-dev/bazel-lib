import os
from dataclasses import dataclass
from typing import Optional

import requests
from yandexcloud import SDK


class AuthError(Exception):
    """Raised when no Yandex Cloud authentication method is available."""

    pass


@dataclass
class YcSettings:
    """Authentication settings discovered from the local environment."""

    token: Optional[str] = None

    def __post_init__(self):
        if self.token is None:
            self.token = os.getenv("YC_TOKEN")

    @property
    def metadata(self):
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


def sdk_get(token: str = None) -> SDK:
    """Create a Yandex Cloud SDK with the first available auth method.

    Authentication is selected in this order: explicit IAM token, ``YC_TOKEN``
    from the environment, then the default instance service account exposed
    through the metadata endpoint.

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
    if settings.token:
        return SDK(iam_token=settings.token)
    if settings.metadata_available():
        return SDK()

    raise AuthError("no auth methods found")

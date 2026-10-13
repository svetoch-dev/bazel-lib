import google.auth
import requests

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request


def get_creds() -> Credentials:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    credentials.refresh(Request())
    return credentials


def get_caller_email(credentials: Credentials) -> str:
    if not credentials.valid:
        credentials.refresh(Request())

    response = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"access_token": credentials.token},
        timeout=10,
    )
    response.raise_for_status()

    token_info = response.json()

    email = token_info.get("email")
    if not email:
        raise ValueError("Token does not expose caller email")

    return email

import google.auth

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request


def get_creds() -> Credentials:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    credentials.refresh(Request())
    return credentials

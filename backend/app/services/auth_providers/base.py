"""Provider-neutral principal and protocol for external auth providers."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class ExternalPrincipal:
    """A user as described by an external provider, normalized across vendors.

    ``subject`` is the stable provider id (Keycloak ``sub`` UUID, AD objectGUID)
    used as ``UserIdentity.provider_subject`` — never the username, which can
    change.  ``provider_refresh_token`` is set only by OIDC providers that
    support silent renewal.
    """

    provider: str
    subject: str
    username: str
    name: str | None = None
    email: str | None = None
    provider_refresh_token: str | None = None


class AuthProvider(Protocol):
    """Marker protocol implemented by every external provider."""

    name: str

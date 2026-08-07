"""External authentication providers (optional, additive).

Each provider authenticates a user on Releasewatch's behalf and returns a
normalized :class:`ExternalPrincipal`.  The rest of the app never sees a
provider token — after authentication, Releasewatch mints its own JWT.
"""

from app.services.auth_providers.base import AuthProvider, ExternalPrincipal
from app.services.auth_providers.ldap import LdapProvider, LdapUnavailable
from app.services.auth_providers.oidc import KeycloakOIDCProvider

__all__ = [
    "AuthProvider",
    "ExternalPrincipal",
    "KeycloakOIDCProvider",
    "LdapProvider",
    "LdapUnavailable",
]

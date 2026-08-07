"""Direct LDAP / Active Directory authentication provider.

``ldap3`` is synchronous — call :meth:`LdapProvider.authenticate` via
``starlette.concurrency.run_in_threadpool`` so it never blocks the event loop.

Two failure modes are deliberately distinguished (see the login flow, D5):

* **Bind rejected** (wrong password / user absent) → returns ``None`` so the
  caller can fall through to local password auth.
* **Server unavailable** (socket/TLS error) → raises :class:`LdapUnavailable`
  so the caller can *also* fall through to local — a directory outage must
  never lock out local admins.
"""

import logging
import uuid

from app.config import settings
from app.services.auth_providers.base import ExternalPrincipal

logger = logging.getLogger(__name__)


class LdapUnavailable(Exception):
    """Raised when the LDAP server cannot be reached (as opposed to bad creds)."""


class LdapProvider:
    """Authenticates a username/password against LDAP/AD via a bind."""

    name = "ldap"

    def authenticate(self, username: str, password: str) -> ExternalPrincipal | None:
        """Return an :class:`ExternalPrincipal` on success, ``None`` on bad creds.

        Raises :class:`LdapUnavailable` if the directory is unreachable.
        """
        # Imported lazily so the dependency is only required when LDAP is enabled.
        from ldap3 import ALL, Connection, Server
        from ldap3.core.exceptions import (
            LDAPBindError,
            LDAPException,
            LDAPSocketOpenError,
        )
        from ldap3.utils.conv import escape_filter_chars

        if not password:
            # An empty password can yield an "unauthenticated bind" that AD may
            # accept as anonymous — treat as a rejected credential.
            return None

        use_ssl = settings.LDAP_SERVER_URI.lower().startswith("ldaps://") or settings.LDAP_USE_TLS

        try:
            server = Server(settings.LDAP_SERVER_URI, use_ssl=use_ssl, get_info=ALL)

            if settings.LDAP_BIND_DN_TEMPLATE:
                # Direct bind: bind as the user themselves.
                user_dn = settings.LDAP_BIND_DN_TEMPLATE.format(username=username)
                try:
                    conn = Connection(server, user=user_dn, password=password, auto_bind=True)
                except LDAPBindError:
                    return None  # bad credentials
            else:
                # Search-then-bind: service account finds the user, then rebind.
                try:
                    svc = Connection(
                        server,
                        user=settings.LDAP_SERVICE_BIND_DN,
                        password=settings.LDAP_SERVICE_PASSWORD,
                        auto_bind=True,
                    )
                except LDAPBindError as exc:  # service account misconfigured
                    logger.error("LDAP service bind failed: %s", exc)
                    raise LdapUnavailable("LDAP service bind failed") from exc

                flt = settings.LDAP_USER_FILTER.format(username=escape_filter_chars(username))
                svc.search(
                    settings.LDAP_USER_BASE_DN,
                    flt,
                    attributes=[settings.LDAP_ATTR_NAME, settings.LDAP_ATTR_EMAIL, "objectGUID"],
                )
                if not svc.entries:
                    return None  # user not found
                user_dn = svc.entries[0].entry_dn
                try:
                    conn = Connection(server, user=user_dn, password=password, auto_bind=True)
                except LDAPBindError:
                    return None  # bad credentials

            # Bound successfully — read attributes for provisioning.
            name, email, subject = self._read_attributes(conn, user_dn, username, escape_filter_chars)
            conn.unbind()
            return ExternalPrincipal(
                provider=self.name,
                subject=subject,
                username=username,
                name=name,
                email=email,
            )

        except LDAPSocketOpenError as exc:
            logger.warning("LDAP server unreachable: %s", exc)
            raise LdapUnavailable(str(exc)) from exc
        except LdapUnavailable:
            raise
        except LDAPException as exc:  # any other protocol-level failure
            logger.warning("LDAP error during authentication: %s", exc)
            raise LdapUnavailable(str(exc)) from exc

    def _read_attributes(self, conn, user_dn, username, escape_filter_chars):
        """Best-effort read of display name, email, and a stable subject id."""
        name = None
        email = None
        subject = None
        try:
            base = settings.LDAP_USER_BASE_DN or user_dn
            scope_filter = (
                settings.LDAP_USER_FILTER.format(username=escape_filter_chars(username))
                if settings.LDAP_USER_BASE_DN
                else "(objectClass=*)"
            )
            conn.search(
                base,
                scope_filter,
                attributes=[settings.LDAP_ATTR_NAME, settings.LDAP_ATTR_EMAIL, "objectGUID"],
            )
            if conn.entries:
                entry = conn.entries[0]
                name = self._attr(entry, settings.LDAP_ATTR_NAME)
                email = self._attr(entry, settings.LDAP_ATTR_EMAIL)
                guid = self._attr(entry, "objectGUID")
                subject = str(guid) if guid else None
        except Exception as exc:  # attribute read is non-fatal — auth already succeeded
            logger.debug("LDAP attribute read failed (non-fatal): %s", exc)

        # Stable subject: objectGUID if available, else a deterministic UUID from
        # the bind DN so the same directory user always maps to the same identity.
        if not subject:
            subject = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_dn.lower()))
        return name, email, subject

    @staticmethod
    def _attr(entry, attr_name):
        try:
            value = entry[attr_name].value
            return value if value else None
        except (KeyError, IndexError):
            return None

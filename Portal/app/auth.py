"""
Autenticação no LDAP / Active Directory.

Fluxo: (1) acha o DN do usuário pelo filtro LDAP_USER_FILTER, (2) faz bind com o DN
e a senha digitada para validar, (3) busca os grupos dele com LDAP_GROUP_FILTER.

Variáveis de ambiente (exemplos para o OpenLDAP do lab; AD corporativo no README):
  LDAP_URL          ldap://ipa-ldap.lab.local   (ldaps://... para TLS)
  LDAP_START_TLS    "true" para STARTTLS em ldap://  (padrão false)
  LDAP_VERIFY_TLS   "false" para aceitar certificado autoassinado (padrão true)
  LDAP_BIND_DN      conta de serviço para as buscas (vazio = bind anônimo)
  LDAP_BIND_PASSWORD
  LDAP_USER_BASE    ou=People,dc=ipa,dc=local
  LDAP_USER_FILTER  (uid={username})            AD: (sAMAccountName={username})
  LDAP_GROUP_BASE   ou=Groups,dc=ipa,dc=local
  LDAP_GROUP_FILTER (|(memberUid={username})(member={user_dn})(uniqueMember={user_dn}))
  LDAP_GROUP_ATTR   cn
  LDAP_NAME_ATTR    atributo com o nome de exibição (padrão cn; AD: displayName)
"""

import os
import ssl

from ldap3 import NONE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError, LDAPException, LDAPInvalidCredentialsResult
from ldap3.utils.conv import escape_filter_chars

LDAP_URL = os.environ.get("LDAP_URL", "")
START_TLS = os.environ.get("LDAP_START_TLS", "false").lower() in ("true", "1", "yes")
VERIFY_TLS = os.environ.get("LDAP_VERIFY_TLS", "true").lower() not in ("false", "0", "no")
BIND_DN = os.environ.get("LDAP_BIND_DN", "")
BIND_PASSWORD = os.environ.get("LDAP_BIND_PASSWORD", "")
USER_BASE = os.environ.get("LDAP_USER_BASE", "")
USER_FILTER = os.environ.get("LDAP_USER_FILTER", "(uid={username})")
GROUP_BASE = os.environ.get("LDAP_GROUP_BASE", "")
GROUP_FILTER = os.environ.get(
    "LDAP_GROUP_FILTER", "(|(memberUid={username})(member={user_dn})(uniqueMember={user_dn}))"
)
GROUP_ATTR = os.environ.get("LDAP_GROUP_ATTR", "cn")
NAME_ATTR = os.environ.get("LDAP_NAME_ATTR", "cn")


class AuthError(Exception):
    """Falha de login que pode ser mostrada ao usuário."""


def _server() -> Server:
    tls = Tls(validate=ssl.CERT_REQUIRED if VERIFY_TLS else ssl.CERT_NONE)
    return Server(LDAP_URL, use_ssl=LDAP_URL.startswith("ldaps://"), tls=tls, get_info=NONE, connect_timeout=5)


def _connect(user: str | None, password: str | None) -> Connection:
    conn = Connection(_server(), user=user, password=password, receive_timeout=10, raise_exceptions=True)
    conn.open()
    if START_TLS:
        conn.start_tls()
    conn.bind()
    return conn


def _first(entry, attr):
    v = entry["attributes"].get(attr)
    if isinstance(v, list):
        return v[0] if v else None
    return v


def authenticate(username: str, password: str) -> dict:
    """Valida usuário e senha no LDAP e devolve {username, name, groups}."""
    if not LDAP_URL or not USER_BASE:
        raise AuthError("Login não configurado: defina LDAP_URL e LDAP_USER_BASE.")
    username = (username or "").strip()
    # Senha vazia faria um "bind anônimo" com sucesso em muitos servidores: recusar sempre.
    if not username or not password:
        raise AuthError("Informe usuário e senha.")

    try:
        # 1. Achar o DN do usuário
        svc = _connect(BIND_DN or None, BIND_PASSWORD or None)
        svc.search(
            USER_BASE,
            USER_FILTER.format(username=escape_filter_chars(username)),
            attributes=[NAME_ATTR],
            size_limit=2,
        )
        entries = [e for e in svc.response if e.get("type") == "searchResEntry"]
        if len(entries) != 1:
            raise AuthError("Usuário ou senha inválidos.")
        user_dn = entries[0]["dn"]
        name = _first(entries[0], NAME_ATTR) or username

        # 2. Validar a senha com o próprio DN
        try:
            _connect(user_dn, password).unbind()
        except (LDAPBindError, LDAPInvalidCredentialsResult):
            raise AuthError("Usuário ou senha inválidos.")

        # 3. Grupos
        groups = []
        if GROUP_BASE:
            svc.search(
                GROUP_BASE,
                GROUP_FILTER.format(username=escape_filter_chars(username), user_dn=escape_filter_chars(user_dn)),
                attributes=[GROUP_ATTR],
            )
            groups = sorted({
                str(_first(e, GROUP_ATTR)) for e in svc.response
                if e.get("type") == "searchResEntry" and _first(e, GROUP_ATTR)
            })
        svc.unbind()
    except AuthError:
        raise
    except LDAPException as e:
        raise AuthError(f"Não foi possível consultar o LDAP: {e.__class__.__name__}")

    return {"username": username, "name": str(name), "groups": groups}

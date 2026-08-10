"""Verify that the two Keycloak realms (travel-customers, travel-admin) are
configured the way infra/keycloak/realms/*.json says they should be, against
a live Keycloak instance. See docs/decisions/0004-identity-two-realms.md.

Usage:
    uv run python tools/verify_auth.py

For each realm this checks: the OIDC discovery document is reachable; each
seed user can get a token via password grant (through verifier-cli, the
client that exists only for this -- see the ADR for why the real front-end
clients never get directAccessGrantsEnabled); the token's signature verifies
against the realm's own JWKS; its `iss` and `aud` claims and its realm role
are what's expected.

It then proves realm separation is real, not decorative, with two
independent assertions on a travel-customers token:
- its `kid` (key ID) is absent from travel-admin's JWKS -- not just "some
  verification exception was raised", which would also be true for a typo'd
  URL or a network blip. Absence of the specific key ID is the actual claim
  being tested.
- its `iss` claim names the customers realm, not the admin realm.

Compact PASS/FAIL output, one line per check. Exit 0 if everything passed,
1 otherwise.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")

# Dev-only seed credential shared by every seed user across both realms,
# matching infra/keycloak/realms/*.json and documented in README.md as such.
# Intentionally not a secret: it's meant to be visible, not hidden.
SEED_PASSWORD = "DevPassword123!"


@dataclass(frozen=True)
class SeedUser:
    username: str
    role: str


@dataclass(frozen=True)
class RealmConfig:
    name: str
    verifier_client: str
    api_client: str
    users: tuple[SeedUser, ...]


REALMS = (
    RealmConfig(
        name="travel-customers",
        verifier_client="verifier-cli",
        api_client="orchestrator-api",
        users=(
            SeedUser("customer.one", "customer"),
            SeedUser("customer.two", "customer"),
        ),
    ),
    RealmConfig(
        name="travel-admin",
        verifier_client="verifier-cli",
        api_client="admin-api",
        users=(
            SeedUser("admin.one", "admin"),
            SeedUser("agent.one", "agent"),
        ),
    ),
)


@dataclass
class CheckReport:
    ok: bool
    label: str
    detail: str = ""

    def line(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        suffix = f" -- {self.detail}" if self.detail else ""
        return f"[{status}] {self.label}{suffix}"


def http_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def http_post_form(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=10) as resp:
        return json.loads(resp.read())


def fetch_discovery(realm: str) -> dict:
    url = f"{KEYCLOAK_URL}/realms/{realm}/.well-known/openid-configuration"
    doc = http_get_json(url)
    # KeyError here is the point: a discovery doc missing these means the
    # realm isn't really up, even if the HTTP request itself succeeded.
    doc["token_endpoint"]
    doc["jwks_uri"]
    return doc


def password_grant(token_endpoint: str, client_id: str, username: str, password: str) -> str:
    response = http_post_form(
        token_endpoint,
        {
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password,
        },
    )
    return response["access_token"]


def verify_signature(token: str, jwks_uri: str) -> dict:
    """Verify the token's signature against jwks_uri and return its claims.

    verify_aud is explicitly disabled here on purpose: if PyJWT validated
    audience as part of decode, a missing/wrong `aud` (e.g. the audience
    mapper isn't wired up) would surface as the same generic decode
    exception as an actually-invalid signature. Those are different bugs and
    the caller asserts `aud` itself, against the already-verified claims, so
    the two failure modes stay distinguishable.
    """
    signing_key = PyJWKClient(jwks_uri).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )


def check_realm(realm: RealmConfig, reports: list[CheckReport]) -> tuple[dict, str] | None:
    """Run all per-realm checks. Returns (discovery, first seed user's raw
    token) for use in the cross-realm check, or None if the realm couldn't
    be reached at all."""
    try:
        discovery = fetch_discovery(realm.name)
        reports.append(CheckReport(True, f"{realm.name}: discovery document reachable"))
    except (OSError, urllib.error.URLError, KeyError) as exc:
        reports.append(CheckReport(False, f"{realm.name}: discovery document reachable", str(exc)))
        return None

    expected_issuer = f"{KEYCLOAK_URL}/realms/{realm.name}"
    first_token: str | None = None

    for index, user in enumerate(realm.users):
        label = f"{realm.name}/{user.username}"
        try:
            token = password_grant(
                discovery["token_endpoint"], realm.verifier_client, user.username, SEED_PASSWORD
            )
            claims = verify_signature(token, discovery["jwks_uri"])
        except (OSError, urllib.error.URLError, jwt.PyJWTError, KeyError) as exc:
            reports.append(
                CheckReport(False, f"{label}: token obtained and signature verifies", str(exc))
            )
            continue

        reports.append(CheckReport(True, f"{label}: token obtained and signature verifies"))

        iss = claims.get("iss")
        reports.append(
            CheckReport(iss == expected_issuer, f"{label}: iss == {expected_issuer}", str(iss))
        )

        aud = claims.get("aud")
        aud_list = aud if isinstance(aud, list) else [aud] if aud else []
        reports.append(
            CheckReport(
                realm.api_client in aud_list, f"{label}: aud contains {realm.api_client}", str(aud)
            )
        )

        roles = claims.get("realm_access", {}).get("roles", [])
        reports.append(
            CheckReport(user.role in roles, f"{label}: has role '{user.role}'", str(roles))
        )

        if index == 0:
            first_token = token

    if first_token is None:
        return None
    return discovery, first_token


def check_cross_realm_separation(
    customer_discovery: dict, customer_token: str, admin_discovery: dict, reports: list[CheckReport]
) -> None:
    kid = jwt.get_unverified_header(customer_token)["kid"]
    try:
        admin_jwks = http_get_json(admin_discovery["jwks_uri"])
        admin_kids = {key["kid"] for key in admin_jwks.get("keys", [])}
        reports.append(
            CheckReport(
                kid not in admin_kids,
                "cross-realm: travel-customers token's kid is absent from travel-admin's JWKS",
                f"kid={kid}, travel-admin kids={sorted(admin_kids)}",
            )
        )
    except (OSError, urllib.error.URLError) as exc:
        reports.append(
            CheckReport(
                False,
                "cross-realm: travel-customers token's kid is absent from travel-admin's JWKS",
                str(exc),
            )
        )

    claims = jwt.decode(customer_token, options={"verify_signature": False})
    customer_issuer = f"{KEYCLOAK_URL}/realms/travel-customers"
    admin_issuer = f"{KEYCLOAK_URL}/realms/travel-admin"
    iss = claims.get("iss")
    reports.append(
        CheckReport(
            iss == customer_issuer and iss != admin_issuer,
            f"cross-realm: travel-customers token's iss is {customer_issuer}, not {admin_issuer}",
            str(iss),
        )
    )


def main() -> int:
    reports: list[CheckReport] = []
    results: dict[str, tuple[dict, str]] = {}

    for realm in REALMS:
        result = check_realm(realm, reports)
        if result is not None:
            results[realm.name] = result

    if "travel-customers" in results and "travel-admin" in results:
        customer_discovery, customer_token = results["travel-customers"]
        admin_discovery, _ = results["travel-admin"]
        check_cross_realm_separation(customer_discovery, customer_token, admin_discovery, reports)
    else:
        reports.append(
            CheckReport(
                False,
                "cross-realm negative assertion",
                "skipped, a realm above failed to produce a token",
            )
        )

    for report in reports:
        print(report.line())

    ok = all(report.ok for report in reports)
    print("RESULT: PASS" if ok else "RESULT: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

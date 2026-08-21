import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import encode as jwt_encode
from jwt.algorithms import RSAAlgorithm

from orchestrator.config import get_settings
from orchestrator.main import app

REQUIRED_ENV = {
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "KEYCLOAK_URL": "http://localhost:8080",
}


@pytest.fixture
def isolated_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Chdir to an empty tmp_path so config.py's relative env_file=".env"
    never picks up the real repo .env, and clear the get_settings cache
    around the test."""
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings_env(isolated_cwd: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield


@pytest.fixture
def client(settings_env: None) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def signed_token(rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]):
    """Factory fixture: signed_token(iss=..., aud=..., exp_delta=..., kid=...)
    returns a signed RS256 JWT string for use against auth/jwt.py's
    verify_access_token (Piece D), once the user implements it."""
    private_key, _ = rsa_keypair

    def _make(
        *,
        iss: str = "http://localhost:8080/realms/travel-customers",
        aud: str | list[str] = "orchestrator-api",
        exp_delta: int = 300,
        kid: str = "test-kid",
        **extra_claims: object,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": iss,
            "aud": aud,
            "iat": now,
            "exp": now + exp_delta,
            "sub": "test-user",
            **extra_claims,
        }
        return jwt_encode(claims, private_key, algorithm="RS256", headers={"kid": kid})

    return _make


@pytest.fixture
def jwks_payload(rsa_keypair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]):
    """Factory fixture: jwks_payload(kid=...) returns a JWKS dict
    (matching what Keycloak's jwks_uri would serve) whose public key
    matches signed_token's signing key."""
    _, public_key = rsa_keypair

    def _make(kid: str = "test-kid") -> dict:
        jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
        jwk["kid"] = kid
        jwk["use"] = "sig"
        jwk["alg"] = "RS256"
        return {"keys": [jwk]}

    return _make

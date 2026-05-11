"""
SD-JWT VC builder for EU PID (eu.europa.ec.eudi.pid.1).

Implements RFC draft-ietf-oauth-sd-jwt-vc and the EUDI ARF v1.4 PID rulebook.
The resulting token is: <JWT>~<disclosure_1>~<disclosure_2>~...~
"""
import json
import base64
import hashlib
import secrets
import time
from datetime import date, datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _sign_es256(header: dict, payload: dict, private_key) -> str:
    """Sign a JWT with ES256, returning the compact serialization."""
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()

    der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    # JWS uses raw 64-byte (r||s), not DER
    raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{h}.{p}.{_b64url(raw_sig)}"


def _make_disclosure(claim_name: str, claim_value) -> tuple[str, str]:
    """
    Build one SD-JWT disclosure.
    Returns (disclosure_b64url, sha256_digest_b64url).
    """
    salt = secrets.token_urlsafe(16)
    raw = json.dumps([salt, claim_name, claim_value], separators=(",", ":"))
    d_b64 = _b64url(raw.encode())
    digest = _b64url(hashlib.sha256(d_b64.encode()).digest())
    return d_b64, digest


def public_key_to_jwk(private_key, kid: str = "key-1") -> dict:
    pub = private_key.public_key()
    nums = pub.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "kid": kid,
        "use": "sig",
        "alg": "ES256",
        "x": _b64url(nums.x.to_bytes(32, "big")),
        "y": _b64url(nums.y.to_bytes(32, "big")),
    }


# Claims that are selectively disclosed (hidden by default, wallet reveals on request)
_SD_CLAIMS = [
    "given_name",
    "family_name",
    "birth_date",
    "age_over_18",
    "age_in_years",
    "age_birth_year",
    "gender",
    "nationality",
    "birth_country",
    "birth_city",
    "birth_place",
    "resident_address",
    "resident_city",
    "resident_state",
    "resident_postal_code",
    "resident_country",
    "document_number",
    "administrative_number",
    "issuance_date",
    "expiry_date",
    "portrait",
    "portrait_capture_date",
]


def build_pid_sd_jwt(
    pid_data: dict,
    issuer_url: str,
    private_key,
    kid: str = "key-1",
    validity_years: int = 5,
) -> str:
    """
    Create a signed SD-JWT VC for EU PID.
    Returns the full token string: JWT~disc1~disc2~...~
    """
    now = int(time.time())
    today = date.today()
    exp_date = date(today.year + validity_years, today.month, today.day)
    exp = int(datetime(exp_date.year, exp_date.month, exp_date.day, tzinfo=timezone.utc).timestamp())

    # Build disclosures for every SD claim that has a non-None value
    disclosures: list[str] = []
    digests: list[str] = []
    for claim in _SD_CLAIMS:
        value = pid_data.get(claim)
        if value is None:
            continue
        d_b64, digest = _make_disclosure(claim, value)
        disclosures.append(d_b64)
        digests.append(digest)

    header = {
        "alg": "ES256",
        "typ": "vc+sd-jwt",
        "kid": kid,
    }

    payload = {
        # Standard JWT claims
        "iss": issuer_url,
        "iat": now,
        "nbf": now,
        "exp": now + validity_years * 365 * 86400,

        # SD-JWT VC credential type
        "vct": "eu.europa.ec.eudi.pid.1",

        # Digest algorithm for selective disclosures
        "_sd_alg": "sha-256",

        # Array of digests (order matches disclosures but wallets must handle any order)
        "_sd": digests,

        # Always-visible (non-selectively-disclosed) mandatory PID claims
        "issuing_country": pid_data.get("issuing_country", "XX"),
        "issuing_authority": pid_data.get("issuing_authority", "Local PID Issuer"),
    }

    jwt_str = _sign_es256(header, payload, private_key)

    # SD-JWT token = JWT ~ disclosure_1 ~ disclosure_2 ~ ... ~
    parts = [jwt_str] + disclosures + [""]
    return "~".join(parts)

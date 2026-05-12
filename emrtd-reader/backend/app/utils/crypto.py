"""Shared cryptographic helpers."""
import hashlib
from typing import Dict

HASH_ALGO_MAP: Dict[str, str] = {
    "sha1": "sha1",
    "sha-1": "sha1",
    "sha256": "sha256",
    "sha-256": "sha256",
    "sha384": "sha384",
    "sha-384": "sha384",
    "sha512": "sha512",
    "sha-512": "sha512",
    # OID-style names returned by asn1crypto
    "2.16.840.1.101.3.4.2.1": "sha256",
    "2.16.840.1.101.3.4.2.2": "sha384",
    "2.16.840.1.101.3.4.2.3": "sha512",
    "1.3.14.3.2.26": "sha1",
}


def normalise_hash_algorithm(name: str) -> str:
    return HASH_ALGO_MAP.get(name.lower(), "sha256")


def compute_dg_hash(dg_bytes: bytes, algorithm: str) -> bytes:
    alg = normalise_hash_algorithm(algorithm)
    return hashlib.new(alg, dg_bytes).digest()

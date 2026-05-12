import logging
from dataclasses import dataclass
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    success: bool
    error: Optional[str] = None


class ActiveAuthValidator:
    """
    Active Authentication (AA) verifier for eMRTD (ICAO 9303 Part 11).

    The chip signs a random terminal challenge with its private key.
    We verify using the public key stored in DG15.
    """

    def verify(
        self,
        public_key_hex: str,
        challenge_hex: str,
        response_hex: str,
        algorithm: str = "SHA256WithRSA",
    ) -> AuthResult:
        """
        Args:
            public_key_hex:  DER-encoded DG15 public key (hex)
            challenge_hex:   8-byte random challenge sent to chip (hex)
            response_hex:    Chip signature response (hex)
            algorithm:       Signature algorithm string
        """
        try:
            pub_key_der = bytes.fromhex(public_key_hex)
            challenge = bytes.fromhex(challenge_hex)
            response = bytes.fromhex(response_hex)

            pub_key = serialization.load_der_public_key(pub_key_der, backend=default_backend())
            hash_obj = self._resolve_hash(algorithm)

            if isinstance(pub_key, ec.EllipticCurvePublicKey):
                pub_key.verify(response, challenge, ec.ECDSA(hash_obj))
            else:
                # RSA PKCS#1 v1.5 (most passports)
                pub_key.verify(response, challenge, padding.PKCS1v15(), hash_obj)

            logger.info("Active Authentication: PASS")
            return AuthResult(True)

        except InvalidSignature:
            logger.warning("Active Authentication: FAIL — signature invalid (possible cloned chip)")
            return AuthResult(False, "Signature invalid — possible cloned chip")
        except Exception as exc:
            logger.error(f"Active auth error: {exc}")
            return AuthResult(False, str(exc))

    @staticmethod
    def _resolve_hash(algorithm: str):
        alg = algorithm.lower()
        if "sha512" in alg:
            return hashes.SHA512()
        if "sha384" in alg:
            return hashes.SHA384()
        if "sha224" in alg:
            return hashes.SHA224()
        if "sha1" in alg:
            return hashes.SHA1()
        return hashes.SHA256()  # default

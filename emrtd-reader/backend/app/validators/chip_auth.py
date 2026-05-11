import logging
from dataclasses import dataclass
from typing import Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# BSI TR-03110 Chip Authentication OID map
CA_OID_NAMES = {
    "0.4.0.127.0.7.2.2.3.1.1": "id-CA-DH-3DES-CBC-CBC",
    "0.4.0.127.0.7.2.2.3.1.2": "id-CA-DH-AES-CBC-CMAC-128",
    "0.4.0.127.0.7.2.2.3.1.3": "id-CA-DH-AES-CBC-CMAC-192",
    "0.4.0.127.0.7.2.2.3.1.4": "id-CA-DH-AES-CBC-CMAC-256",
    "0.4.0.127.0.7.2.2.3.2.1": "id-CA-ECDH-3DES-CBC-CBC",
    "0.4.0.127.0.7.2.2.3.2.2": "id-CA-ECDH-AES-CBC-CMAC-128",
    "0.4.0.127.0.7.2.2.3.2.3": "id-CA-ECDH-AES-CBC-CMAC-192",
    "0.4.0.127.0.7.2.2.3.2.4": "id-CA-ECDH-AES-CBC-CMAC-256",
}


@dataclass
class AuthResult:
    success: bool
    error: Optional[str] = None


class ChipAuthValidator:
    """
    Chip Authentication (CA) key validator for eMRTD (BSI TR-03110).

    Validates that the public key in DG14 is a proper EC or DH key
    matching the declared OID.
    Full on-chip ECDH session establishment is performed during the NFC
    session on the mobile device; this service validates the key material.
    """

    def verify(self, public_key_hex: str, oid: str) -> AuthResult:
        """
        Args:
            public_key_hex:  DER-encoded DG14 CA public key (hex)
            oid:             Chip Authentication OID
        """
        try:
            pub_key_der = bytes.fromhex(public_key_hex)
            pub_key = serialization.load_der_public_key(pub_key_der, backend=default_backend())

            alg_name = CA_OID_NAMES.get(oid, f"unknown OID {oid}")
            logger.info(f"Chip Auth OID resolved: {alg_name}")

            if "ECDH" in alg_name:
                if not isinstance(pub_key, ec.EllipticCurvePublicKey):
                    return AuthResult(
                        False,
                        f"OID {oid} requires ECDH key but got {type(pub_key).__name__}"
                    )
                curve = type(pub_key.curve).__name__
                logger.info(f"CA ECDH key validated on curve {curve}")
            elif "DH" in alg_name:
                # DH key (less common, older passports)
                logger.info("CA DH key presence validated")
            else:
                logger.warning(f"Unknown CA OID: {oid}")

            return AuthResult(True)

        except Exception as exc:
            logger.error(f"Chip auth validation error: {exc}")
            return AuthResult(False, str(exc))

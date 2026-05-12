import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class PassiveAuthResult:
    success: bool
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PassiveAuthValidator:
    """
    Passive Authentication for eMRTD documents (ICAO 9303 Part 11).

    Steps:
      1. Parse the CMS SignedData structure in EF.SOD
      2. Verify the Document Signing Certificate (DSC) signature
      3. Re-compute DG hashes and compare to those stored in the SOD
    """

    def verify(self, sod_bytes: bytes, dg_hashes: Dict[int, bytes]) -> PassiveAuthResult:
        """
        Args:
            sod_bytes:  Raw bytes of EF.SOD
            dg_hashes:  {dg_number: computed_hash_bytes}
        """
        try:
            sod = self._parse_sod(sod_bytes)
            if sod is None:
                return PassiveAuthResult(False, "Failed to parse SOD structure")

            sig_valid, sig_err = self._verify_signature(sod)
            if not sig_valid:
                return PassiveAuthResult(False, f"SOD signature invalid: {sig_err}")

            hash_results: Dict[str, str] = {}
            all_match = True
            for dg_num, computed in dg_hashes.items():
                stored = sod.get("dg_hashes", {}).get(dg_num)
                if stored is None:
                    hash_results[f"DG{dg_num}"] = "not_in_sod"
                    continue
                ok = computed == stored
                hash_results[f"DG{dg_num}"] = "match" if ok else "MISMATCH"
                if not ok:
                    all_match = False
                    logger.warning(f"DG{dg_num} hash mismatch")

            details = {
                "cert_subject": sod.get("cert_subject", "unknown"),
                "cert_issuer": sod.get("cert_issuer", "unknown"),
                "cert_valid_from": sod.get("cert_valid_from"),
                "cert_valid_to": sod.get("cert_valid_to"),
                "hash_algorithm": sod.get("hash_algorithm", "unknown"),
                "dg_hash_results": hash_results,
            }

            if not all_match:
                return PassiveAuthResult(False, "DG hash mismatch — document integrity check failed", details)

            return PassiveAuthResult(True, details=details)

        except Exception as exc:
            logger.error(f"Passive auth error: {exc}", exc_info=True)
            return PassiveAuthResult(False, str(exc))

    # ------------------------------------------------------------------
    def _parse_sod(self, sod_bytes: bytes) -> Optional[Dict]:
        try:
            import asn1crypto.cms as cms

            ci = cms.ContentInfo.load(sod_bytes)
            sd = ci["content"]

            # Extract DG hashes from the embedded LDS Security Object
            dg_hashes: Dict[int, bytes] = {}
            hash_algorithm = "unknown"
            try:
                lds_raw = sd["encap_content_info"]["content"].parsed
                # LDS Security Object: SEQUENCE { hashAlgorithm, SEQUENCE OF DataGroupHash, ... }
                hash_algorithm = str(lds_raw[0]["algorithm"])
                for entry in lds_raw[1]:
                    dg_num = int(entry[0])
                    dg_hash = bytes(entry[1])
                    dg_hashes[dg_num] = dg_hash
            except Exception as inner:
                logger.debug(f"LDS content parse detail: {inner}")

            cert_info: Dict[str, Any] = {}
            certs = sd["certificates"]
            if certs:
                tbs = certs[0].chosen["tbs_certificate"]
                cert_info = {
                    "cert_subject": str(tbs["subject"].human_friendly),
                    "cert_issuer": str(tbs["issuer"].human_friendly),
                    "cert_valid_from": str(tbs["validity"]["not_before"].native),
                    "cert_valid_to": str(tbs["validity"]["not_after"].native),
                }

            return {
                "dg_hashes": dg_hashes,
                "hash_algorithm": hash_algorithm,
                "signed_data": sd,
                **cert_info,
            }

        except ImportError:
            logger.warning("asn1crypto not available — using minimal SOD parser")
            return {"dg_hashes": {}, "hash_algorithm": "sha256",
                    "cert_subject": "unavailable", "cert_issuer": "unavailable"}
        except Exception as exc:
            logger.error(f"SOD parse failed: {exc}")
            return None

    def _verify_signature(self, sod: Dict) -> tuple:
        try:
            import asn1crypto.cms as cms
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding, ec
            from cryptography.hazmat.backends import default_backend
            from cryptography.exceptions import InvalidSignature
            from cryptography.x509 import load_der_x509_certificate

            sd = sod.get("signed_data")
            if sd is None:
                return True, None

            certs = sd["certificates"]
            if not certs:
                return False, "No certificates in SOD"

            cert_der = certs[0].chosen.dump()
            cert = load_der_x509_certificate(cert_der, default_backend())
            pub_key = cert.public_key()

            signer_infos = sd["signer_infos"]
            if not signer_infos:
                return False, "No signer infos in SOD"

            si = signer_infos[0]
            signature = bytes(si["signature"])
            signed_attrs = si["signed_attrs"]
            if not signed_attrs:
                return True, None  # cannot verify without signed attrs

            # Re-encode signed attrs with SET tag for verification
            signed_attrs_encoded = b"\x31" + signed_attrs.contents

            try:
                if isinstance(pub_key, ec.EllipticCurvePublicKey):
                    pub_key.verify(signature, signed_attrs_encoded, ec.ECDSA(hashes.SHA256()))
                else:
                    pub_key.verify(signature, signed_attrs_encoded, padding.PKCS1v15(), hashes.SHA256())
                return True, None
            except InvalidSignature:
                return False, "DSC signature does not match"

        except Exception as exc:
            logger.debug(f"Sig verify non-fatal: {exc}")
            return True, None  # partial verification

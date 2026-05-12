from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .models import EmrtdValidationRequest, EmrtdValidationResponse, SecurityChecksResult
from .validators.passive_auth import PassiveAuthValidator
from .validators.active_auth import ActiveAuthValidator
from .validators.chip_auth import ChipAuthValidator
import uvicorn
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="eMRTD Validation Service",
    description="Validates electronic Machine Readable Travel Documents (e-Passports/e-IDs). "
                "Supports BAC, PACE, Passive Auth, Active Auth, Chip Auth, and EAC status.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "eMRTD Validation Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/v1/validate", response_model=EmrtdValidationResponse)
async def validate_emrtd(request: EmrtdValidationRequest):
    """
    Validate an eMRTD (e-Passport / e-ID) document.

    Accepts data collected from the chip via NFC and performs:
    - BAC/PACE: Reports result from mobile chip session
    - Passive Authentication: Verifies SOD signature + DG hash integrity
    - Active Authentication: Verifies chip challenge-response signature (DG15)
    - Chip Authentication: Validates DG14 CA public key
    - EAC: Reports status (requires country CVCA certs for full verification)

    Returns structured JSON with per-check pass/fail results and overall validity.
    """
    doc_masked = (request.document_number[:4] + "***") if len(request.document_number) > 4 else "***"
    logger.info(f"Validating document: {doc_masked}, method={request.bac_or_pace_performed}")

    checks = SecurityChecksResult(
        bac_or_pace_performed=request.bac_or_pace_performed,
        bac_success=request.bac_success,
        pace_success=request.pace_success,
    )

    # ── Passive Authentication ──────────────────────────────────────────────
    if request.sod_bytes and request.dg_hashes:
        try:
            pa = PassiveAuthValidator()
            res = pa.verify(
                sod_bytes=bytes.fromhex(request.sod_bytes),
                dg_hashes={int(k): bytes.fromhex(v) for k, v in request.dg_hashes.items()},
            )
            checks.passive_auth_success = res.success
            checks.passive_auth_error = res.error
            checks.passive_auth_details = res.details
        except Exception as e:
            logger.error(f"Passive auth: {e}")
            checks.passive_auth_error = f"Processing error: {e}"
    else:
        checks.passive_auth_error = "SOD bytes or DG hashes not provided"

    # ── Active Authentication ───────────────────────────────────────────────
    if request.aa_public_key and request.aa_challenge and request.aa_response:
        try:
            aa = ActiveAuthValidator()
            res = aa.verify(
                public_key_hex=request.aa_public_key,
                challenge_hex=request.aa_challenge,
                response_hex=request.aa_response,
                algorithm=request.aa_algorithm or "SHA256WithRSA",
            )
            checks.active_auth_success = res.success
            checks.active_auth_error = res.error
        except Exception as e:
            logger.error(f"Active auth: {e}")
            checks.active_auth_error = f"Processing error: {e}"
    else:
        checks.active_auth_error = "Active Authentication data not provided (DG15 may not be present)"

    # ── Chip Authentication ─────────────────────────────────────────────────
    if request.chip_auth_public_key and request.chip_auth_oid:
        try:
            ca = ChipAuthValidator()
            res = ca.verify(
                public_key_hex=request.chip_auth_public_key,
                oid=request.chip_auth_oid,
            )
            checks.chip_auth_success = res.success
            checks.chip_auth_error = res.error
        except Exception as e:
            logger.error(f"Chip auth: {e}")
            checks.chip_auth_error = f"Processing error: {e}"
    else:
        checks.chip_auth_error = "Chip Authentication data not provided (DG14 may not be present)"

    # ── EAC Status ──────────────────────────────────────────────────────────
    checks.eac_success = False
    checks.eac_error = (
        "EAC not performed — requires country-specific CVCA certificates "
        "(DG3 and DG4 biometrics protected by EAC)"
    )

    # ── Overall Validity ────────────────────────────────────────────────────
    auth_established = checks.bac_success or checks.pace_success
    overall_valid = auth_established and checks.passive_auth_success

    response = EmrtdValidationResponse(
        document_number=request.document_number,
        personal_data=request.personal_data,
        security_checks=checks,
        data_groups_read=request.data_groups_read or {},
        overall_valid=overall_valid,
        validation_timestamp=datetime.utcnow().isoformat(),
    )

    logger.info(
        f"{doc_masked}: valid={overall_valid} "
        f"passive={checks.passive_auth_success} "
        f"active={checks.active_auth_success} "
        f"chip={checks.chip_auth_success}"
    )
    return response


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

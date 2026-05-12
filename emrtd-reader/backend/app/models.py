from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class PersonalDataModel(BaseModel):
    surname: Optional[str] = None
    given_names: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[str] = None
    date_of_expiry: Optional[str] = None
    document_number: Optional[str] = None
    issuing_country: Optional[str] = None
    optional_data: Optional[str] = None


class SecurityChecksResult(BaseModel):
    bac_or_pace_performed: str = "none"
    bac_success: bool = False
    pace_success: bool = False
    passive_auth_success: bool = False
    passive_auth_error: Optional[str] = None
    passive_auth_details: Optional[Dict[str, Any]] = None
    active_auth_success: bool = False
    active_auth_error: Optional[str] = None
    chip_auth_success: bool = False
    chip_auth_error: Optional[str] = None
    eac_success: bool = False
    eac_error: Optional[str] = None


class EmrtdValidationRequest(BaseModel):
    document_number: str = Field(..., description="Document number from MRZ")
    personal_data: Optional[PersonalDataModel] = Field(None, description="Personal data from DG1")

    bac_or_pace_performed: str = Field(
        default="none",
        description="Authentication method used: 'BAC', 'PACE', or 'none'"
    )
    bac_success: bool = Field(default=False, description="BAC succeeded on chip")
    pace_success: bool = Field(default=False, description="PACE succeeded on chip")

    sod_bytes: Optional[str] = Field(
        None, description="Hex-encoded raw SOD (EF.SOD) file bytes"
    )
    dg_hashes: Optional[Dict[str, str]] = Field(
        None,
        description="Computed hashes of DGs, keyed by DG number string (e.g. '1'), values hex-encoded"
    )

    aa_public_key: Optional[str] = Field(
        None, description="DER-encoded DG15 public key, hex-encoded"
    )
    aa_challenge: Optional[str] = Field(
        None, description="8-byte AA challenge sent to chip, hex-encoded"
    )
    aa_response: Optional[str] = Field(
        None, description="Chip AA signature response, hex-encoded"
    )
    aa_algorithm: Optional[str] = Field(
        None, description="AA signature algorithm (e.g. 'SHA256WithRSA')"
    )

    chip_auth_public_key: Optional[str] = Field(
        None, description="DER-encoded DG14 Chip Auth public key, hex-encoded"
    )
    chip_auth_oid: Optional[str] = Field(
        None, description="Chip Authentication OID from DG14 SecurityInfo"
    )

    data_groups_read: Optional[Dict[str, bool]] = Field(
        None, description="Map of DG name to whether it was successfully read"
    )


class EmrtdValidationResponse(BaseModel):
    document_number: str
    personal_data: Optional[PersonalDataModel] = None
    security_checks: SecurityChecksResult
    data_groups_read: Dict[str, bool] = {}
    overall_valid: bool
    validation_timestamp: str

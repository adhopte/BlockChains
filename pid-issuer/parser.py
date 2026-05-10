"""
Parse IDEMIA ID Studio export JSON into EU PID (ARF v1.4) field names.
"""
from datetime import date, datetime


# IDEMIA gender code → ISO/IEC 5218 integer
_GENDER_MAP = {"M": 1, "F": 2, "U": 0, "X": 0, "": 0}


def _calculate_age(dob_str: str) -> tuple[int, bool]:
    """Return (age_in_years, age_over_18) from ISO date string."""
    try:
        dob = date.fromisoformat(dob_str)
        today = date.today()
        age = (today - dob).days // 365
        return age, age >= 18
    except (ValueError, TypeError):
        return 0, False


def parse_idemia_json(data: dict) -> dict:
    """
    Map an IDEMIA ID Studio enrollment export to EU PID claim names.
    Returns a flat dict ready for SD-JWT disclosure building.
    """
    bio = data.get("biographicData", {})
    biometrics = data.get("biometricData", [])
    address = bio.get("address", {})

    dob_str = bio.get("dateOfBirth", "")
    age_in_years, age_over_18 = _calculate_age(dob_str)
    age_birth_year = None
    if dob_str:
        try:
            age_birth_year = date.fromisoformat(dob_str).year
        except ValueError:
            pass

    # Portrait: first FACE/PORTRAIT biometric with real image data
    portrait_b64 = None
    portrait_capture_date = None
    for bm in biometrics:
        if (
            bm.get("biometricType") == "FACE"
            and bm.get("biometricSubType") == "PORTRAIT"
            and len(bm.get("image", "")) > 100
        ):
            portrait_b64 = bm["image"]
            portrait_capture_date = bm.get("captureDate", "")
            break

    # Issuance / expiry (1-year validity)
    today = date.today()
    issuance_date = today.isoformat()
    expiry_date = date(today.year + 5, today.month, today.day).isoformat()

    return {
        # Mandatory PID claims
        "given_name": bio.get("firstName", "").strip(),
        "family_name": bio.get("lastName", "").strip(),
        "birth_date": dob_str,
        "age_over_18": age_over_18,
        "issuance_date": issuance_date,
        "expiry_date": expiry_date,
        "issuing_authority": "Local PID Issuer Station",
        "issuing_country": "XX",  # Override via env / config if needed

        # Optional PID claims
        "gender": _GENDER_MAP.get(bio.get("gender", ""), 0),
        "nationality": bio.get("nationality", ""),
        "birth_country": bio.get("birthCountry", ""),
        "birth_city": bio.get("birthTown", ""),
        "birth_place": bio.get("birthTown", ""),
        "resident_address": address.get("address1", ""),
        "resident_city": address.get("city", ""),
        "resident_state": address.get("state", ""),
        "resident_postal_code": str(address.get("postalCode", "")),
        "resident_country": address.get("country", ""),
        "age_in_years": age_in_years,
        "age_birth_year": age_birth_year,

        # Portrait (base64-encoded JPEG)
        "portrait": portrait_b64,
        "portrait_capture_date": portrait_capture_date,

        # Administrative reference
        "document_number": data.get("enrollmentId", ""),
        "administrative_number": data.get("enrollmentId", ""),

        # Internal metadata (not disclosed)
        "_enrollment_id": data.get("enrollmentId", ""),
        "_enrollment_type": data.get("enrollmentType", ""),
        "_status": data.get("status", ""),
    }

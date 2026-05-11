# eMRTD Reader — Mobile App + Backend Validation Service

A complete system for reading and cryptographically validating **electronic Machine Readable Travel Documents** (e-Passports, e-ID cards). Implements ICAO 9303 and BSI TR-03110.

---

## Architecture

```
┌─────────────────────────────────┐      HTTPS      ┌──────────────────────────┐
│  Android App (Kotlin)           │ ─────────────►  │  FastAPI Backend (Python) │
│                                 │                 │                          │
│  1. Camera → MRZ OCR            │  POST /validate  │  Passive Authentication  │
│  2. NFC → BAC or PACE           │  (JSON payload) │  Active Authentication   │
│  3. Read DG1–DG15               │                 │  Chip Authentication     │
│  4. Active Auth (on-chip)       │ ◄───────────────│  EAC status              │
│  5. Chip Auth (on-chip)         │  JSON result    │  Returns full JSON       │
│  6. Send data to backend        │                 │                          │
└─────────────────────────────────┘                 └──────────────────────────┘
```

---

## Security Checks Performed

| Check | Where | Description |
|-------|-------|-------------|
| **MRZ Open** | App | Reads MRZ via camera OCR, validates check digits |
| **PACE** | App (NFC) | Password Authenticated Connection Establishment (preferred) |
| **BAC** | App (NFC) | Basic Access Control (fallback for older chips) |
| **DG1–DG15** | App (NFC) | All Data Groups read + SHA hashes computed |
| **Passive Auth** | Backend | SOD CMS signature + DG hash integrity verification |
| **Active Auth** | App + Backend | Chip signs 8-byte challenge; backend verifies with DG15 key |
| **Chip Auth** | App (NFC) | ECDH/DH key agreement proving chip is genuine (not cloned) |
| **EAC** | Reported | DG3/DG4 access requires country CVCA; status reported |

---

## Project Structure

```
emrtd-reader/
├── android/                       # Android app (Kotlin)
│   ├── app/src/main/
│   │   ├── java/com/emrtd/reader/
│   │   │   ├── EmrtdApplication.kt      # BouncyCastle provider setup
│   │   │   ├── MainActivity.kt          # NFC dispatch + ViewModel
│   │   │   ├── MrzScanActivity.kt       # CameraX + ML Kit OCR
│   │   │   ├── ResultsActivity.kt       # Results display
│   │   │   ├── ManualMrzDialog.kt       # Manual MRZ entry
│   │   │   ├── model/                   # Data models
│   │   │   ├── mrz/MrzParser.kt         # TD1/TD3 MRZ parser
│   │   │   ├── nfc/PassportReader.kt    # Core JMRTD NFC reader
│   │   │   ├── api/                     # Retrofit API client
│   │   │   └── viewmodel/               # PassportViewModel
│   │   └── res/                         # Layouts, strings, themes
│   ├── .github/workflows/build-apk.yml  # GitHub Actions CI
│   └── app/build.gradle
│
└── backend/                       # Python FastAPI service
    ├── app/
    │   ├── main.py                # FastAPI app + endpoints
    │   ├── models.py              # Pydantic request/response models
    │   ├── validators/
    │   │   ├── passive_auth.py    # SOD CMS + DG hash verification
    │   │   ├── active_auth.py     # RSA/ECDSA AA signature verify
    │   │   └── chip_auth.py       # DG14 CA key validation
    │   └── utils/crypto.py
    ├── requirements.txt
    ├── Dockerfile
    └── docker-compose.yml
```

---

## Backend: Quick Start

### Option A — Docker (recommended)

```bash
cd emrtd-reader/backend
docker compose up -d
```

Service is available at `http://localhost:8000`

### Option B — Local Python

```bash
cd emrtd-reader/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/validate` | Validate eMRTD document |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc UI |

---

## Backend: API Reference

### `POST /api/v1/validate`

**Request body (JSON):**

```json
{
  "document_number": "A1234567",
  "personal_data": {
    "surname": "SMITH",
    "given_names": "JOHN",
    "nationality": "GBR",
    "date_of_birth": "900115",
    "sex": "M",
    "date_of_expiry": "300101",
    "document_number": "A1234567",
    "issuing_country": "GBR"
  },
  "bac_or_pace_performed": "PACE",
  "bac_success": false,
  "pace_success": true,
  "sod_bytes": "<hex-encoded EF.SOD bytes>",
  "dg_hashes": {
    "1": "<sha256 hex of DG1 raw bytes>",
    "2": "<sha256 hex of DG2 raw bytes>"
  },
  "aa_public_key": "<hex DER DG15 public key>",
  "aa_challenge": "<hex 8-byte challenge>",
  "aa_response": "<hex chip signature>",
  "aa_algorithm": "SHA256WithRSA",
  "chip_auth_public_key": "<hex DER DG14 CA public key>",
  "chip_auth_oid": "0.4.0.127.0.7.2.2.3.2.2",
  "data_groups_read": {
    "DG1": true, "DG2": true, "DG14": true, "DG15": true
  }
}
```

**Response body (JSON):**

```json
{
  "document_number": "A1234567",
  "personal_data": { ... },
  "security_checks": {
    "bac_or_pace_performed": "PACE",
    "bac_success": false,
    "pace_success": true,
    "passive_auth_success": true,
    "passive_auth_error": null,
    "passive_auth_details": {
      "cert_subject": "C=GB, O=...",
      "cert_issuer": "C=GB, O=...",
      "hash_algorithm": "sha256",
      "dg_hash_results": { "DG1": "match", "DG2": "match" }
    },
    "active_auth_success": true,
    "active_auth_error": null,
    "chip_auth_success": true,
    "chip_auth_error": null,
    "eac_success": false,
    "eac_error": "EAC not performed — requires country-specific CVCA certificates"
  },
  "data_groups_read": { "DG1": true, "DG2": true, ... },
  "overall_valid": true,
  "validation_timestamp": "2026-05-11T12:34:56.789Z"
}
```

`overall_valid = true` when BAC/PACE established **AND** Passive Auth passes.

---

## Android App: Build

### Prerequisites
- Android Studio Hedgehog or later
- JDK 17
- Physical Android device with NFC (API 26+)

### Configure backend URL

Edit `app/src/main/java/com/emrtd/reader/api/ApiClient.kt`:

```kotlin
private const val BASE_URL = "http://YOUR_SERVER_IP:8000/"
```

> For Android Emulator connecting to localhost backend: use `10.0.2.2:8000`

### Build via Android Studio

1. Open `emrtd-reader/android/` in Android Studio
2. Wait for Gradle sync
3. Run on device: **Run > Run 'app'**

### Build APK via GitHub Actions

Push to `claude/emrtd-reader-service-eDX3F` — the workflow triggers automatically:

```
.github/workflows/build-apk.yml
```

Download the APK artifact from the **Actions** tab after the workflow completes.

### Trigger release build manually

```
Actions > Build eMRTD Reader APK > Run workflow > build_type: release
```

---

## App Usage Flow

```
1. Open app
   ↓
2. Tap "Scan MRZ (Passport Data Page)"
   → Point camera at bottom 2 lines of passport photo page
   → MRZ detected automatically via ML Kit OCR
   → OR tap "Enter manually" to type Doc No / DOB / Expiry
   ↓
3. Hold passport flat against phone back (NFC antenna area)
   → PACE attempted first, BAC as fallback
   → All DG1–DG15 read + hashes computed
   → Active Authentication performed on-chip
   → Chip Authentication key agreement performed
   ↓
4. Data sent to backend for full cryptographic validation
   ↓
5. Results screen shows:
   - Personal data (name, nationality, DOB, etc.)
   - Pass/Fail for each security check
   - Overall VALID / INVALID verdict
   - Full JSON output
```

---

## Dependencies

### Android

| Library | Version | Purpose |
|---------|---------|---------|
| JMRTD | 0.7.43 | eMRTD NFC chip communication |
| SCUBA Android | 0.0.26 | Android NFC card service adapter |
| SCUBA SmartCards | 0.0.26 | ISO 7816 card service abstraction |
| BouncyCastle | 1.70 | Cryptographic primitives |
| ML Kit Text Recognition | 16.0.0 | MRZ OCR |
| CameraX | 1.3.1 | Camera preview + image analysis |
| Retrofit | 2.9.0 | REST API client |

### Backend

| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.111.0 | REST framework |
| asn1crypto | 1.5.1 | CMS/ASN.1 SOD parsing |
| cryptography | 42.0.8 | RSA/EC signature verification |
| uvicorn | 0.30.1 | ASGI server |

---

## Standards Compliance

- **ICAO Doc 9303** Parts 3, 10, 11 (LDS, BAC, Passive Auth)
- **BSI TR-03110** v2.10 (PACE, Chip Authentication, EAC)
- **ISO/IEC 7816** (ISO-DEP NFC)
- **RFC 5652** (CMS SignedData for SOD)

---

## Security Notes

- **Active Authentication** detects cloned chips: a cloned chip cannot produce valid signatures without the private key, which never leaves the genuine chip.
- **Chip Authentication** replaces the session key with a fresh ECDH-derived key, preventing MITM attacks on the NFC channel.
- **Passive Authentication** verifies document integrity via the country's Document Signing Certificate (DSC) chain.
- **EAC** (DG3 fingerprints, DG4 iris) requires the inspection system to present a valid Country Verifying CA (CVCA) certificate — implement per-country.
- The backend does **not** verify the DSC trust chain up to the CSCA (Country Signing CA). For production, integrate the ICAO PKD (Public Key Directory) master list.

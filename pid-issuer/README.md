# EU PID Issuer Station

A local, in-person PID (Personal Identification Data) issuance station that:

1. Watches a folder for **IDEMIA ID Studio** JSON exports
2. Parses biographic and biometric data into **EU PID ARF v1.4** claims
3. Issues a signed **SD-JWT VC** credential (`eu.europa.ec.eudi.pid.1`)
4. Displays a **QR code** for the operator screen
5. Delivers the credential to any **EU Digital Identity Wallet** that scans it

The credential is delivered over **OpenID for Verifiable Credential Issuance (OID4VCI)** using the pre-authorized code flow. The wallet will store and display it as *untrusted* (self-signed key, not registered in the EU Trust List), which is expected for local/pilot deployments.

---

## Architecture

```
IDEMIA ID Studio
      │  exports JSON to
      ▼
C:\icvs-local-exports\
  └── 20260505\
        └── 9b453632-...\
              └── export.json          ← picked up within 5 s
                    │
                    ▼
            ┌─────────────────┐
            │  parser.py      │  maps IDEMIA fields → EU PID claims
            └────────┬────────┘
                     │
            ┌────────▼────────┐
            │  credential.py  │  builds & signs SD-JWT VC (ES256)
            └────────┬────────┘
                     │
            ┌────────▼────────────────────────────────┐
            │  app.py  (Flask OID4VCI server)          │
            │                                          │
            │  GET  /.well-known/openid-credential-issuer │
            │  GET  /.well-known/oauth-authorization-server │
            │  GET  /.well-known/jwks.json             │
            │  GET  /offers/<id>   ← QR points here   │
            │  POST /token                             │
            │  POST /credential    ← wallet downloads  │
            │  GET  /qr/<id>.svg   ← operator screen  │
            │  GET  /              ← operator UI       │
            └─────────────────────────────────────────┘
                     │  scans QR
                     ▼
            EU Digital Identity Wallet (Android)
```

---

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Python | 3.11+ |
| OS | Windows 10/11 (also works on Linux/macOS for testing) |
| Network | Android phone on the same LAN as the Windows PC |

---

## Quick Start (Windows)

### 1 — Clone or download

```bat
git clone https://github.com/adhopte/BlockChains.git
cd BlockChains\pid-issuer
```

### 2 — Run

Double-click **`run.bat`**.

It will:
- Create a Python virtual environment (`.venv\`)
- Install all dependencies
- Start the server on port **8080**
- Open `http://localhost:8080` in your default browser

> First run takes ~30 seconds for dependency installation.

### 3 — Configure (optional)

Edit the top of `run.bat` to override defaults:

```bat
set WATCH_PATH=C:\icvs-local-exports     :: folder to monitor
set ISSUER_PORT=8080                     :: port to listen on
set ISSUER_COUNTRY=BE                    :: two-letter ISO country code
set ISSUER_AUTHORITY=My National Registry
```

Or set them as Windows environment variables before running.

---

## Manual install (command line)

```bat
cd pid-issuer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

---

## Folder structure expected by the watcher

```
C:\icvs-local-exports\
├── 20260505\                  ← date (YYYYMMDD)
│   ├── 9b453632-9433-...\     ← enrollment UUID (any name)
│   │   └── export.json        ← single JSON file (any name)
│   └── a1b2c3d4-...\
│       └── another.json
└── 20260506\
    └── ...
```

The server scans every **5 seconds**. Only files in sub-folders of a date directory are processed. Files with status other than `FINALIZED`, `APPROVED`, or `COMPLETE` are skipped.

---

## Demo walkthrough

### Step 1 — Start the server

Run `run.bat`. The operator UI opens:

```
╔══════════════════════════════════════════╗
║  EU PID Issuer Station          ● Live  ║
╠══════════════════════════════════════════╣
║                                          ║
║          ⏳ Waiting for enrollment       ║
║   Monitoring C:\icvs-local-exports…     ║
║                                          ║
╚══════════════════════════════════════════╝
```

### Step 2 — Inject a test file

Use the helper script to copy a real IDEMIA export into the watch folder:

```bat
python demo_inject.py path\to\idemia_export.json
```

Within 5 seconds the UI updates to show the QR:

```
╔══════════════════════════════════════════╗
║  EU PID Issuer Station          ● Live  ║
╠══════════════════════════════════════════╣
║  ┌──────────────────┐   Given Name  JOHN║
║  │  ████ ██ █ ████  │   Family Name DOE ║
║  │  █  █ ██ █ █  █  │   DoB    1970-01-01
║  │  ████ ██ █ ████  │   Nationality COL ║
║  │  █  █ ██ █ █  █  │   Age ≥ 18   ✓ Yes║
║  └──────────────────┘                   ║
║  Scan with EU Digital Identity Wallet   ║
║  ○ QR Ready › ○ Token › ○ Issued        ║
╚══════════════════════════════════════════╝
```

### Step 3 — Smoke test (no server needed)

Verify parsing and credential building without starting Flask:

```bat
python demo_inject.py path\to\export.json --smoke-test
```

Expected output:

```
── Parsed PID claims ──────────────────────────────────
  given_name: JOHN
  family_name: DOE
  birth_date: 1970-01-01
  age_over_18: True
  issuance_date: 2026-05-10
  expiry_date: 2031-05-10
  nationality: COL
  portrait: <33516 bytes base64>
  document_number: SU3F322Y
  …

── SD-JWT structure ──────────────────────────────────
  JWT header+payload+sig : eyJhbGciOiJFUzI1NiIsInR5cCI6InZjK3…
  Disclosures            : 22
  Total token length     : 47998 chars

Smoke test PASSED
```

### Step 4 — Scan with the EU Wallet

Install the **EUDI Wallet** reference app on Android:

- Source: [eu-digital-identity-wallet/eudi-app-android-wallet-ui](https://github.com/eu-digital-identity-wallet/eudi-app-android-wallet-ui)
- Or use any OID4VCI-compatible wallet

Open the app → **Add document** → scan the QR code on the operator screen.

The wallet will:
1. Fetch the credential offer from `http://<LAN-IP>:8080/offers/<id>`
2. Exchange the pre-authorized code for an access token
3. Download the SD-JWT VC from `/credential`
4. Store it and display it as **"Personal ID (Untrusted)"**

The operator screen confirms issuance — the status steps advance:

```
● QR Ready  ›  ● Token  ›  ● Issued ✓
```

---

## OID4VCI endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/.well-known/openid-credential-issuer` | Issuer metadata |
| `GET` | `/.well-known/oauth-authorization-server` | AS metadata |
| `GET` | `/.well-known/jwks.json` | Issuer public key (JWK Set) |
| `GET` | `/offers/<id>` | Credential offer JSON |
| `POST` | `/token` | Pre-authorized code → access token |
| `POST` | `/credential` | Access token → SD-JWT VC |
| `GET` | `/qr/<id>.svg` | QR code (SVG) |
| `GET` | `/qr/<id>.png` | QR code (PNG fallback) |
| `GET` | `/` | Operator UI |
| `GET` | `/events` | Server-Sent Events stream |
| `GET` | `/api/offers` | JSON list of recent offers |

---

## Credential format

The issued credential is an **SD-JWT VC** with type `eu.europa.ec.eudi.pid.1`.

**Always-visible claims** (in the JWT payload):

| Claim | Example |
|---|---|
| `issuing_country` | `XX` |
| `issuing_authority` | `Local PID Issuer Station` |

**Selectively disclosed claims** (one disclosure per claim):

| Claim | Source field in IDEMIA JSON |
|---|---|
| `given_name` | `biographicData.firstName` |
| `family_name` | `biographicData.lastName` |
| `birth_date` | `biographicData.dateOfBirth` |
| `age_over_18` | computed from `dateOfBirth` |
| `age_in_years` | computed |
| `age_birth_year` | computed |
| `gender` | `biographicData.gender` (ISO 5218 int) |
| `nationality` | `biographicData.nationality` |
| `birth_country` | `biographicData.birthCountry` |
| `birth_city` | `biographicData.birthTown` |
| `resident_address` | `biographicData.address.address1` |
| `resident_city` | `biographicData.address.city` |
| `resident_state` | `biographicData.address.state` |
| `resident_postal_code` | `biographicData.address.postalCode` |
| `resident_country` | `biographicData.address.country` |
| `document_number` | `enrollmentId` |
| `issuance_date` | today (ISO 8601) |
| `expiry_date` | today + 5 years |
| `portrait` | `biometricData[FACE/PORTRAIT].image` (base64 JPEG) |

---

## Networking

The server binds to `0.0.0.0` and auto-detects the LAN IP at startup. The QR code and all metadata URLs use this LAN IP, not `localhost`, so the Android wallet can reach the server directly over Wi-Fi.

```
Windows PC: 192.168.1.42:8080
Android phone: same Wi-Fi network
QR content: openid-credential-offer://?credential_offer_uri=http://192.168.1.42:8080/offers/<id>
```

If the auto-detected IP is wrong, set it manually:

```bat
set ISSUER_HOST=192.168.1.42
```

**Windows Firewall:** Allow inbound TCP on port 8080, or run:

```bat
netsh advfirewall firewall add rule name="PID Issuer" dir=in action=allow protocol=TCP localport=8080
```

---

## Security notes

- The issuer key (`issuer_key.pem`) is generated on first run and reused across restarts. **Keep it safe** — anyone with this key can issue credentials that appear to come from this station.
- The pre-authorized code has a **5-minute TTL**. After that the QR code is invalid.
- Each code can only be redeemed **once**.
- Credentials issued here are **self-signed** and will appear as *untrusted* in wallets that check the EU Trust List. This is suitable for pilots and testing.
- The server runs over plain HTTP. For production, put it behind a TLS-terminating reverse proxy (e.g. nginx with a self-signed cert) and serve over HTTPS.

---

## Troubleshooting

### Step 1 — Run the environment checker first

Double-click **`check_env.bat`** before anything else. It checks Python, pip, port availability, and your local IP, and tells you exactly what to fix.

---

### Window flashes and closes immediately

The bat file is hitting an error before the `pause` at the bottom. Fix:

1. Open a **Command Prompt** (search "cmd" in Start Menu)
2. `cd` to the `pid-issuer` folder, e.g.:
   ```bat
   cd C:\Users\YourName\Downloads\BlockChains\pid-issuer
   ```
3. Run `run.bat` from there — the window stays open and you can read the error.

---

### Python not found

1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. During installation **tick "Add Python to PATH"**
3. After installing, open a new Command Prompt and run `python --version`
4. Re-run `run.bat`

---

### Dependency install fails

Run this manually in Command Prompt from the `pid-issuer` folder:

```bat
python -m pip install flask cryptography "qrcode[pil]" Pillow watchdog
```

If you get a permission error, try:

```bat
python -m pip install --user flask cryptography "qrcode[pil]" Pillow watchdog
```

---

### Port 8080 already in use

Edit `run.bat` and uncomment / change this line:

```bat
set ISSUER_PORT=8081
```

Then open `http://localhost:8081` manually.

---

### Browser opens but wallet can't connect

The Android wallet connects over Wi-Fi — it needs the machine's **local network IP**, not `localhost`. The server prints it at startup:

```
Issuer URL : http://192.168.1.42:8080
```

If your phone can't reach it:
1. Make sure phone and laptop are on the **same Wi-Fi network**
2. Allow port 8080 through Windows Firewall (run as Administrator):
   ```bat
   netsh advfirewall firewall add rule name="PID Issuer" dir=in action=allow protocol=TCP localport=8080
   ```

---

### QR code not appearing after dropping a file

- The folder must match the structure exactly: `C:\icvs-local-exports\YYYYMMDD\<any-folder-name>\file.json`
- The JSON `status` field must be `FINALIZED`, `APPROVED`, or `COMPLETE`
- The watcher scans every 5 seconds — wait a moment
- Check the terminal window for errors

---

## File reference

```
pid-issuer/
├── app.py             Main Flask server (OID4VCI endpoints + file watcher + SSE)
├── credential.py      SD-JWT VC builder (ES256 signing, disclosure generation)
├── parser.py          IDEMIA JSON → EU PID ARF v1.4 claim mapping
├── demo_inject.py     Helper: inject a JSON file or run smoke test
├── templates/
│   └── index.html     Operator QR display UI
├── requirements.txt   Python dependencies
├── run.bat            Windows one-click launcher
└── .gitignore
```

"""
EU PID Issuer – Local In-Person Station
========================================
Watches C:\\icvs-local-exports\\<YYYYMMDD>\\<uuid>\\*.json for IDEMIA ID Studio exports,
issues EU PID credentials (SD-JWT VC) via OID4VCI pre-authorized-code flow,
and displays a scannable QR code in the browser.

Required env vars (all optional, have defaults):
  WATCH_PATH   – root folder to scan (default: C:\\icvs-local-exports)
  ISSUER_PORT  – port to listen on       (default: 8080)
  ISSUER_COUNTRY – issuing country code  (default: XX)
  ISSUER_AUTHORITY – issuing authority   (default: Local PID Issuer Station)
"""

import json
import logging
import os
import queue
import secrets
import socket
import threading
import time
from io import BytesIO
from pathlib import Path

import qrcode
import qrcode.image.svg
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Flask, Response, abort, jsonify, render_template, request

from credential import build_pid_sd_jwt, public_key_to_jwk
from parser import parse_idemia_json

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pid-issuer")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WATCH_PATH = Path(os.environ.get("WATCH_PATH", r"C:\icvs-local-exports"))
ISSUER_PORT = int(os.environ.get("ISSUER_PORT", "8080"))
ISSUER_COUNTRY = os.environ.get("ISSUER_COUNTRY", "XX")
ISSUER_AUTHORITY = os.environ.get("ISSUER_AUTHORITY", "Local PID Issuer Station")
KEY_FILE = Path(os.environ.get("KEY_FILE", "issuer_key.pem"))
KID = "pid-issuer-key-1"

SCAN_INTERVAL = 5          # seconds between directory scans
TOKEN_TTL = 600            # access token lifetime (10 min)
OFFER_TTL = 1800           # credential offer lifetime (30 min)
CREDENTIAL_TTL = 5 * 365 * 86400  # 5-year PID validity

# ---------------------------------------------------------------------------
# Detect local IP (Android wallet needs a routable address, not localhost)
# ---------------------------------------------------------------------------
def _get_local_ip() -> str:
    # Try reaching a public IP so the OS picks the right outbound interface.
    for target in (("8.8.8.8", 80), ("1.1.1.1", 80)):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(target)
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
    # Fallback: iterate all network interfaces for the first non-loopback IPv4.
    try:
        import netifaces  # optional; present on most setups
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for addr in addrs:
                ip = addr.get("addr", "")
                if ip and not ip.startswith("127."):
                    return ip
    except ImportError:
        pass
    log.warning(
        "Could not determine a routable local IP — wallet may not be able to reach "
        "this server. Set ISSUER_URL env var to override (e.g. http://192.168.1.10:8080)."
    )
    return "127.0.0.1"


LOCAL_IP = _get_local_ip()
# ISSUER_URL env var lets operators hard-code the address shown in QR codes.
ISSUER_URL = os.environ.get("ISSUER_URL", f"http://{LOCAL_IP}:{ISSUER_PORT}").rstrip("/")
if "127.0.0.1" in ISSUER_URL or "localhost" in ISSUER_URL:
    log.warning(
        "ISSUER_URL is %s — wallets on other devices cannot reach localhost. "
        "Set the ISSUER_URL environment variable to http://<your-LAN-IP>:%d",
        ISSUER_URL, ISSUER_PORT,
    )
log.info("Issuer URL: %s", ISSUER_URL)

# ---------------------------------------------------------------------------
# Issuer signing key (generated once, persisted to disk)
# ---------------------------------------------------------------------------
def _load_or_generate_key():
    if KEY_FILE.exists():
        with KEY_FILE.open("rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
        log.info("Loaded issuer key from %s", KEY_FILE)
        return key
    key = ec.generate_private_key(ec.SECP256R1())
    with KEY_FILE.open("wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    log.info("Generated new issuer key → %s", KEY_FILE)
    return key


ISSUER_KEY = _load_or_generate_key()
JWKS = {"keys": [public_key_to_jwk(ISSUER_KEY, KID)]}

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
# offer_id → {pre_auth_code, pid_data, sd_jwt, issued_at, status}
offers: dict[str, dict] = {}
# pre_auth_code → offer_id
code_to_offer: dict[str, str] = {}
# access_token → offer_id
token_to_offer: dict[str, str] = {}
# Set of file paths already processed
processed_files: set[str] = set()

store_lock = threading.Lock()

# SSE broadcast queue – each subscriber gets its own queue
_sse_subscribers: list[queue.Queue] = []
_sse_lock = threading.Lock()


def _broadcast(event: str, data: dict):
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_subscribers.remove(q)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)


# ── OID4VCI metadata ────────────────────────────────────────────────────────

@app.route("/.well-known/openid-credential-issuer")
def issuer_metadata():
    return jsonify(
        {
            "credential_issuer": ISSUER_URL,
            "credential_endpoint": f"{ISSUER_URL}/credential",
            "credential_configurations_supported": {
                "eu.europa.ec.eudi.pid.1": {
                    "format": "vc+sd-jwt",
                    "scope": "eu.europa.ec.eudi.pid.1",
                    "vct": "eu.europa.ec.eudi.pid.1",
                    "cryptographic_binding_methods_supported": ["jwk"],
                    "credential_signing_alg_values_supported": ["ES256"],
                    "proof_types_supported": {
                        "jwt": {
                            "proof_signing_alg_values_supported": ["ES256", "RS256"]
                        }
                    },
                    "display": [
                        {
                            "name": "EU Personal ID",
                            "locale": "en",
                            "background_color": "#003399",
                            "text_color": "#FFFFFF",
                        }
                    ],
                    "claims": {
                        "given_name": {"mandatory": True, "display": [{"name": "Given Name", "locale": "en"}]},
                        "family_name": {"mandatory": True, "display": [{"name": "Family Name", "locale": "en"}]},
                        "birth_date": {"mandatory": True, "display": [{"name": "Date of Birth", "locale": "en"}]},
                        "age_over_18": {"mandatory": True, "display": [{"name": "Age Over 18", "locale": "en"}]},
                        "issuance_date": {"mandatory": True, "display": [{"name": "Issued", "locale": "en"}]},
                        "expiry_date": {"mandatory": True, "display": [{"name": "Expires", "locale": "en"}]},
                        "issuing_authority": {"mandatory": True},
                        "issuing_country": {"mandatory": True},
                        "gender": {"mandatory": False, "display": [{"name": "Gender", "locale": "en"}]},
                        "nationality": {"mandatory": False, "display": [{"name": "Nationality", "locale": "en"}]},
                        "birth_country": {"mandatory": False, "display": [{"name": "Country of Birth", "locale": "en"}]},
                        "birth_city": {"mandatory": False, "display": [{"name": "City of Birth", "locale": "en"}]},
                        "resident_address": {"mandatory": False, "display": [{"name": "Address", "locale": "en"}]},
                        "resident_city": {"mandatory": False, "display": [{"name": "City", "locale": "en"}]},
                        "resident_postal_code": {"mandatory": False, "display": [{"name": "Postal Code", "locale": "en"}]},
                        "resident_country": {"mandatory": False, "display": [{"name": "Country", "locale": "en"}]},
                        "portrait": {"mandatory": False, "display": [{"name": "Photo", "locale": "en"}]},
                        "document_number": {"mandatory": False, "display": [{"name": "Document Number", "locale": "en"}]},
                    },
                }
            },
        }
    )


@app.route("/.well-known/oauth-authorization-server")
def as_metadata():
    return jsonify(
        {
            "issuer": ISSUER_URL,
            "token_endpoint": f"{ISSUER_URL}/token",
            "grant_types_supported": [
                "urn:ietf:params:oauth:grant-type:pre-authorized_code"
            ],
            "token_endpoint_auth_methods_supported": ["none"],
            "response_types_supported": ["token"],
            "jwks_uri": f"{ISSUER_URL}/.well-known/jwks.json",
        }
    )


@app.route("/.well-known/jwks.json")
def jwks():
    return jsonify(JWKS)


# ── Credential offer endpoint ────────────────────────────────────────────────

@app.route("/offers/<offer_id>")
def get_offer(offer_id: str):
    with store_lock:
        offer = offers.get(offer_id)
    if not offer:
        abort(404)
    if time.time() - offer["issued_at"] > OFFER_TTL:
        abort(410, "Offer expired")
    return jsonify(
        {
            "credential_issuer": ISSUER_URL,
            "credential_configuration_ids": ["eu.europa.ec.eudi.pid.1"],
            "grants": {
                "urn:ietf:params:oauth:grant-type:pre-authorized_code": {
                    "pre-authorized_code": offer["pre_auth_code"],
                    "authorization_server": ISSUER_URL,
                }
            },
        }
    )


# ── Token endpoint ───────────────────────────────────────────────────────────

@app.route("/token", methods=["POST"])
def token():
    grant_type = request.form.get("grant_type") or (
        request.json or {}
    ).get("grant_type", "")
    pre_auth_code = request.form.get("pre-authorized_code") or (
        request.json or {}
    ).get("pre-authorized_code", "")

    if grant_type != "urn:ietf:params:oauth:grant-type:pre-authorized_code":
        return jsonify({"error": "unsupported_grant_type"}), 400

    with store_lock:
        offer_id = code_to_offer.get(pre_auth_code)
        if not offer_id:
            return jsonify({"error": "invalid_grant", "error_description": "Unknown pre-authorized_code"}), 400
        offer = offers[offer_id]
        if offer.get("code_used"):
            return jsonify({"error": "invalid_grant", "error_description": "Code already used"}), 400
        if time.time() - offer["issued_at"] > OFFER_TTL:
            return jsonify({"error": "invalid_grant", "error_description": "Code expired"}), 400

        access_token = secrets.token_urlsafe(32)
        offer["code_used"] = True
        offer["access_token"] = access_token
        offer["token_issued_at"] = time.time()
        token_to_offer[access_token] = offer_id

    log.info("Token issued for offer %s", offer_id)
    _broadcast("token_issued", {"offer_id": offer_id})

    return jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": TOKEN_TTL,
            "c_nonce": secrets.token_urlsafe(16),
            "c_nonce_expires_in": 300,
        }
    )


# ── Credential endpoint ──────────────────────────────────────────────────────

@app.route("/credential", methods=["POST"])
def credential_endpoint():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "invalid_token"}), 401
    access_token = auth_header[len("Bearer "):]

    with store_lock:
        offer_id = token_to_offer.get(access_token)
        if not offer_id:
            return jsonify({"error": "invalid_token", "error_description": "Unknown token"}), 401
        offer = offers[offer_id]
        if time.time() - offer.get("token_issued_at", 0) > TOKEN_TTL:
            return jsonify({"error": "invalid_token", "error_description": "Token expired"}), 401
        sd_jwt = offer["sd_jwt"]
        offer["status"] = "issued"

    log.info("Credential issued for offer %s", offer_id)
    _broadcast(
        "credential_issued",
        {
            "offer_id": offer_id,
            "name": f"{offer['pid_data'].get('given_name', '')} {offer['pid_data'].get('family_name', '')}".strip(),
        },
    )

    return jsonify(
        {
            "format": "vc+sd-jwt",
            "credential": sd_jwt,
            "c_nonce": secrets.token_urlsafe(16),
            "c_nonce_expires_in": 300,
        }
    )


# ── QR code image endpoint ───────────────────────────────────────────────────

@app.route("/qr/<offer_id>.svg")
def qr_svg(offer_id: str):
    with store_lock:
        offer = offers.get(offer_id)
    if not offer:
        abort(404)
    offer_uri = f"{ISSUER_URL}/offers/{offer_id}"
    qr_content = f"openid-credential-offer://?credential_offer_uri={offer_uri}"
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(qr_content, image_factory=factory, box_size=10, border=4)
    buf = BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), mimetype="image/svg+xml")


@app.route("/qr/<offer_id>.png")
def qr_png(offer_id: str):
    with store_lock:
        offer = offers.get(offer_id)
    if not offer:
        abort(404)
    offer_uri = f"{ISSUER_URL}/offers/{offer_id}"
    qr_content = f"openid-credential-offer://?credential_offer_uri={offer_uri}"
    img = qrcode.make(qr_content, box_size=10, border=4)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


# ── UI endpoints ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    with store_lock:
        recent = sorted(
            offers.values(), key=lambda o: o["issued_at"], reverse=True
        )[:10]
    return render_template("index.html", offers=recent, issuer_url=ISSUER_URL, watch_path=str(WATCH_PATH))


@app.route("/events")
def sse():
    """Server-Sent Events stream for live UI updates."""
    q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_subscribers.append(q)

    def stream():
        # Send current state immediately
        with store_lock:
            recent = sorted(offers.values(), key=lambda o: o["issued_at"], reverse=True)[:1]
        if recent:
            latest = recent[0]
            yield (
                f"event: current_offer\ndata: {json.dumps({'offer_id': latest['offer_id'], 'status': latest['status'], 'pid_data': _safe_pid(latest['pid_data'])})}\n\n"
            )
        try:
            while True:
                try:
                    msg = q.get(timeout=10)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                try:
                    _sse_subscribers.remove(q)
                except ValueError:
                    pass

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@app.route("/api/offers")
def api_offers():
    with store_lock:
        result = [
            {
                "offer_id": o["offer_id"],
                "status": o["status"],
                "issued_at": o["issued_at"],
                "name": f"{o['pid_data'].get('given_name','')} {o['pid_data'].get('family_name','')}".strip(),
                "dob": o["pid_data"].get("birth_date", ""),
                "enrollment_id": o["pid_data"].get("_enrollment_id", ""),
            }
            for o in sorted(offers.values(), key=lambda x: x["issued_at"], reverse=True)
        ]
    return jsonify(result)


def _safe_pid(pid_data: dict) -> dict:
    """Return PID data safe to send to the browser (no portrait blob)."""
    return {k: v for k, v in pid_data.items() if k != "portrait" and not k.startswith("_")}


# ---------------------------------------------------------------------------
# Credential offer factory
# ---------------------------------------------------------------------------

def create_offer(pid_data: dict, source_file: str) -> str:
    """Build SD-JWT, store everything, return offer_id."""
    pid_data["issuing_country"] = ISSUER_COUNTRY
    pid_data["issuing_authority"] = ISSUER_AUTHORITY

    sd_jwt = build_pid_sd_jwt(
        pid_data=pid_data,
        issuer_url=ISSUER_URL,
        private_key=ISSUER_KEY,
        kid=KID,
    )

    offer_id = secrets.token_urlsafe(12)
    pre_auth_code = secrets.token_urlsafe(24)

    offer = {
        "offer_id": offer_id,
        "pre_auth_code": pre_auth_code,
        "pid_data": pid_data,
        "sd_jwt": sd_jwt,
        "issued_at": time.time(),
        "status": "pending",       # pending → token_issued → issued
        "source_file": source_file,
        "code_used": False,
    }

    with store_lock:
        offers[offer_id] = offer
        code_to_offer[pre_auth_code] = offer_id

    offer_uri = f"{ISSUER_URL}/offers/{offer_id}"
    qr_content = f"openid-credential-offer://?credential_offer_uri={offer_uri}"

    log.info(
        "Offer created: %s  →  %s %s",
        offer_id,
        pid_data.get("given_name", ""),
        pid_data.get("family_name", ""),
    )
    log.info("QR content: %s", qr_content)

    _broadcast(
        "new_offer",
        {
            "offer_id": offer_id,
            "status": "pending",
            "pid_data": _safe_pid(pid_data),
            "qr_url": f"{ISSUER_URL}/qr/{offer_id}.svg",
        },
    )
    return offer_id


# ---------------------------------------------------------------------------
# File system watcher
# ---------------------------------------------------------------------------

def _scan_directory():
    """
    Recursively find JSON files under WATCH_PATH.
    Handles all of these layouts:
      WATCH_PATH/YYYYMMDD/file.json
      WATCH_PATH/YYYYMMDD/subfolder/file.json
      WATCH_PATH/YYYYMMDD/subfolder/deeper/file.json
    """
    if not WATCH_PATH.exists():
        return

    for date_dir in sorted(WATCH_PATH.iterdir()):
        if not date_dir.is_dir() or not date_dir.name.isdigit():
            continue
        for json_file in date_dir.rglob("*.json"):
            fpath = str(json_file)
            if fpath in processed_files:
                continue
            _process_file(json_file)


def _process_file(json_file: Path):
    fpath = str(json_file)
    try:
        with json_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Only process FINALIZED enrollments
        if data.get("status") not in ("FINALIZED", "APPROVED", "COMPLETE"):
            log.info("Skipping %s (status=%s)", fpath, data.get("status"))
            processed_files.add(fpath)
            return

        pid_data = parse_idemia_json(data)
        offer_id = create_offer(pid_data, fpath)
        processed_files.add(fpath)
        log.info("Processed %s → offer %s", fpath, offer_id)

    except json.JSONDecodeError as e:
        log.warning("Bad JSON in %s: %s", fpath, e)
        processed_files.add(fpath)
    except Exception as e:
        log.error("Error processing %s: %s", fpath, e)


def _watcher_thread():
    log.info("Watching: %s (every %ds)", WATCH_PATH, SCAN_INTERVAL)
    while True:
        try:
            _scan_directory()
        except Exception as e:
            log.error("Watcher error: %s", e)
        time.sleep(SCAN_INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Start file watcher in background
    t = threading.Thread(target=_watcher_thread, daemon=True)
    t.start()

    print(f"\n{'='*60}")
    print(f"  EU PID Issuer Station")
    print(f"  Issuer URL : {ISSUER_URL}")
    print(f"  Watch path : {WATCH_PATH}")
    print(f"  Open UI    : http://{LOCAL_IP}:{ISSUER_PORT}")
    print(f"{'='*60}\n")

    app.run(host="0.0.0.0", port=ISSUER_PORT, debug=False, threaded=True)

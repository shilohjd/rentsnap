"""
agent_wrapper.py
----------------
Bridges RentSnap's web form -> your existing DNH analyze_unit function.
"""

import json
import os
import re
import sys
import traceback
import urllib.error
import urllib.request
from html import escape
from typing import Any, List, Optional

import markdown as md

sys.path.insert(0, os.path.dirname(__file__))
from agent import analyze_unit

HUD_FMR_BASE_URL = "https://www.huduser.gov/hudapi/public/fmr/data"
HUD_FMR_PATH_BASE_URL = "https://www.huduser.gov/hudapi/public/fmr/data/"
ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

BEDROOM_FMR_KEYS = {
    0: ("Efficiency", "efficiency", "0", "0br", "0_br", "zero_bedroom"),
    1: ("One-Bedroom", "One Bedroom", "one_bedroom", "1", "1br", "1_br"),
    2: ("Two-Bedroom", "Two Bedroom", "two_bedroom", "2", "2br", "2_br"),
    3: ("Three-Bedroom", "Three Bedroom", "three_bedroom", "3", "3br", "3_br"),
    4: ("Four-Bedroom", "Four Bedroom", "four_bedroom", "4", "4br", "4_br"),
}

BEDROOM_LABELS = {
    0: "Efficiency",
    1: "1 bedroom",
    2: "2 bedrooms",
    3: "3 bedrooms",
    4: "4 bedrooms",
}


def generate_report(
    address:       str,
    beds:          int,
    baths:         float,
    property_type: str           = "House",
    current_rent:  Optional[str] = None,
    amenities:     List[str]     = [],
) -> str:
    try:
        # Build the notes string - this is what gives the agent rich context.
        # It reads directly into the prompt Claude sees, so the more specific
        # the better for comp matching.
        notes_parts = [property_type]

        if amenities:
            notes_parts.append("Amenities: " + ", ".join(amenities))
        else:
            notes_parts.append("No special amenities listed")

        notes_parts.append("Pricing analysis via RentSnap")
        notes = " | ".join(notes_parts)

        # Parse current rent - if the landlord left it blank, use 0
        # (agent prompt will say $0/mo which signals a new pricing query)
        rent_value = 0
        if current_rent and current_rent.strip():
            try:
                rent_value = float(current_rent.replace("$", "").replace(",", "").strip())
            except ValueError:
                rent_value = 0

        unit = {
            "id":           "web-query",
            "address":      address,
            "bedrooms":     beds,
            "bathrooms":    baths,
            "current_rent": rent_value,
            "notes":        notes,
        }

        fmr_result = _get_hud_fmr(address, beds)
        raw_text = analyze_unit(unit)

        # Convert Claude's markdown output -> HTML for the results card
        report_html = md.markdown(raw_text, extensions=["tables", "nl2br"])
        return _hud_fmr_html(fmr_result) + report_html

    except Exception as e:
        traceback.print_exc()
        return _error_html(address, str(e))


def _extract_zip(address: str) -> Optional[str]:
    match = ZIP_RE.search(address or "")
    return match.group(1) if match else None


def _get_hud_fmr(address: str, beds: int) -> dict:
    zip_code = _extract_zip(address)
    selected_beds = max(0, min(int(beds or 0), 4))
    result = {
        "zip_code": zip_code,
        "bedrooms": selected_beds,
        "label": BEDROOM_LABELS.get(selected_beds, f"{selected_beds} bedrooms"),
        "rent": None,
        "error": None,
    }

    if not zip_code:
        result["error"] = "No ZIP code found in the address."
        return result

    headers = _hud_headers()
    errors = []

    for url in _hud_fmr_urls(zip_code):
        request = urllib.request.Request(url, headers=headers, method="GET")
        _log_hud_request(request)

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"{url}: {exc}")
            print(f"HUD FMR request failed: {url} -> {exc}", flush=True)
            continue

        result["rent"] = _selected_bedroom_fmr(payload, selected_beds)
        if result["rent"] is None:
            result["error"] = "HUD FMR response did not include a value for the selected bedroom count."
        return result

    result["error"] = "HUD FMR lookup unavailable: " + " | ".join(errors)
    return result


def _hud_fmr_urls(zip_code: str) -> List[str]:
    primary_url = f"{HUD_FMR_BASE_URL.rstrip('/')}/{zip_code}"
    fallback_url = f"{HUD_FMR_PATH_BASE_URL}{zip_code}"
    return list(dict.fromkeys([primary_url, fallback_url]))


def _hud_headers() -> dict:
    headers = {
        "Accept": "application/json",
        "User-Agent": "RentSnap/1.0",
    }
    token = (os.getenv("HUD_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print("HUD_API_TOKEN is not set; HUD FMR request will be sent without Authorization.", flush=True)
    return headers


def _log_hud_request(request: urllib.request.Request) -> None:
    headers = dict(request.header_items())
    logged_headers = dict(headers)
    if "Authorization" in logged_headers:
        logged_headers["Authorization"] = _redact_authorization(logged_headers["Authorization"])

    print(f"HUD FMR request URL: {request.full_url}", flush=True)
    print(f"HUD FMR request headers: {logged_headers}", flush=True)


def _redact_authorization(value: str) -> str:
    if not value.startswith("Bearer "):
        return "<redacted>"
    token = value.removeprefix("Bearer ")
    if len(token) <= 8:
        return "Bearer <redacted>"
    return f"Bearer {token[:4]}...{token[-4:]}"


def _selected_bedroom_fmr(payload: Any, beds: int) -> Optional[float]:
    target_keys = {_normalize_fmr_key(key) for key in BEDROOM_FMR_KEYS.get(beds, ())}

    def walk(value: Any) -> Optional[float]:
        if isinstance(value, dict):
            for key, item in value.items():
                if _normalize_fmr_key(str(key)) in target_keys:
                    parsed = _parse_rent(item)
                    if parsed is not None:
                        return parsed
            for item in value.values():
                parsed = walk(item)
                if parsed is not None:
                    return parsed
        elif isinstance(value, list):
            for item in value:
                parsed = walk(item)
                if parsed is not None:
                    return parsed
        return None

    return walk(payload)


def _normalize_fmr_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _parse_rent(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _hud_fmr_html(fmr_result: dict) -> str:
    zip_code = escape(fmr_result.get("zip_code") or "Not found")
    label = escape(fmr_result.get("label") or "selected bedroom count")

    if fmr_result.get("rent") is not None:
        rent = f"${fmr_result['rent']:,.0f}/mo"
        detail = f"HUD Fair Market Rent for {label} in ZIP {zip_code}"
        value_html = f"<strong>{escape(rent)}</strong>"
    else:
        detail = f"HUD Fair Market Rent for {label}"
        value_html = f"<span style=\"color:#991b1b\">{escape(fmr_result.get('error') or 'Unavailable')}</span>"

    return f"""
    <section style="border:1px solid #d9e2ec;background:#f8fbff;
                    border-radius:8px;padding:0.85rem 1rem;margin-bottom:1rem">
        <div style="font-size:0.78rem;color:#52606d;text-transform:uppercase;
                    letter-spacing:0.04em;margin-bottom:0.25rem">
            HUD Fair Market Rent
        </div>
        <div style="font-size:1rem;color:#1f2933;margin-bottom:0.2rem">
            {value_html}
        </div>
        <div style="font-size:0.82rem;color:#52606d">
            {escape(detail)}
        </div>
    </section>
    """


def _error_html(address: str, error_msg: str) -> str:
    return f"""
    <div style="padding:0.5rem 0">
        <p style="color:#C0392B;font-weight:500;margin-bottom:0.75rem">
            Something went wrong generating the report for {address}.
        </p>
        <pre style="background:#fef2f2;border:1px solid #fecaca;
                    padding:1rem;border-radius:6px;font-size:0.78rem;
                    color:#991b1b;overflow-x:auto;white-space:pre-wrap">{error_msg}</pre>
        <p style="font-size:0.82rem;color:#6B6B72;margin-top:0.75rem">
            Full traceback printed to your terminal or Railway logs.
        </p>
    </div>
    """

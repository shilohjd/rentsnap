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

HUD_FMR_STATEDATA_BASE_URL = "https://www.huduser.gov/hudapi/public/fmr/statedata"
ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
STATE_ZIP_RE = re.compile(r"(?:,|\b)\s*([A-Za-z]{2})\s+\d{5}(?:-\d{4})?\b")
US_STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

BEDROOM_FMR_KEYS = {
    0: ("Efficiency", "efficiency", "0", "0br", "0_br", "zero_bedroom", "fmr_0", "fmr0"),
    1: ("One-Bedroom", "One Bedroom", "one_bedroom", "1", "1br", "1_br", "fmr_1", "fmr1"),
    2: ("Two-Bedroom", "Two Bedroom", "two_bedroom", "2", "2br", "2_br", "fmr_2", "fmr2"),
    3: ("Three-Bedroom", "Three Bedroom", "three_bedroom", "3", "3br", "3_br", "fmr_3", "fmr3"),
    4: ("Four-Bedroom", "Four Bedroom", "four_bedroom", "4", "4br", "4_br", "fmr_4", "fmr4"),
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


def _extract_state(address: str) -> Optional[str]:
    match = STATE_ZIP_RE.search(address or "")
    if not match:
        return None

    state = match.group(1).upper()
    return state if state in US_STATE_ABBREVIATIONS else None


def _get_hud_fmr(address: str, beds: int) -> dict:
    zip_code = _extract_zip(address)
    state = _extract_state(address)
    selected_beds = max(0, min(int(beds or 0), 4))
    result = {
        "zip_code": zip_code,
        "state": state,
        "bedrooms": selected_beds,
        "label": BEDROOM_LABELS.get(selected_beds, f"{selected_beds} bedrooms"),
        "rent": None,
        "area_name": None,
        "error": None,
    }

    if not zip_code:
        result["error"] = "No ZIP code found in the address."
        return result
    if not state:
        result["error"] = "No state abbreviation found in the address."
        return result

    url = f"{HUD_FMR_STATEDATA_BASE_URL}/{state}"
    request = urllib.request.Request(url, headers=_hud_headers(), method="GET")
    _log_hud_request(request)

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"HUD FMR request failed: {url} -> {exc}", flush=True)
        result["error"] = f"HUD FMR lookup unavailable: {exc}"
        return result

    area = _find_fmr_area_for_zip(payload, zip_code)
    if not area:
        result["error"] = f"HUD FMR response did not include a county or metro area for ZIP {zip_code}."
        return result

    result["rent"] = _selected_bedroom_fmr(area, selected_beds)
    result["area_name"] = _area_name(area)
    if result["rent"] is None:
        result["error"] = "HUD FMR response did not include a value for the selected bedroom count."
    return result


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


def _find_fmr_area_for_zip(payload: Any, zip_code: str) -> Optional[dict]:
    for collection_name in ("counties", "metroareas"):
        for area in _collect_named_lists(payload, collection_name):
            if isinstance(area, dict) and _area_matches_zip(area, zip_code):
                return area
    return None


def _collect_named_lists(value: Any, target_name: str) -> List[Any]:
    matches = []
    normalized_target = _normalize_fmr_key(target_name)

    if isinstance(value, dict):
        for key, item in value.items():
            if _normalize_fmr_key(str(key)) == normalized_target and isinstance(item, list):
                matches.extend(item)
            matches.extend(_collect_named_lists(item, target_name))
    elif isinstance(value, list):
        for item in value:
            matches.extend(_collect_named_lists(item, target_name))

    return matches


def _area_matches_zip(area: dict, zip_code: str) -> bool:
    def walk(value: Any, key_hint: str = "") -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = _normalize_fmr_key(str(key))
                if "zip" in normalized_key and _value_contains_zip(item, zip_code):
                    return True
                if walk(item, normalized_key):
                    return True
        elif isinstance(value, list):
            if "zip" in key_hint and _value_contains_zip(value, zip_code):
                return True
            for item in value:
                if walk(item, key_hint):
                    return True
        elif "zip" in key_hint and _value_contains_zip(value, zip_code):
            return True
        return False

    return walk(area)


def _value_contains_zip(value: Any, zip_code: str) -> bool:
    if isinstance(value, list):
        return any(_value_contains_zip(item, zip_code) for item in value)
    if isinstance(value, dict):
        return any(_value_contains_zip(item, zip_code) for item in value.values())
    if value is None:
        return False
    return zip_code in re.findall(r"\d{5}", str(value))


def _area_name(area: dict) -> Optional[str]:
    for key in ("area_name", "areaname", "name", "county_name", "countyname", "metro_name", "metroname"):
        value = _find_first_value(area, key)
        if value:
            return str(value)
    return None


def _find_first_value(value: Any, target_key: str) -> Optional[Any]:
    normalized_target = _normalize_fmr_key(target_key)
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalize_fmr_key(str(key)) == normalized_target and item not in (None, ""):
                return item
            found = _find_first_value(item, target_key)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first_value(item, target_key)
            if found not in (None, ""):
                return found
    return None


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
    area_name = fmr_result.get("area_name")

    if fmr_result.get("rent") is not None:
        rent = f"${fmr_result['rent']:,.0f}/mo"
        detail = f"HUD Fair Market Rent for {label} in ZIP {zip_code}"
        if area_name:
            detail += f" ({area_name})"
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

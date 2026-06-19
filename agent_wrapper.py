"""
agent_wrapper.py
----------------
Bridges RentSnap's web form -> your existing DNH analyze_unit function.
"""

import re
import sys
import traceback
from html import escape
from typing import List, Optional
import os

import markdown as md

sys.path.insert(0, os.path.dirname(__file__))
from agent import analyze_unit

ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
STATE_RE = re.compile(r"\b(KY|Kentucky)\b", re.IGNORECASE)
COUNTY_RE = re.compile(r"\b([A-Za-z .'-]+?)\s+County\b", re.IGNORECASE)

BEDROOM_LABELS = {
    0: "Efficiency",
    1: "1 bedroom",
    2: "2 bedrooms",
    3: "3 bedrooms",
    4: "4 bedrooms",
}

# FY2025 HUD county-level FMR data for Kentucky. Includes Madison, Fayette,
# Jefferson, and the top 20 KY counties by HUD's 2022 population field.
KY_FY2025_FMR_BY_COUNTY = {
    "Jefferson": {"area_name": "Louisville, KY-IN HUD Metro FMR Area", "fmr_0": 1003, "fmr_1": 1094, "fmr_2": 1330, "fmr_3": 1714, "fmr_4": 1989},
    "Fayette": {"area_name": "Lexington-Fayette, KY MSA", "fmr_0": 799, "fmr_1": 982, "fmr_2": 1165, "fmr_3": 1583, "fmr_4": 1781},
    "Kenton": {"area_name": "Cincinnati, OH-KY-IN HUD Metro FMR Area", "fmr_0": 883, "fmr_1": 993, "fmr_2": 1287, "fmr_3": 1707, "fmr_4": 1885},
    "Boone": {"area_name": "Cincinnati, OH-KY-IN HUD Metro FMR Area", "fmr_0": 883, "fmr_1": 993, "fmr_2": 1287, "fmr_3": 1707, "fmr_4": 1885},
    "Warren": {"area_name": "Bowling Green, KY HUD Metro FMR Area", "fmr_0": 882, "fmr_1": 993, "fmr_2": 1173, "fmr_3": 1413, "fmr_4": 1793},
    "Hardin": {"area_name": "Elizabethtown, KY HUD Metro FMR Area", "fmr_0": 857, "fmr_1": 862, "fmr_2": 1075, "fmr_3": 1506, "fmr_4": 1805},
    "Daviess": {"area_name": "Owensboro, KY MSA", "fmr_0": 854, "fmr_1": 860, "fmr_2": 1128, "fmr_3": 1494, "fmr_4": 1496},
    "Campbell": {"area_name": "Cincinnati, OH-KY-IN HUD Metro FMR Area", "fmr_0": 883, "fmr_1": 993, "fmr_2": 1287, "fmr_3": 1707, "fmr_4": 1885},
    "Madison": {"area_name": "Madison County, KY", "fmr_0": 740, "fmr_1": 825, "fmr_2": 944, "fmr_3": 1323, "fmr_4": 1407},
    "Bullitt": {"area_name": "Louisville, KY-IN HUD Metro FMR Area", "fmr_0": 1003, "fmr_1": 1094, "fmr_2": 1330, "fmr_3": 1714, "fmr_4": 1989},
    "Christian": {"area_name": "Clarksville, TN-KY HUD Metro FMR Area", "fmr_0": 916, "fmr_1": 976, "fmr_2": 1229, "fmr_3": 1722, "fmr_4": 2064},
    "Oldham": {"area_name": "Louisville, KY-IN HUD Metro FMR Area", "fmr_0": 1003, "fmr_1": 1094, "fmr_2": 1330, "fmr_3": 1714, "fmr_4": 1989},
    "McCracken": {"area_name": "McCracken County, KY", "fmr_0": 693, "fmr_1": 781, "fmr_2": 1011, "fmr_3": 1218, "fmr_4": 1698},
    "Pulaski": {"area_name": "Pulaski County, KY", "fmr_0": 676, "fmr_1": 716, "fmr_2": 939, "fmr_3": 1131, "fmr_4": 1449},
    "Laurel": {"area_name": "Laurel County, KY", "fmr_0": 610, "fmr_1": 678, "fmr_2": 889, "fmr_3": 1118, "fmr_4": 1206},
    "Pike": {"area_name": "Pike County, KY", "fmr_0": 706, "fmr_1": 771, "fmr_2": 981, "fmr_3": 1182, "fmr_4": 1431},
    "Scott": {"area_name": "Lexington-Fayette, KY MSA", "fmr_0": 799, "fmr_1": 982, "fmr_2": 1165, "fmr_3": 1583, "fmr_4": 1781},
    "Jessamine": {"area_name": "Lexington-Fayette, KY MSA", "fmr_0": 799, "fmr_1": 982, "fmr_2": 1165, "fmr_3": 1583, "fmr_4": 1781},
    "Franklin": {"area_name": "Franklin County, KY", "fmr_0": 741, "fmr_1": 839, "fmr_2": 1064, "fmr_3": 1397, "fmr_4": 1670},
    "Boyd": {"area_name": "Huntington-Ashland, WV-KY-OH HUD Metro FMR Area", "fmr_0": 844, "fmr_1": 850, "fmr_2": 971, "fmr_3": 1259, "fmr_4": 1459},
}

KY_STATEWIDE_MEDIAN_FMR = {
    "area_name": "Kentucky statewide median",
    "fmr_0": 636,
    "fmr_1": 721,
    "fmr_2": 872,
    "fmr_3": 1187,
    "fmr_4": 1336,
}

KY_CITY_TO_COUNTY = {
    "ashland": "Boyd",
    "berea": "Madison",
    "bowling green": "Warren",
    "burlington": "Boone",
    "covington": "Kenton",
    "elizabethtown": "Hardin",
    "florence": "Boone",
    "fort thomas": "Campbell",
    "frankfort": "Franklin",
    "georgetown": "Scott",
    "hopkinsville": "Christian",
    "independence": "Kenton",
    "la grange": "Oldham",
    "lexington": "Fayette",
    "london": "Laurel",
    "louisville": "Jefferson",
    "newport": "Campbell",
    "nicholasville": "Jessamine",
    "owensboro": "Daviess",
    "paducah": "McCracken",
    "pikeville": "Pike",
    "radcliff": "Hardin",
    "richmond": "Madison",
    "shepherdsville": "Bullitt",
    "somerset": "Pulaski",
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
    return "KY" if STATE_RE.search(address or "") else None


def _get_hud_fmr(address: str, beds: int) -> dict:
    zip_code = _extract_zip(address)
    state = _extract_state(address)
    selected_beds = max(0, min(int(beds or 0), 4))
    county = _extract_kentucky_county(address) if state == "KY" else None
    fmr_data = KY_FY2025_FMR_BY_COUNTY.get(county) if county else None
    used_fallback = fmr_data is None

    if used_fallback:
        fmr_data = KY_STATEWIDE_MEDIAN_FMR

    return {
        "zip_code": zip_code,
        "state": state,
        "county": county,
        "bedrooms": selected_beds,
        "label": BEDROOM_LABELS.get(selected_beds, f"{selected_beds} bedrooms"),
        "rent": fmr_data.get(f"fmr_{selected_beds}"),
        "area_name": fmr_data.get("area_name"),
        "source_year": "FY2025",
        "used_fallback": used_fallback,
        "error": None if state == "KY" else "Static HUD FMR lookup is currently available for Kentucky only.",
    }


def _extract_kentucky_county(address: str) -> Optional[str]:
    normalized_address = _normalize_text(address)

    county_match = COUNTY_RE.search(address or "")
    if county_match:
        county = _title_county(county_match.group(1))
        if county in KY_FY2025_FMR_BY_COUNTY:
            return county

    for county in KY_FY2025_FMR_BY_COUNTY:
        if re.search(rf"\b{re.escape(county.lower())}\s+county\b", normalized_address):
            return county

    for city, county in KY_CITY_TO_COUNTY.items():
        if re.search(rf"\b{re.escape(city)}\b", normalized_address):
            return county

    return None


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _title_county(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().title()


def _hud_fmr_html(fmr_result: dict) -> str:
    zip_code = escape(fmr_result.get("zip_code") or "Not found")
    label = escape(fmr_result.get("label") or "selected bedroom count")
    area_name = fmr_result.get("area_name")
    county = fmr_result.get("county")
    source_year = escape(fmr_result.get("source_year") or "FY2025")

    if fmr_result.get("rent") is not None and not fmr_result.get("error"):
        rent = f"${fmr_result['rent']:,.0f}/mo"
        if county:
            detail = f"{source_year} HUD Fair Market Rent for {label} in {county} County, KY"
        else:
            detail = f"{source_year} HUD Fair Market Rent for {label} in Kentucky"
        if area_name:
            detail += f" ({area_name})"
        if fmr_result.get("used_fallback"):
            detail += " - statewide median fallback"
        value_html = f"<strong>{escape(rent)}</strong>"
    else:
        detail = f"{source_year} HUD Fair Market Rent for {label}"
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
            {escape(detail)}; ZIP {zip_code}
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

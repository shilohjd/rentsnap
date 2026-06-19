"""
agent_wrapper.py
----------------
Bridges RentSnap's web form → your existing DNH analyze_unit function.
"""

import os
import sys
import traceback
from typing import List, Optional
import markdown as md

sys.path.insert(0, os.path.dirname(__file__))
from agent import analyze_unit


def generate_report(
    address:       str,
    beds:          int,
    baths:         float,
    property_type: str           = "House",
    current_rent:  Optional[str] = None,
    amenities:     List[str]     = [],
) -> str:
    try:
        # Build the notes string — this is what gives the agent rich context.
        # It reads directly into the prompt Claude sees, so the more specific
        # the better for comp matching.
        notes_parts = [property_type]

        if amenities:
            notes_parts.append("Amenities: " + ", ".join(amenities))
        else:
            notes_parts.append("No special amenities listed")

        notes_parts.append("Pricing analysis via RentSnap")
        notes = " | ".join(notes_parts)

        # Parse current rent — if the landlord left it blank, use 0
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

        raw_text = analyze_unit(unit)

        # Convert Claude's markdown output → HTML for the results card
        html = md.markdown(raw_text, extensions=["tables", "nl2br"])
        return html

    except Exception as e:
        traceback.print_exc()
        return _error_html(address, str(e))


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

import os
import json
import base64
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# ---------- Gemini config ----------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAS_GEMINI = bool(GEMINI_API_KEY)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "gemini-2.0-flash:generateContent"
)

# ---------- FastAPI app ----------

app = FastAPI(title="Permit Navigation Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # prod-da domen bilan cheklasang bo'ladi
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Utils ----------

def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


def build_google_maps_link(
    origin: str,
    destination: str,
    waypoints: Optional[List[str]] = None,
    travel_mode: str = "driving",
) -> str:
    """
    Google Maps URL: origin + destination + via:waypoints.
    via: prefix => 'shu nuqta orqali majburiy o‘t' (short-cut yo‘q).
    """
    params: Dict[str, Any] = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }

    via_points: List[str] = []
    if waypoints:
        for wp in waypoints:
            wp = (wp or "").strip()
            if wp:
                via_points.append(f"via:{wp}")

    if via_points:
        # Google &urlencode ichida ham to‘g‘ri ishlaydi
        params["waypoints"] = "|".join(via_points)

    return "https://www.google.com/maps/dir/?" + urlencode(params)


def clean_gemini_text_to_json(text: str) -> dict:
    """
    Gemini text -> JSON:
    - ```json ... ``` bloklarni kesadi
    - faqat { ... } orasini oladi
    - json.loads qiladi
    """
    if not text:
        raise ValueError("empty gemini text")

    t = text.strip()

    # ```json ... ``` bo'lishi mumkin
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()

    start_idx = t.find("{")
    end_idx = t.rfind("}")
    if start_idx != -1 and end_idx != -1:
        t = t[start_idx:end_idx + 1].strip()

    return json.loads(t)


# ---------- Core LLM logic ----------

async def analyze_route_with_gemini(
    start_address: str,
    end_address: str,
    permits: Optional[List[UploadFile]],
) -> dict:
    """
    Advanced route-compliance mode.

    0) Agar permits bo'lmasa:
       - faqat adres bilan ishlaydi, LLM chaqirilmaydi.
    1) Agar permits bo'lsa:
       - ROUTE / MILES jadvali bo'yicha segmentlarni chiqaradi.
       - Har bir highway / EXIT o'z segmentiga ega bo'ladi.
       - waypoints = segmentlardagi gmaps_query’lar (tartib bilan).
       - Google Maps link 'via:' waypoints bilan quriladi
         (Google shortcut qilolmaydi).
    """

    permits = permits or []
    start_address = (start_address or "").strip()
    end_address = (end_address or "").strip()

    # --- 0) umuman permit yo'q -> faqat adreslar ---
    if not permits:
        if not (start_address and end_address):
            raise HTTPException(
                400,
                "Please provide at least one permit PDF or both starting and destination addresses.",
            )

        return {
            "origin": start_address,
            "destination": end_address,
            "notes": "No permits uploaded. Used user-provided addresses directly.",
            "used_gemini": False,
            "waypoints": [],
            "segments": [],
        }

    # --- 1) permits bor, lekin GEMINI_API_KEY yo'q ---
    if not HAS_GEMINI:
        if not (start_address and end_address):
            raise HTTPException(
                500,
                "Permits were uploaded but Gemini is not configured. "
                "Please either configure GEMINI_API_KEY or provide both addresses.",
            )

        return {
            "origin": start_address,
            "destination": end_address,
            "notes": "Permits uploaded but Gemini API key missing. Used user-provided addresses.",
            "used_gemini": False,
            "waypoints": [],
            "segments": [],
        }

    # --- 2) permits bor + Gemini bor -> full route extraction ---
    parts: List[dict] = []

    prompt = f"""
You are an expert oversize/overweight permit routing assistant.

You receive up to ~20 permit PDFs for one multi-state load.
Each permit may contain:
- Origin / Destination cities and states,
- One or more ROUTE / MILES / DISTANCE tables
  (columns like: Miles | Route | To, or similar).

The user may optionally provide:
- Global starting address A1: "{start_address or "not provided"}"
- Global final destination A2: "{end_address or "not provided"}"

Your job is to FOLLOW THE PERMIT ROUTE TABLE(S) EXACTLY, not to optimize.

ROUTING RULES (VERY IMPORTANT):
- The truck must follow the same highways, ramps and exits shown in the permit's
  route table(s). This is COMPLIANCE, not shortest-path routing.
- DO NOT choose shortcuts or alternative paths that are not in the route table.
- Every time the table changes highway, changes direction, or changes from one
  road to another (or to a ramp/exit), that is a NEW SEGMENT.
- Use the Miles / Route / To (or equivalent) lines as the single source of truth.
- If different permits describe consecutive states (e.g. ND -> SD -> IA),
  join them into ONE continuous ordered sequence of segments.
- If something is unclear and you cannot follow the permit exactly, you MUST
  still try to infer the correct junction/exit using nearby cities and mileages.
- Only if it is truly impossible to follow the permit, output an 'error'
  field in the JSON explaining why.

MAPPING RULES:
- Convert each segment into a Google Maps friendly search query that pins
  the key junction/exit or small area where that segment ends.
  Example (conceptual):
    "I-80 WB (EXIT 16)" -> "I-80 W Exit 16 interchange with I-880 near Neola, IA"
- Those search queries will be used as 'via:' waypoints in order, so Google
  is forced to follow the permitted route instead of shortcuts.
- Prefer 5–20 segments in total. If the table is extremely granular,
  you may merge small consecutive lines on the SAME highway and direction,
  but do NOT change the logical path.

OUTPUT REQUIREMENTS:
Return ONLY ONE JSON object with the following structure. Do not add markdown.

{{
  "origin": "<Google Maps friendly origin, city/state or full address>",
  "destination": "<Google Maps friendly destination, city/state or full address>",
  "notes": "Short explanation of how you derived the route and which permits/states you used.",
  "waypoints": [
    "<gmaps search query for waypoint #1 in driving order>",
    "<gmaps search query for waypoint #2>",
    "... more in order from origin to destination ..."
  ],
  "segments": [
    {{
      "order": 1,
      "state": "TX",
      "route": "I-29 SB",
      "from": "State border of South Dakota",
      "to": "I-880 EB (EXIT 71)",
      "miles": 10.5,
      "gmaps_query": "I-880 E Exit 71 interchange with I-29 near Loveland, IA"
    }},
    {{
      "order": 2,
      "state": "IA",
      "route": "I-880 EB",
      "from": "I-29 SB",
      "to": "I-80 WB (EXIT 16)",
      "miles": 22.3,
      "gmaps_query": "I-80 W Exit 16 near Neola, IA"
    }}
    // ... more segments in strict driving order ...
  ]
}}

ADDITIONAL RULES:
- 'origin' and 'destination' should be the global start and end of the ENTIRE trip,
  usually matching the first and last meaningful cities or addresses.
  Use A1/A2 as hints; if they are clearly wrong, you may refine them.
- 'waypoints' MUST list the segment.gmaps_query values in STRICT driving order from
  origin to destination, WITHOUT re-ordering by yourself afterwards.
- Do NOT include any keys other than: origin, destination, notes, waypoints, segments, error.
- The JSON must be valid and parseable. If you truly cannot follow the permit
  route, set "error": "cannot_generate_permit_exact_route: <reason>" and still
  provide your best guess for origin/destination.
"""

    parts.append({"text": prompt})

    any_pdf = False
    for idx, permit in enumerate(permits, start=1):
        content = await permit.read()
        if not content:
            continue
        any_pdf = True

        # Fayl nomi ko‘pincha state/yo‘l haqida hint beradi
        if permit.filename:
            parts.append({"text": f"FILE_{idx} name: {permit.filename}"})

        parts.append(
            {
                "inlineData": {
                    "data": pdf_to_base64(content),
                    "mimeType": "application/pdf",
                }
            }
        )

    if not any_pdf:
        if not (start_address and end_address):
            raise HTTPException(
                400,
                "Permit files are empty and addresses are missing. "
                "Provide at least addresses or valid PDFs.",
            )
        return {
            "origin": start_address,
            "destination": end_address,
            "notes": "Permit files were empty. Used user-provided addresses.",
            "used_gemini": False,
            "waypoints": [],
            "segments": [],
        }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ]
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code != 200:
        raise HTTPException(500, f"Gemini error: {resp.text}")

    try:
        resp_json = resp.json()
        raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise HTTPException(500, f"Gemini response format is invalid: {resp.text}")

    try:
        data = clean_gemini_text_to_json(raw_text)
    except Exception as e:
        raise HTTPException(500, f"Gemini did not return valid JSON: {e}")

    # Agar LLM “error” qaytarsa, baribir foydali narsasini ishlatamiz
    error_msg = (data.get("error") or "").strip() if isinstance(data, dict) else ""

    origin = (data.get("origin") or start_address).strip()
    destination = (data.get("destination") or end_address).strip()
    notes = (data.get("notes") or "").strip()

    if not notes:
        notes = "Origin/destination and route were derived from the permit route tables and user input."

    # waypoints: ro‘yxat bo‘lsa – ishlatamiz, bo‘lmasa bo‘sh
    waypoints_raw = data.get("waypoints")
    waypoints: List[str] = []
    if isinstance(waypoints_raw, list):
        for wp in waypoints_raw:
            if isinstance(wp, str) and wp.strip():
                waypoints.append(wp.strip())

    # segments: ro‘yxat bo‘lsa – pass-through, aks holda bo‘sh
    segments_raw = data.get("segments")
    segments: List[dict] = []
    if isinstance(segments_raw, list):
        for seg in segments_raw:
            if isinstance(seg, dict):
                segments.append(seg)

    # Minimal himoya: origin/destination topilmasa – bu ishlamaydi
    if not origin or not destination:
        raise HTTPException(
            500,
            f"Could not determine origin/destination from permits and addresses. LLM error: {error_msg or 'unknown'}",
        )

    if error_msg:
        # Izohga qo‘shib yuboramiz, lekin baribir yo‘lni beramiz
        notes = f"[LLM warning: {error_msg}] {notes}"

    return {
        "origin": origin,
        "destination": destination,
        "notes": notes,
        "used_gemini": True,
        "waypoints": waypoints,
        "segments": segments,
    }


# ---------- API route ----------

@app.post("/api/generate-navigation-link")
async def generate_navigation_link(
    start_address: str = Form(""),
    end_address: str = Form(""),
    travel_mode: str = Form("driving"),
    permits: Optional[List[UploadFile]] = File(None),
):
    """
    Request:
    - start_address (optional)
    - end_address (optional)
    - travel_mode: driving|walking|bicycling|transit
    - permits: 0..N PDF files (15–20+ segments supported)

    Response:
    - success, origin, destination, notes
    - google_maps_link (with via:waypoints)
    - travel_mode, used_gemini
    - waypoints[] (ordered), segments[] (full table)
    """

    allowed_modes = {"driving", "walking", "bicycling", "transit"}
    travel_mode = (travel_mode or "driving").lower()
    if travel_mode not in allowed_modes:
        travel_mode = "driving"

    data = await analyze_route_with_gemini(start_address, end_address, permits)

    origin = (data.get("origin") or "").strip()
    destination = (data.get("destination") or "").strip()
    notes = (data.get("notes") or "").strip()
    waypoints: List[str] = data.get("waypoints") or []
    segments: List[dict] = data.get("segments") or []
    used_gemini = bool(data.get("used_gemini"))

    if not origin or not destination:
        raise HTTPException(500, "Could not determine origin/destination from analysis result.")

    link = build_google_maps_link(origin, destination, waypoints=waypoints, travel_mode=travel_mode)

    return JSONResponse(
        {
            "success": True,
            "origin": origin,
            "destination": destination,
            "notes": notes,
            "google_maps_link": link,
            "travel_mode": travel_mode,
            "used_gemini": used_gemini,
            "waypoints": waypoints,
            "segments": segments,
        }
    )

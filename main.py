# import os
# import json
# import base64
# from typing import List, Optional
# from urllib.parse import urlencode

# import httpx
# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from dotenv import load_dotenv

# load_dotenv()

# # --------- Gemini config ---------

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# HAS_GEMINI = bool(GEMINI_API_KEY)

# GEMINI_API_URL = (
#     "https://generativelanguage.googleapis.com/v1/models/"
#     "gemini-2.0-flash:generateContent"
# )

# # --------- FastAPI app ---------

# app = FastAPI(title="Permit Navigation Link API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],      # demo/prototype; prod-da domen bilan cheklasang bo'ladi
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # --------- Utils ---------

# def build_google_maps_link(origin: str, destination: str, travel_mode: str = "driving") -> str:
#     params = {
#         "api": "1",
#         "origin": origin,
#         "destination": destination,
#         "travelmode": travel_mode,
#     }
#     return f"https://www.google.com/maps/dir/?{urlencode(params)}"


# def pdf_to_base64(file_bytes: bytes) -> str:
#     return base64.b64encode(file_bytes).decode("utf-8")


# async def analyze_route_with_gemini(
#     start_address: str,
#     end_address: str,
#     permits: Optional[List[UploadFile]],
# ) -> dict:
#     """
#     Logic:
#     - If NO permits:
#         - require both addresses
#         - return them directly (no Gemini).
#     - If permits exist:
#         - if no Gemini key: fall back to addresses if possible.
#         - else: call Gemini with PDFs + optional addresses.
#     """

#     permits = permits or []
#     start_address = (start_address or "").strip()
#     end_address = (end_address or "").strip()

#     # 1) No permits at all => pure address mode
#     if not permits:
#         if not (start_address and end_address):
#             raise HTTPException(
#                 400,
#                 "Please provide at least one permit PDF or both starting and destination addresses.",
#             )

#         return {
#             "origin": start_address,
#             "destination": end_address,
#             "notes": "No permits uploaded. Used user-provided addresses directly.",
#             "used_gemini": False,
#         }

#     # 2) Permits exist but Gemini is not configured
#     if not HAS_GEMINI:
#         if not (start_address and end_address):
#             raise HTTPException(
#                 500,
#                 "Permits were uploaded but Gemini is not configured. "
#                 "Please either configure GEMINI_API_KEY or provide both addresses.",
#             )

#         return {
#             "origin": start_address,
#             "destination": end_address,
#             "notes": "Permits uploaded but Gemini API key missing. Used user-provided addresses.",
#             "used_gemini": False,
#         }

#     # 3) Permits exist and Gemini is available → call Gemini
#     inline_parts = []
#     for permit in permits:
#         content = await permit.read()
#         if not content:
#             continue

#         inline_parts.append(
#             {
#                 "inlineData": {
#                     "data": pdf_to_base64(content),
#                     "mimeType": "application/pdf",
#                 }
#             }
#         )

#     if not inline_parts:
#         # All files were empty → fallback to addresses
#         if not (start_address and end_address):
#             raise HTTPException(
#                 400,
#                 "Permit files are empty and addresses are missing. "
#                 "Provide at least addresses or valid PDFs.",
#             )

#         return {
#             "origin": start_address,
#             "destination": end_address,
#             "notes": "Permit files were empty. Used user-provided addresses.",
#             "used_gemini": False,
#         }

#     prompt = f"""
# You are a senior logistics & dispatch assistant.

# You receive multiple permit PDF files (rate confirmation, TX PERMIT, CO PERMIT, etc.).
# Each permit may contain load info: PU (pickup), ORIGIN, PICKUP, DEL (delivery),
# DESTINATION, addresses, cities, and dates.

# User input (optional):
# - Starting address: "{start_address or "not provided"}"
# - Destination address: "{end_address or "not provided"}"

# Your task:
# 1) Read ALL PDFs together as ONE load.
# 2) Determine the pickup CITY/ADDRESS and STATE where the driver starts.
# 3) Determine the delivery CITY/ADDRESS and STATE where the driver finishes.
# 4) If only highway references like "5.0mi SE of SH114 & FM 718" or "2.8mi from BOONE"
#    are given, convert them into a nearest town/city + state (e.g. "Rhome, TX", "Boone, CO").
# 5) If the user-provided addresses look correct, you may keep them or slightly refine them.
# 6) Respond ONLY raw JSON:

# {{
#   "origin": "<Google Maps friendly query: city/state or address>",
#   "destination": "<Google Maps friendly query: city/state or address>",
#   "notes": "short explanation"
# }}

# No markdown. No extra keys.
# """

#     payload = {
#         "contents": [
#             {
#                 "role": "user",
#                 "parts": [
#                     {"text": prompt},
#                     *inline_parts,
#                 ],
#             }
#         ]
#     }

#     url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

#     async with httpx.AsyncClient(timeout=60) as client:
#         r = await client.post(url, json=payload)

#     if r.status_code != 200:
#         raise HTTPException(500, f"Gemini error: {r.text}")

#     try:
#         resp_json = r.json()
#         raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
#     except Exception:
#         raise HTTPException(500, f"Gemini response format is invalid: {r.text}")

#     # Clean possible ```json ... ``` wrappers
#     text = raw_text.strip()
#     if text.startswith("```"):
#         lines = text.splitlines()
#         if lines and lines[0].startswith("```"):
#             lines = lines[1:]
#         if lines and lines[-1].startswith("```"):
#             lines = lines[:-1]
#         text = "\n".join(lines).strip()

#     start_idx = text.find("{")
#     end_idx = text.rfind("}")
#     if start_idx != -1 and end_idx != -1:
#         text = text[start_idx : end_idx + 1].strip()

#     try:
#         data = json.loads(text)
#     except Exception:
#         raise HTTPException(500, f"Gemini did not return valid JSON: {text}")

#     origin = (data.get("origin") or start_address).strip()
#     destination = (data.get("destination") or end_address).strip()
#     notes = (data.get("notes") or "").strip() or "Origin/destination were determined from permits and user input."

#     return {
#         "origin": origin,
#         "destination": destination,
#         "notes": notes,
#         "used_gemini": True,
#     }


# # --------- API route ---------

# @app.post("/api/generate-navigation-link")
# async def generate_navigation_link(
#     start_address: str = Form(""),
#     end_address: str = Form(""),
#     travel_mode: str = Form("driving"),
#     permits: Optional[List[UploadFile]] = File(None),
# ):
#     """
#     Accepts:
#     - start_address (optional)
#     - end_address (optional)
#     - travel_mode: driving|walking|bicycling|transit (default: driving)
#     - permits: 0..N PDF files
#     """

#     # Normalize travel_mode
#     allowed_modes = {"driving", "walking", "bicycling", "transit"}
#     travel_mode = (travel_mode or "driving").lower()
#     if travel_mode not in allowed_modes:
#         travel_mode = "driving"

#     data = await analyze_route_with_gemini(start_address, end_address, permits)

#     origin = (data.get("origin") or "").strip()
#     destination = (data.get("destination") or "").strip()
#     notes = (data.get("notes") or "").strip()
#     used_gemini = bool(data.get("used_gemini"))

#     if not origin or not destination:
#         raise HTTPException(500, f"Could not determine origin/destination: {data}")

#     link = build_google_maps_link(origin, destination, travel_mode)

#     return JSONResponse(
#         {
#             "success": True,
#             "origin": origin,
#             "destination": destination,
#             "notes": notes,
#             "google_maps_link": link,
#             "travel_mode": travel_mode,
#             "used_gemini": used_gemini,
#         }
#     )
import os
import json
import base64
from typing import List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# --------- Gemini config ---------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAS_GEMINI = bool(GEMINI_API_KEY)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "gemini-2.0-flash:generateContent"
)

# --------- FastAPI app ---------

app = FastAPI(title="Permit Navigation Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # demo/prototype; limit domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utils ---------


def build_google_maps_link(
    origin: str,
    destination: str,
    travel_mode: str = "driving",
    waypoints: Optional[List[str]] = None,
) -> str:
    """
    Build a Google Maps directions link.
    If waypoints are provided, they are added as intermediate stops.
    """
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }

    if waypoints:
        # Google Maps supports multiple waypoints separated by "|"
        # We limit to e.g. 10 to keep URL reasonable
        cleaned = [wp for wp in waypoints if wp]
        if cleaned:
            params["waypoints"] = "|".join(cleaned[:10])

    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


def _normalize_waypoints(raw_waypoints) -> List[str]:
    """
    Normalize waypoints coming from Gemini.
    Can be:
      - list of strings
      - list of objects
      - comma separated string
    We convert everything to a clean list[str].
    """
    if not raw_waypoints:
        return []

    if isinstance(raw_waypoints, str):
        # Maybe "Amarillo, TX; Raton, NM; Pueblo, CO"
        parts = [p.strip() for p in raw_waypoints.replace(";", ",").split(",")]
        return [p for p in parts if p]

    if isinstance(raw_waypoints, list):
        cleaned = []
        for item in raw_waypoints:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    cleaned.append(text)
            elif isinstance(item, dict):
                # could be { "name": "Amarillo, TX", "note": "…" }
                name = str(item.get("name", "")).strip()
                if name:
                    cleaned.append(name)
        return cleaned

    # Fallback
    return []


# --------- Core Gemini logic ---------


async def analyze_route_with_gemini(
    start_address: str,
    end_address: str,
    permits: Optional[List[UploadFile]],
) -> dict:
    """
    Logic:
    - If NO permits:
        - require both addresses
        - return them directly (no Gemini).
    - If permits exist (N PDFs for one load):
        - if no Gemini key: fall back to addresses if possible.
        - else: call Gemini with PDFs + optional addresses.
    """

    permits = permits or []
    start_address = (start_address or "").strip()
    end_address = (end_address or "").strip()

    # 1) No permits at all => pure address mode
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
            "waypoints": [],
            "used_gemini": False,
        }

    # 2) Permits exist but Gemini is not configured
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
            "waypoints": [],
            "used_gemini": False,
        }

    # 3) Permits exist and Gemini is available → call Gemini
    parts: List[dict] = []
    any_pdf = False

    # Fayllar ro‘yxati va soni – promptga dynamic kiradi
    filenames: List[str] = []
    for p in permits:
        if p.filename:
            filenames.append(p.filename)
        else:
            filenames.append("unnamed.pdf")

    files_list_text = "\n".join(f"- {name}" for name in filenames)
    num_files = len(permits)

    # Prompt – hech qanday statik shahar yo‘q, hammasi shu request uchun dynamic
    prompt = f"""
You are a senior logistics & routing specialist for oversize/overweight permits.

You are given {num_files} permit PDF file(s) that all *probably* belong to ONE load.
The files for this request are:

{files_list_text}

User-provided hints for THIS request:
- Starting address hint: "{start_address or "not provided"}"
- Destination address hint: "{end_address or "not provided"}"

Inside the PDFs, carefully look for fields and text such as:
- "ROUTE", "ROUTING", "PERMITTED ROUTE", "PROPOSED ROUTE"
- "MILES", "TOTAL MILES", "SEGMENT MILES", "DISTANCE"
- city and state names, origin/destination terminals, pickup/delivery locations
- highway designations, junctions, mile-markers, and distance descriptions.

Work ONLY with the information in these PDFs and the optional hints above.
Do NOT assume any static example route from previous tasks. Always reason
freshly for this specific set of files.

Your tasks for THIS load:

1) Read ALL permits and infer the allowed path for the truck, using the ROUTE /
   ROUTING sections and MILES / DISTANCE information to understand direction
   and ordering of segments.

2) Determine the GLOBAL ORIGIN:
   - The earliest legal starting point on the permitted route, preferably close
     to the starting address hint if it is reasonable.

3) Determine the GLOBAL DESTINATION:
   - The final legal delivery point on the permitted route, preferably close
     to the destination address hint if it is reasonable.

4) From the permitted ROUTES and MILES, build a SMALL ORDERED list of important
   intermediate waypoints (maximum about 9 items). These should be major
   towns/cities or important junctions on the permitted route, not every minor
   turn.

5) If you see vague distance phrases such as "X miles from Y" or
   "at junction of HWY A and HWY B", map them to a nearby town/city + state
   that is suitable for a Google Maps search.

6) OUTPUT ONLY strict JSON in exactly this structure:

{{
  "origin": "<Google Maps friendly query: city/state or full address>",
  "destination": "<Google Maps friendly query: city/state or full address>",
  "waypoints": ["<city/state or address 1>", "<city/state or address 2>", "..."],
  "notes": "Short explanation of how you used the ROUTE / MILES data from these permits to choose origin, destination and waypoints."
}}

- "waypoints" MUST be an array (possibly empty).
- Do NOT include any other keys.
- Do NOT return markdown or commentary outside the JSON.
"""

    # Promptni parts ga qo'shamiz
    parts.append({"text": prompt})

    # Har bir PDF faylni dynamic tarzda qo‘shamiz
    for idx, permit in enumerate(permits, start=1):
        content = await permit.read()
        if not content:
            continue

        any_pdf = True

        if permit.filename:
            parts.append({"text": f"FILE_{idx} content (PDF):"})

        parts.append(
            {
                "inlineData": {
                    "data": pdf_to_base64(content),
                    "mimeType": "application/pdf",
                }
            }
        )

    if not any_pdf:
        # All files were empty → fallback to addresses
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
            "waypoints": [],
            "used_gemini": False,
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

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload)

    if r.status_code != 200:
        raise HTTPException(500, f"Gemini error: {r.text}")

    try:
        resp_json = r.json()
        raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise HTTPException(500, f"Gemini response format is invalid: {r.text}")

    # Clean possible ```json … ``` wrappers
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx : end_idx + 1].strip()

    try:
        data = json.loads(text)
    except Exception:
        raise HTTPException(500, f"Gemini did not return valid JSON: {text}")

    origin = (data.get("origin") or start_address).strip()
    destination = (data.get("destination") or end_address).strip()
    notes = (data.get("notes") or "").strip() or \
        "Origin/destination were determined from the permitted routes, miles and user input."

    waypoints_raw = data.get("waypoints") or []
    if not isinstance(waypoints_raw, list):
        waypoints_raw = []

    waypoints: List[str] = []
    for w in waypoints_raw:
        if isinstance(w, str) and w.strip():
            waypoints.append(w.strip())

    return {
        "origin": origin,
        "destination": destination,
        "notes": notes,
        "waypoints": waypoints,
        "used_gemini": True,
    }


# --------- API route ---------


@app.post("/api/generate-navigation-link")
async def generate_navigation_link(
    start_address: str = Form(""),
    end_address: str = Form(""),
    travel_mode: str = Form("driving"),
    permits: Optional[List[UploadFile]] = File(None),
):
    """
    Accepts:
    - start_address (optional)
    - end_address (optional)
    - travel_mode: driving|walking|bicycling|transit (default: driving)
    - permits: 0..N PDF files (15–20+ segments supported)
    """

    allowed_modes = {"driving", "walking", "bicycling", "transit"}
    travel_mode = (travel_mode or "driving").lower()
    if travel_mode not in allowed_modes:
        travel_mode = "driving"

    data = await analyze_route_with_gemini(start_address, end_address, permits)

    origin = (data.get("origin") or "").strip()
    destination = (data.get("destination") or "").strip()
    notes = (data.get("notes") or "").strip()
    used_gemini = bool(data.get("used_gemini"))
    waypoints = _normalize_waypoints(data.get("waypoints"))

    if not origin or not destination:
        raise HTTPException(500, f"Could not determine origin/destination: {data}")

    link = build_google_maps_link(origin, destination, travel_mode, waypoints)

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
        }
    )


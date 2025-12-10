# import os
# import json
# import base64
# import re
# from typing import List, Optional, Dict, Any
# from urllib.parse import urlencode

# import httpx
# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from dotenv import load_dotenv

# load_dotenv()

# # --------- mini config ---------

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# HAS_GEMINI = bool(GEMINI_API_KEY)

# GEMINI_API_URL = (
#     "https://generativelanguage.googleapis.com/v1/models/"
#     "gemini-2.0-flash:generateContent"
# )

# # --------- Google Maps config (faqat backendda saqlanadi) ---------

# GOOGLE_MAPS_EMBED_API_KEY = os.getenv("MAPS_API_KEY")
# HAS_EMBED_KEY = bool(GOOGLE_MAPS_EMBED_API_KEY)

# GOOGLE_MAPS_JS_API_KEY = os.getenv("MAPS_API_KEY")  # /api/config uchun ham shu


# # --------- FastAPI app ---------

# app = FastAPI(title="Permit Navigation Link API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # demo/prototype; prod-da domen bilan cheklash mumkin
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # --------- Utils ---------

# def pdf_to_base64(file_bytes: bytes) -> str:
#     return base64.b64encode(file_bytes).decode("utf-8")


# def _normalize_waypoints_for_directions(
#     waypoints: Optional[List[str]],
#     add_via_prefix: bool = True,
#     max_points: int = 20,
# ) -> List[str]:
#     """
#     Waypointlarni tozalash:
#     - bo'shlarini tashlab yuboradi
#     - takrorlarini olib tashlaydi
#     - kerak bo'lsa boshiga 'via:' qo'shib qo'yadi (Directions URL uchun)
#     """
#     if not waypoints:
#         return []

#     cleaned: List[str] = []
#     seen = set()

#     for w in waypoints:
#         if not w:
#             continue
#         w = str(w).strip()
#         if not w:
#             continue



#         key = w.lower()
#         if key in seen:
#             continue

#         seen.add(key)
#         cleaned.append(w)

#         if len(cleaned) >= max_points:
#             break

#     return cleaned


# STATE_CODES = {"TX", "OK", "CO", "NM", "NY", "NJ", "PA", "CT", "MA"}


# def _has_state_token(s: str) -> bool:
#     for st in STATE_CODES:
#         if re.search(rf"\b{st}\b", s):
#             return True
#     return False


# def _normalize_highway_codes(s: str) -> str:
#     """
#     BI-40D, SL-335, US-87 EFR kabi kodlarni Google Maps-friendly shaklga keltiradi.
#     Misollar:
#       BI-40D NW near Yarnall, TX -> I-40 Business near Yarnall, TX
#       SL-335 Ramp near Mayer, TX -> Loop 335 near Mayer, TX
#       US-87 EFR near Amarillo, TX -> US-87 near Amarillo, TX
#       BI40J W near Shamrock, TX -> I-40 Business near Shamrock, TX
#     """
#     t = s

#     # BI-40J / BI-40D / BI40J / BI40D → I-40 Business
#     t = re.sub(r"\bBI-?40[JD]?\b", "I-40 Business", t, flags=re.IGNORECASE)

#     # SL-335 / SL335 / SL 335 → Loop 335
#     t = re.sub(r"\bSL-?335\b", "Loop 335", t, flags=re.IGNORECASE)

#     # US-87 EFR / WFR / NFR / SFR → US-87
#     t = re.sub(r"\bUS-?87\s+(E|W|N|S)FR\b", "US-87", t, flags=re.IGNORECASE)

#     # US-287 EFR / WFR / NFR / SFR → US-287
#     t = re.sub(r"\bUS-?287\s+(E|W|N|S)FR\b", "US-287", t, flags=re.IGNORECASE)

#     # US 385 OK Line → US-385 near the Oklahoma state line, CO
#     t = re.sub(
#         r"\bUS\s*385\s+OK\s+Line\b",
#         "US-385 near the Oklahoma state line, CO",
#         t,
#         flags=re.IGNORECASE,
#     )

#     # Yonalishe suffixlar: NW, NE, SW, SE ni olib tashlaymiz
#     t = re.sub(r"\b(NW|NE|SW|SE)\b", "", t, flags=re.IGNORECASE)

#     # EFR/WFR/NFR/SFR qoldiqlari bo'lsa ham tozalaymiz
#     t = re.sub(r"\b(EFR|WFR|NFR|SFR)\b", "", t, flags=re.IGNORECASE)

#     # I-40 Business W / Loop 335 E / US-87 N kabi "yakuniy harf"ni olib tashlaymiz
#     t = re.sub(
#         r"\b(I-40 Business|Loop 335|US-87|US-287)\s+[NnEeWw]\b",
#         r"\1",
#         t,
#         flags=re.IGNORECASE,
#     )

#     # Ramp so'zini va yonidagi n/e/s/w ni kesib tashlash
#     t = re.sub(r"\bRamp\b(\s+[NnEeSs])?", "", t)

#     # Ortiqcha vergul va bo'shliqlarni tozalash
#     t = re.sub(r"\s+,", ",", t)
#     t = re.sub(r",\s+", ", ", t)
#     t = " ".join(t.split())

#     return t.strip(", ").strip()


# def postprocess_waypoints_for_gmaps(
#     raw_waypoints: Optional[List[str]],
# ) -> List[str]:
#     """
#     LLM dan kelgan waypointlarni Google Maps uchun yakuniy tozalash:
#     - 'via:' prefiksini olib tashlaydi
#     - BI-40D / SL-335 / US-87 EFR kabi kodlarni normalizatsiya qiladi
#     - 'Route1 & Route2 near City, ST' -> faqat Route1 qoldiriladi
#     - 'Ramp' kabi juda noaniq joylarni soddalashtiradi
#     - bo'sh va juda qisqa stringlarni tashlab yuboradi
#     """
#     if not raw_waypoints:
#         return []

#     cleaned: List[str] = []
#     for w in raw_waypoints:
#         if not w:
#             continue
#         s = " ".join(str(w).strip().split())

#         # 'via:' bilan kelsa – olib tashlaymiz, biz o'zimiz via: qo'shamiz
#         if s.lower().startswith("via:"):
#             s = s[4:].strip()

#         # Highway kodlarini normalizatsiya
#         s = _normalize_highway_codes(s)

#         # Agar "ROUTE1 & ROUTE2 near City, ST" bo'lsa – ROUTE2 ni olib tashlaymiz
#         # Masalan: "SH-114 & FM 718 near Rhome, TX" -> "SH-114 near Rhome, TX"
#         m = re.match(r"^(.*?)\s*&\s*([^ ]+.*?)\s+near\s+(.*)$", s, flags=re.IGNORECASE)
#         if m:
#             route1 = m.group(1).strip()
#             location = m.group(3).strip()
#             s = f"{route1} near {location}"

#         # Agar "Ramp" qolgan bo'lsa va state ham yo'q bo'lsa → ehtimol juda xom joy
#         if "Ramp" in s and not _has_state_token(s):
#             # masalan "I-684 Ramp" → "I-684"
#             s = re.sub(r"\bRamp\b.*", "", s).strip(", ").strip()

#         # juda qisqa va ma'nosiz bo'lsa – tashlab yuboramiz
#         if len(s) < 4:
#             continue

#         cleaned.append(s)

#     return cleaned


# def build_google_maps_link(
#     origin: str,
#     destination: str,
#     travel_mode: str = "driving",
#     waypoints: Optional[List[str]] = None,
# ) -> str:
#     """
#     Classic Google Maps Directions URL (fallback).
#     - origin / destination – matn
#     - waypoints – "via:...." ko‘rinishidagi ro‘yxat (max ~20 ta)
#     """
#     params = {
#         "api": "1",
#         "origin": origin,
#         "destination": destination,
#         "travelmode": travel_mode,
#     }

#     cleaned = _normalize_waypoints_for_directions(
#         waypoints,
#         add_via_prefix=True,
#         max_points=20,
#     )
#     if cleaned:
#         # `via:...|via:...` ko‘rinishidagi qator
#         params["waypoints"] = "|".join(cleaned)

#     # safe="|:" – via: va | belgilarini URL-encoding qilmaslik uchun
#     return f"https://www.google.com/maps/dir/?{urlencode(params, safe='|:')}"


# async def build_google_maps_link_smart(
#     origin: str,
#     destination: str,
#     travel_mode: str = "driving",
#     waypoints: Optional[List[str]] = None,
# ) -> str:
#     """
#     Smart Google Maps Directions URL:
#     - waypointlar avval postprocess (Ramp, via: va h.k.)
#     - agar MAPS_API_KEY bo'lsa, har bir waypointni Geocoding API orqali
#       lat,lng ga o'giramiz va 'via:lat,lng' formatida yuboramiz.
#     - agar geocoding ANIQ shu waypoint uchun topolmasa, o'sha waypointni SKIP qilamiz
#       (matn ko'rinishida via:... qilib qo'shmaymiz).
#     """

#     # 0) LLMdan kelgan waypointlarni yakuniy tozalash
#     safe_waypoints = postprocess_waypoints_for_gmaps(waypoints)

#     # Agar MAPS_API_KEY yo'q bo'lsa yoki waypoint yo'q bo'lsa – classic link
#     if not GOOGLE_MAPS_EMBED_API_KEY or not safe_waypoints:
#         return build_google_maps_link(origin, destination, travel_mode, safe_waypoints)

#     # 1) via: qo'ymagan, tozalangan waypointlar (matn ko'rinishida)
#     cleaned = _normalize_waypoints_for_directions(
#         safe_waypoints,
#         add_via_prefix=False,
#         max_points=20,
#     )
#     if not cleaned:
#         return build_google_maps_link(origin, destination, travel_mode, safe_waypoints)

#     geo_waypoints: List[str] = []

#     # 2) Har bir waypointni Geocoding API orqali lat,lng ga aylantiramiz
#     geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"

#     async with httpx.AsyncClient(timeout=20) as client:
#         for w in cleaned:
#             try:
#                 params = {
#                     "address": w,
#                     "key": GOOGLE_MAPS_EMBED_API_KEY,  # MAPS_API_KEY bilan ishlayapmiz
#                 }
#                 resp = await client.get(geocode_url, params=params)
#                 if resp.status_code != 200:
#                     # API xato bo'lsa – bu waypointni SKIP qilamiz
#                     continue

#                 j = resp.json()
#                 results = j.get("results") or []
#                 if not results:
#                     # topilmadi – SKIP
#                     continue

#                 loc = results[0]["geometry"]["location"]
#                 lat = loc.get("lat")
#                 lng = loc.get("lng")
#                 if lat is None or lng is None:
#                     # noto'g'ri format – SKIP
#                     continue

#                 # Eng toza ko'rinish: via:lat,lng
#                 geo_waypoints.append(f"via:{lat},{lng}")
#             except Exception:
#                 # Xatolarni yutamiz, lekin servisni sindirmaymiz – SKIP
#                 continue

#     # Agar geocodingdan keyin ham bo'sh bo'lib qolsa – classic link
#     if not geo_waypoints:
#         return build_google_maps_link(origin, destination, travel_mode, safe_waypoints)

#     params = {
#         "api": "1",
#         "origin": origin,
#         "destination": destination,
#         "travelmode": travel_mode,
#         # `via:lat,lng|via:lat,lng` ko'rinishida
#         "waypoints": "|".join(geo_waypoints),
#     }

#     # safe='|:,' – via: va | va lat,lng dagi vergul URL-encode bo'lmasin
#     return f"https://www.google.com/maps/dir/?{urlencode(params, safe='|:,')}"


# async def validate_directions_with_api(
#     origin: str,
#     destination: str,
#     waypoints: Optional[List[str]],
#     travel_mode: str,
# ) -> bool:
#     """
#     Google Directions API orqali tekshiradi:
#     - status == "OK" va routes[] bo'lsa → True
#     - aks holda → False (Google Maps route chizolmaydi deb hisoblaymiz)
#     """
#     if not GOOGLE_MAPS_EMBED_API_KEY:
#         # API kalit yo'q bo'lsa, validatsiya qila olmaymiz → "OK" deb qabul qilamiz
#         return True

#     safe_waypoints = postprocess_waypoints_for_gmaps(waypoints)
#     params: Dict[str, Any] = {
#         "origin": origin,
#         "destination": destination,
#         "mode": travel_mode,
#         "key": GOOGLE_MAPS_EMBED_API_KEY,
#     }
#     if safe_waypoints:
#         params["waypoints"] = "|".join(safe_waypoints)

#     url = "https://maps.googleapis.com/maps/api/directions/json"
#     async with httpx.AsyncClient(timeout=20) as client:
#         resp = await client.get(url, params=params)

#     if resp.status_code != 200:
#         return False

#     try:
#         j = resp.json()
#     except Exception:
#         return False

#     status = j.get("status")
#     routes = j.get("routes") or []
#     if status == "OK" and routes:
#         return True
#     return False


# def build_google_maps_embed_url(
#     origin: str,
#     destination: str,
#     travel_mode: str = "driving",
#     waypoints: Optional[List[str]] = None,
# ) -> Optional[str]:
#     """
#     Google Maps Embed API (iframe uchun) Directions URL.
#     Bu yerda API KEY ishlatiladi va faqat backendda qoladi.
#     Frontend faqat `map_embed_url` ni oladi.
#     """
#     if not HAS_EMBED_KEY:
#         return None

#     # Embed uchun ham waypointlarni oldin safe qilib olamiz
#     safe_waypoints = postprocess_waypoints_for_gmaps(waypoints)

#     params: Dict[str, Any] = {
#         "key": GOOGLE_MAPS_EMBED_API_KEY,
#         "origin": origin,
#         "destination": destination,
#         "mode": travel_mode,
#     }

#     # Embed Directions API uchun via: shart emas, shunchaki waypointlar yetarli
#     cleaned = _normalize_waypoints_for_directions(
#         safe_waypoints,
#         add_via_prefix=False,  # bu yerda "via:" qo‘shmaymiz
#         max_points=20,
#     )
#     if cleaned:
#         # "Wichita Falls, TX|Childress, TX|..." kabi
#         params["waypoints"] = "|".join(cleaned)

#     # `|` belgisi saqlanib qolishi uchun safe="|"
#     return f"https://www.google.com/maps/embed/v1/directions?{urlencode(params, safe='|')}"


# # --------- Gemini logika ---------

# async def analyze_route_with_gemini(
#     start_address: str,
#     end_address: str,
#     permits: Optional[List[UploadFile]],
# ) -> Dict[str, Any]:
#     """
#     Logika:
#     - Agar permits yo‘q:
#         - ikkala address ham bo‘lishi shart
#         - Gemini chaqirilmaydi.
#     - Agar permits mavjud:
#         - Gemini yo‘q bo‘lsa (API key bo‘lmasa) -> faqat addresslardan foydalanamiz.
#         - Aks holda:
#             - 15–20 ta permit PDF (multi-state, multi-segment) ni o‘qib:
#               origin / destination / waypoints / segments ni chiqaradi.
#     """

#     permits = permits or []
#     start_address = (start_address or "").strip()
#     end_address = (end_address or "").strip()

#     # 1) Umuman permit yo‘q → to‘g‘ridan-to‘g‘ri address rejimi
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
#             "waypoints": [],
#             "segments": [],
#         }

#     # 2) Permits bor, lekin GEMINI yo‘q
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
#             "waypoints": [],
#             "segments": [],
#         }

#     # 3) Permits + GEMINI → to‘liq AI tahlil
#     parts: List[dict] = []
#     any_pdf = False

#     # 🔥 Monstr prompt – ROUTE + MILES + ketma-ketlik + to‘liq segmentlar
#     prompt = f"""
# You are a senior logistics & dispatch assistant.

# You receive up to ~20 permit PDF files (TX PERMIT, CO PERMIT, Rate Confirm, etc.)
# for ONE oversize/overweight load. Each permit describes ROUTE + MILES that the
# truck is ALLOWED to travel inside that jurisdiction.

# User high-level input (optional):
# - Global starting address A1: "{start_address or "not provided"}"
# - Global final destination A2: "{end_address or "not provided"}"

# ========================
#  CORE LOGIC
# ========================

# 1) You MUST work from the PERMIT TEXT – ROUTE and MILES – not from your own idea
#    of a shortcut. Do NOT simplify or optimize the route.
#    The goal is to MATCH the permit's legal route, not the shortest one.

# 2) Build a single continuous route from A1 to A2 by stitching ALL relevant permits
#    in order (e.g., TX → OK → CO → NM → CO). Ignore any permit that clearly belongs
#    to a different, unrelated load.

# 3) CITY / STATE ORDER (VERY IMPORTANT):

#    - When you list towns / cities (for waypoints or gmaps_query), you MUST follow
#      the **actual travel order** as described in the PERMIT ROUTE and MILES text.
#    - Do NOT randomize or reorder towns by state or alphabet.
#    - Think of the trip as a timeline: TX town A → TX town B → OK town C → CO town D.
#    - Your waypoints and segments must respect this order.
#    - Do NOT invent towns, exits, or addresses that are not clearly implied by the permits.
#      Every waypoint MUST be traceable back to some ROUTE or CITY mention inside the PDFs.

# ========================
#  GOOGLE MAPS QUERY RULES
# ========================

# Your output will be consumed by a backend that calls:

#   https://www.google.com/maps/dir/?api=1
#     &origin=...
#     &destination=...
#     &waypoints=via:WAYPOINT1|via:WAYPOINT2|...

# So EVERY string in "waypoints" and every "gmaps_query" inside "segments"
# MUST be a short, Google-Maps-friendly query of ONE of these forms:

#   (A) "<ROUTE> Exit <NUMBER>, <State or City>"
#   (B) "<ROUTE> near <Town>, <State>"
#       "<ROUTE> near <Landmark>"
#       "<ROUTE1 & ROUTE2> near <Town>, <State>"
#   (C) "<house number> <street>, <City>, <State> <ZIP>, USA"

# Examples:
#   - "I-287 Exit 15, New Jersey"
#   - "I-287 Exit 9A, Brewster, NY"
#   - "US-287 near Etter, TX"
#   - "US-287 near Kerrick, TX"
#   - "I-40 Business near Shamrock, TX"
#   - "Loop 335 near Amarillo, TX"
#   - "US-385 near the Oklahoma state line, CO"
#   - "CO-96 near Boone, CO"
#   - "US-287 & SH-114 near Rhome, TX"
#   - "NY-120 near Westchester County Airport"
#   - "113 King St, Armonk, NY 10504, USA"

# IMPORTANT:
# - If an EXIT number (like "I-78 Exit 29" or "NJ-57 Exit 31") is NOT clearly in the permit text,
#   do NOT invent it. Only use EXIT numbers that are explicitly present in the PDFs.

# ========================
#  INTERNAL CODE NORMALIZATION
# ========================

# TX/CO permits use internal codes like:
# - "BI40J w [WEST 12TH STREET] (to SHAMROCK TX)"
# - "BI40D nw (to YARNALL TX)"
# - "via:BI-40D nw Yarnall, TX"
# - "SL335 Ramp n (to MAYER TX)"
# - "US87EFR n [DUMAS DRIVEEFR] (AMARILLO TX)"
# - "US287 Ramp w (to ETTER  TX)"
# - "US287WFR n", "US287EFR n"
# - "US 385 OK Line"
# - "CO-96, 2.8mi from BOONE"
# - "5.0mi SE of SH114 & FM 718 (RHOME  TX)"
# - "I-684 Ramp" or "via:I-684 Ramp"

# You MUST convert these internal notations into the CLEAN patterns above.
# NEVER keep raw codes like "BI40D", "SL335 Ramp n", "US87EFR", etc. in your
# final waypoints or gmaps_query.

# A) HIGHWAY NAME NORMALIZATION

#   - "IH40", "IH 40", "IH40NFR", "IH40 Ramp w"        → "I-40"
#   - "BI40J ...", "BI40D ...", "BI-40J ...", "BI-40D ..."  → "I-40 Business"
#   - "SL335 ...", "SL 335 ...", "SL-335 ..."          → "Loop 335"
#   - "US87EFR n", "US87WFR n", "US87 Ramp n/w/e/s"   → "US-87"
#   - "US287EFR n", "US287WFR n", "US287 Ramp w/n/e/s"→ "US-287"
#   - "US 385 OK Line"                                → "US-385 near the Oklahoma state line, CO"

# B) DROP THESE SUFFIXES FROM FINAL STRINGS

# They may appear in the permit text, but MUST NOT appear in the final
# Google query that you output:

#   - "EFR", "WFR", "NFR", "SFR"
#   - "Ramp", "Ramp n", "Ramp w", "Ramp e", "Ramp s"
#   - trailing ", n", ", w", ", e", ", s"
#   - " nw", " ne", " sw", " se"
#   - raw "OK Line" (replace with "near the Oklahoma state line, CO")
#   - leading "via:" (e.g. "via:BI-40D nw Yarnall, TX" → "I-40 Business near Yarnall, TX")

# FINAL STRINGS MUST NEVER END WITH "Ramp" OR ONLY BE "I-684 Ramp" etc.

# Concrete examples you MUST follow:

#   - "via:BI-40D nw Yarnall, TX"
#       → "I-40 Business near Yarnall, TX"
#   - "BI-40D nw (to YARNALL TX)"
#       → "I-40 Business near Yarnall, TX"
#   - "BI40J W near SHAMROCK TX"
#       → "I-40 Business near Shamrock, TX"
#   - "SL-335 Ramp n (to MAYER TX)"
#       → "Loop 335 near Mayer, TX"
#   - "US87EFR n [DUMAS DRIVEEFR] (AMARILLO TX)"
#       → "US-87 near Amarillo, TX"
#   - "US287 Ramp w (to ETTER TX)"
#       → "US-287 near Etter, TX"
#   - "US 385 OK Line"
#       → "US-385 near the Oklahoma state line, CO"
#   - "SH114 & FM 718 (RHOME TX)"
#       → "SH-114 near Rhome, TX"

# C) “TOWARDS” / RAMP-ONLY PATTERNS

# If you see patterns like:
#   - "I-87 E towards I-287 White Plains/Rye"
#   - "I-684 Ramp"
#   - "via:I-684 Ramp"

# You MUST output something like:
#   - "I-87 & I-287 near White Plains, NY"
#   - "I-684 near Brewster, NY"
#   - or "I-684 near White Plains, NY"

# General rule:
#   - Turn any "X towards Y City/Route" or "ROUTE Ramp" text into either:
#       "<ROUTE1 & ROUTE2> near <City>, <State>"
#     or:
#       "<ROUTE> near <City>, <State>"

# D) BAD vs GOOD EXAMPLES

# BAD (never output):
#   - "BI-40D nw near Yarnall, TX"
#   - "via:BI-40D nw Yarnall, TX"
#   - "SL-335 Ramp n near Mayer, TX"
#   - "US-87EFR n near Amarillo, TX"
#   - "US-287 Ramp w near Etter, TX"
#   - "US 385 OK Line"
#   - "I-87 E towards I-287 White Plains/Rye"
#   - "I-684 Ramp"

# GOOD (what you MUST output):
#   - "I-40 Business near Yarnall, TX"
#   - "I-40 Business near Shamrock, TX"
#   - "Loop 335 near Mayer, TX"  (or "Loop 335 near Amarillo, TX")
#   - "US-87 near Amarillo, TX"
#   - "US-287 near Etter, TX"
#   - "US-385 near the Oklahoma state line, CO"
#   - "I-87 & I-287 near White Plains, NY"
#   - "I-684 near Brewster, NY"

# ========================
#  JSON OUTPUT FORMAT
# ========================

# Return ONLY one JSON object, no markdown, no comments. It must be valid JSON:

#   {{
#     "origin": "<Google Maps friendly origin>",
#     "destination": "<Google Maps friendly destination>",
#     "notes": "short explanation of how you stitched the route from the permits",
#     "waypoints": [
#       "<EXIT / NEAR / ADDRESS query in strict travel order from the permits>",
#       "... up to about 15–20 items max ..."
#     ],
#     "segments": [
#       {{
#         "order": 1,
#         "state": "TX",
#         "route": "US287 N",
#         "from": "<from description from permit>",
#         "to": "<to description from permit>",
#         "miles": 90.0,
#         "gmaps_query": "<same style Google Maps query>"
#       }}
#       // additional segments in strict travel order...
#     ]
#   }}

# STRICT RULES FOR waypoints AND gmaps_query:
# - Every string MUST be exactly one of:
#     (A) "<ROUTE> Exit <NUMBER>, <State or City>"
#     (B) "<ROUTE> near <Town>, <State>"
#         "<ROUTE> near <Landmark>"
#         "<ROUTE1 & ROUTE2> near <Town>, <State>"
#     (C) a full normal address like "113 King St, Armonk, NY 10504, USA"
# - Do NOT output raw codes like "BI40D", "SL335 Ramp n", "US87EFR", "US287WFR",
#   "US 385 OK Line", "I-684 Ramp", or "towards I-287 White Plains/Rye".
# - Do NOT leave a bare code like "BI-40D nw Yarnall, TX" or "via:BI-40D nw Yarnall, TX".
#   Always convert it into a proper Google Maps query like
#   "I-40 Business near Yarnall, TX".

# The JSON MUST be syntactically valid (double quotes, no trailing commas, no ```).
# "origin" = first pickup city in the trip, aligned with A1 if reasonable.
# "destination" = final delivery city, aligned with A2 if reasonable.
# """

#     parts.append({"text": prompt})

#     # Har bir permit faylini qo‘shamiz
#     for idx, permit in enumerate(permits, start=1):
#         content = await permit.read()
#         if not content:
#             continue

#         any_pdf = True

#         if permit.filename:
#             parts.append({"text": f"FILE_{idx} name: {permit.filename}"})

#         parts.append(
#             {
#                 "inlineData": {
#                     "data": pdf_to_base64(content),
#                     "mimeType": "application/pdf",
#                 }
#             }
#         )

#     if not any_pdf:
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
#             "waypoints": [],
#             "segments": [],
#         }

#     payload = {
#         "contents": [
#             {
#                 "role": "user",
#                 "parts": parts,
#             }
#         ]
#     }

#     url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

#     async with httpx.AsyncClient(timeout=120) as client:
#         r = await client.post(url, json=payload)

#     if r.status_code != 200:
#         raise HTTPException(500, f"Gemini error: {r.text}")

#     try:
#         resp_json = r.json()
#         raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
#     except Exception:
#         raise HTTPException(500, f"Gemini response format is invalid: {r.text}")

#     # ```json ... ``` bo‘lsa, tozalab olamiz
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
#         text = text[start_idx: end_idx + 1].strip()

#     try:
#         data = json.loads(text)
#     except Exception as e:
#         raise HTTPException(
#             500,
#             f"Gemini did not return valid JSON: {e}. Raw text: {text}",
#         )

#     origin = (data.get("origin") or start_address).strip()
#     destination = (data.get("destination") or end_address).strip()
#     notes = (data.get("notes") or "").strip() or (
#         "Origin/destination were determined from permits (ROUTE+MILES) and user input."
#     )

#     waypoints = data.get("waypoints") or []
#     if not isinstance(waypoints, list):
#         waypoints = []

#     segments = data.get("segments") or []
#     if not isinstance(segments, list):
#         segments = []

#     # Agar waypoints bo‘sh bo‘lsa, segmentlardan yig‘ib olamiz
#     if not waypoints and segments:
#         try:
#             segments_sorted = sorted(
#                 segments,
#                 key=lambda s: s.get("order", 0),
#             )
#         except Exception:
#             segments_sorted = segments

#         tmp: List[str] = []
#         for seg in segments_sorted:
#             q = (seg.get("gmaps_query") or "").strip()
#             if q:
#                 tmp.append(q)
#         waypoints = tmp

#     # LLM-dan kelgan waypoint/gmaps_query’larni ham normalizatsiya qilib qo’yamiz
#     waypoints = postprocess_waypoints_for_gmaps(waypoints)

#     # segment ichidagi gmaps_querylarni ham tozalaymiz
#     for seg in segments:
#         q = (seg.get("gmaps_query") or "").strip()
#         if q:
#             cleaned_q_list = postprocess_waypoints_for_gmaps([q])
#             seg["gmaps_query"] = cleaned_q_list[0] if cleaned_q_list else q

#     return {
#         "origin": origin,
#         "destination": destination,
#         "notes": notes,
#         "used_gemini": True,
#         "waypoints": waypoints,
#         "segments": segments,
#     }


# async def refine_waypoints_with_gemini(
#     base_data: Dict[str, Any],
#     bad_link: str,
# ) -> Dict[str, Any]:
#     """
#     Directions API route topolmadi.
#     Shu uchun eski JSON (+ yomon link) ni Gemini'ga yuborib,
#     faqat waypoint/gmaps_query'larni tozalab qayta olishga urinib ko'ramiz.
#     """
#     if not HAS_GEMINI:
#         return base_data

#     # eski JSONni matnga aylantiramiz
#     prev_json_text = json.dumps(base_data, ensure_ascii=False)

#     prompt = f"""
# You previously produced the following JSON for a trucking route:

# {prev_json_text}

# Then we built this Google Maps directions link from it:
# {bad_link}

# When we called the Google Directions API with the same origin, destination,
# and waypoints, it FAILED to produce a route (status != OK).

# Your task NOW:

# 1) Keep the SAME overall route and legal logic from the permits (do NOT invent a new shortcut).
# 2) FIX ONLY:
#    - "waypoints" array
#    - and, if needed, each segment's "gmaps_query"
#    so that Google Maps Directions will be able to draw the route.

# 3) Use the SAME strict rules as before:
#    - waypoints and gmaps_query MUST be one of:
#        (A) "<ROUTE> Exit <NUMBER>, <State or City>"
#        (B) "<ROUTE> near <Town>, <State>"
#            "<ROUTE> near <Landmark>"
#            "<ROUTE1 & ROUTE2> near <Town>, <State>"
#        (C) full address like "113 King St, Armonk, NY 10504, USA"
#    - DO NOT output raw internal codes like "BI40D", "SL335 Ramp n", "US87EFR",
#      "US287WFR", "US 385 OK Line", "I-684 Ramp", or "towards I-287 White Plains/Rye".

# 4) VERY IMPORTANT:
#    - Preserve the travel order of cities/towns from the original route.
#    - If in doubt, prefer town-level waypoints (e.g. "US-287 near Etter, TX")
#      instead of complicated ramps or "5.0mi SE of ..." forms.

# Return ONLY the corrected JSON object in the SAME structure.
# """

#     payload = {
#         "contents": [
#             {
#                 "role": "user",
#                 "parts": [
#                     {"text": prompt}
#                 ],
#             }
#         ]
#     }

#     url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

#     async with httpx.AsyncClient(timeout=120) as client:
#         r = await client.post(url, json=payload)

#     if r.status_code != 200:
#         # refine urinish fail bo'lsa – eski datani qaytaramiz
#         return base_data

#     try:
#         resp_json = r.json()
#         raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
#     except Exception:
#         return base_data

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
#         text = text[start_idx: end_idx + 1].strip()

#     try:
#         new_data = json.loads(text)
#     except Exception:
#         return base_data

#     # minimal guard – agar origin/destination bo'sh bo'lib qolsa, eski datadan olamiz
#     if not (new_data.get("origin") and new_data.get("destination")):
#         new_data["origin"] = base_data.get("origin")
#         new_data["destination"] = base_data.get("destination")

#     return new_data


# async def build_link_with_retries(
#     data: Dict[str, Any],
#     travel_mode: str,
#     max_attempts: int = 3,
# ) -> Dict[str, Any]:
#     """
#     1) data (origin, destination, waypoints, segments) dan link yasaydi
#     2) Directions API bilan tekshiradi
#     3) Agar FAIL bo'lsa:
#        - bad_link va eski JSONni Gemini'ga berib waypoint/gmaps_query'larni refine qiladi
#        - qayta link yasab, yana Directions API bilan tekshiradi
#     4) max_attempts marta urunib ko'radi
#     Natijada:
#       - { "link": ..., "origin": ..., "destination": ..., "waypoints": ... } qaytaradi
#     """
#     origin = (data.get("origin") or "").strip()
#     destination = (data.get("destination") or "").strip()
#     waypoints = data.get("waypoints") or []

#     last_link = None

#     for attempt in range(max_attempts):
#         # 1) link yasaymiz
#         link = await build_google_maps_link_smart(
#             origin,
#             destination,
#             travel_mode,
#             waypoints,
#         )
#         last_link = link

#         # 2) Directions API bilan tekshiramiz
#         ok = await validate_directions_with_api(
#             origin,
#             destination,
#             waypoints,
#             travel_mode,
#         )
#         if ok:
#             # OK bo'ldi – shu linkni ishlatamiz
#             return {
#                 "link": link,
#                 "origin": origin,
#                 "destination": destination,
#                 "waypoints": waypoints,
#             }

#         # 3) FAIL bo'ldi → agar haliyam attempt qolaetgan bo'lsa, Gemini bilan refine
#         if attempt < max_attempts - 1:
#             data = await refine_waypoints_with_gemini(data, link)
#             origin = (data.get("origin") or origin).strip()
#             destination = (data.get("destination") or destination).strip()
#             waypoints = data.get("waypoints") or waypoints

#     # 3 ta urinishdan keyin ham bo'lmasa – oxirgi linkni qaytaramiz
#     return {
#         "link": last_link,
#         "origin": origin,
#         "destination": destination,
#         "waypoints": waypoints,
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
#     - permits: 0..N PDF files (15–20+ segments supported)
#     """

#     allowed_modes = {"driving", "walking", "bicycling", "transit"}
#     travel_mode = (travel_mode or "driving").lower()
#     if travel_mode not in allowed_modes:
#         travel_mode = "driving"

#     data = await analyze_route_with_gemini(start_address, end_address, permits)

#     origin = (data.get("origin") or "").strip()
#     destination = (data.get("destination") or "").strip()
#     notes = (data.get("notes") or "").strip()
#     used_gemini = bool(data.get("used_gemini"))
#     waypoints = data.get("waypoints") or []
#     segments = data.get("segments") or []

#     if not origin or not destination:
#         raise HTTPException(500, f"Could not determine origin/destination: {data}")

#     # 🔥 Linkni 3 marta attempt + background check bilan yasaymiz
#     link_result = await build_link_with_retries(
#         {
#             "origin": origin,
#             "destination": destination,
#             "notes": notes,
#             "used_gemini": used_gemini,
#             "waypoints": waypoints,
#             "segments": segments,
#         },
#         travel_mode,
#         max_attempts=3,
#     )

#     origin = link_result["origin"]
#     destination = link_result["destination"]
#     waypoints = link_result["waypoints"]
#     link = link_result["link"]

#     # iframe uchun Embed API URL (yakuniy waypointlar bilan)
#     embed_url = build_google_maps_embed_url(origin, destination, travel_mode, waypoints)

#     return JSONResponse(
#         {
#             "success": True,
#             "origin": origin,
#             "destination": destination,
#             "notes": notes,
#             "google_maps_link": link,
#             "map_embed_url": embed_url,  # frontend shu bilan preview qiladi
#             "travel_mode": travel_mode,
#             "used_gemini": used_gemini,
#             "waypoints": waypoints,
#             "segments": segments,
#         }
#     )


# @app.get("/api/config")
# def get_config():
#     return {
#         "google_maps_js_api_key": GOOGLE_MAPS_JS_API_KEY,
#     }


import os
import json
import base64
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# --------- mini config ---------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAS_GEMINI = bool(GEMINI_API_KEY)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "gemini-2.0-flash:generateContent"
)

# --------- Google Maps config (faqat backendda saqlanadi) ---------

GOOGLE_MAPS_EMBED_API_KEY = os.getenv("MAPS_API_KEY")
HAS_EMBED_KEY = bool(GOOGLE_MAPS_EMBED_API_KEY)

GOOGLE_MAPS_JS_API_KEY = os.getenv("MAPS_API_KEY")  # /api/config uchun ham shu


# --------- FastAPI app ---------

app = FastAPI(title="Permit Navigation Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo/prototype; prod-da domen bilan cheklash mumkin
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utils ---------

def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


def _normalize_waypoints_for_directions(
    waypoints: Optional[List[str]],
    add_via_prefix: bool = True,
    max_points: int = 20,
) -> List[str]:
    """
    Waypointlarni tozalash:
    - bo'shlarini tashlab yuboradi
    - takrorlarini olib tashlaydi
    - kerak bo'lsa boshiga 'via:' qo'shib qo'yadi (Directions URL uchun)
    """
    if not waypoints:
        return []

    cleaned: List[str] = []
    seen = set()

    for w in waypoints:
        if not w:
            continue
        w = str(w).strip()
        if not w:
            continue

        # if add_via_prefix and not w.lower().startswith("via:"):
        #     w = f"via:{w}"

        key = w.lower()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(w)

        if len(cleaned) >= max_points:
            break

    return cleaned


STATE_CODES = {"TX", "OK", "CO", "NM", "NY", "NJ", "PA", "CT", "MA"}


def _has_state_token(s: str) -> bool:
    for st in STATE_CODES:
        if re.search(rf"\b{st}\b", s):
            return True
    return False


def _normalize_highway_codes(s: str) -> str:
    """
    BI-40D, SL-335, US-87 EFR kabi kodlarni Google Maps-friendly shaklga keltiradi.
    Misollar:
      BI-40D NW near Yarnall, TX -> I-40 Business near Yarnall, TX
      SL-335 Ramp near Mayer, TX -> Loop 335 near Mayer, TX
      US-87 EFR near Amarillo, TX -> US-87 near Amarillo, TX
      BI40J W near Shamrock, TX -> I-40 Business near Shamrock, TX
    """
    t = s

    # BI-40J / BI-40D / BI40J / BI40D → I-40 Business
    t = re.sub(r"\bBI-?40[JD]?\b", "I-40 Business", t, flags=re.IGNORECASE)

    # SL-335 / SL335 / SL 335 → Loop 335
    t = re.sub(r"\bSL-?335\b", "Loop 335", t, flags=re.IGNORECASE)

    # US-87 EFR / WFR / NFR / SFR → US-87
    t = re.sub(r"\bUS-?87\s+(E|W|N|S)FR\b", "US-87", t, flags=re.IGNORECASE)

    # US-287 EFR / WFR / NFR / SFR → US-287
    t = re.sub(r"\bUS-?287\s+(E|W|N|S)FR\b", "US-287", t, flags=re.IGNORECASE)

    # US 385 OK Line → US-385 near the Oklahoma state line, CO
    t = re.sub(
        r"\bUS\s*385\s+OK\s+Line\b",
        "US-385 near the Oklahoma state line, CO",
        t,
        flags=re.IGNORECASE,
    )

    # Yonalishe suffixlar: NW, NE, SW, SE ni olib tashlaymiz
    t = re.sub(r"\b(NW|NE|SW|SE)\b", "", t, flags=re.IGNORECASE)

    # EFR/WFR/NFR/SFR qoldiqlari bo'lsa ham tozalaymiz
    t = re.sub(r"\b(EFR|WFR|NFR|SFR)\b", "", t, flags=re.IGNORECASE)

    # I-40 Business W / Loop 335 E / US-87 N kabi "yakuniy harf"ni olib tashlaymiz
    t = re.sub(
        r"\b(I-40 Business|Loop 335|US-87|US-287)\s+[NnEeWw]\b",
        r"\1",
        t,
        flags=re.IGNORECASE,
    )

    # Ramp so'zini va yonidagi n/e/s/w ni kesib tashlash
    t = re.sub(r"\bRamp\b(\s+[NnEeSs])?", "", t)

    # Ortiqcha vergul va bo'shliqlarni tozalash
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s+", ", ", t)
    t = " ".join(t.split())

    return t.strip(", ").strip()


def postprocess_waypoints_for_gmaps(
    raw_waypoints: Optional[List[str]],
) -> List[str]:
    """
    LLM dan kelgan waypointlarni Google Maps uchun yakuniy tozalash:
    - 'via:' prefiksini olib tashlaydi
    - BI-40D / SL-335 / US-87 EFR kabi kodlarni normalizatsiya qiladi
    - 'Route1 & Route2 near City, ST' -> faqat Route1 qoldiriladi
    - 'Ramp' kabi juda noaniq joylarni soddalashtiradi
    - bo'sh va juda qisqa stringlarni tashlab yuboradi
    """
    if not raw_waypoints:
        return []

    cleaned: List[str] = []
    for w in raw_waypoints:
        if not w:
            continue
        s = " ".join(str(w).strip().split())

        # 'via:' bilan kelsa – olib tashlaymiz, biz o'zimiz via: qo'shamiz
        if s.lower().startswith("via:"):
            s = s[4:].strip()

        # Highway kodlarini normalizatsiya
        s = _normalize_highway_codes(s)

        # Agar "ROUTE1 & ROUTE2 near City, ST" bo'lsa – ROUTE2 ni olib tashlaymiz
        # Masalan: "SH-114 & FM 718 near Rhome, TX" -> "SH-114 near Rhome, TX"
        m = re.match(r"^(.*?)\s*&\s*([^ ]+.*?)\s+near\s+(.*)$", s, flags=re.IGNORECASE)
        if m:
            route1 = m.group(1).strip()
            location = m.group(3).strip()
            s = f"{route1} near {location}"

        # Agar "Ramp" qolgan bo'lsa va state ham yo'q bo'lsa → ehtimol juda xom joy
        if "Ramp" in s and not _has_state_token(s):
            # masalan "I-684 Ramp" → "I-684"
            s = re.sub(r"\bRamp\b.*", "", s).strip(", ").strip()

        # juda qisqa va ma'nosiz bo'lsa – tashlab yuboramiz
        if len(s) < 4:
            continue

        cleaned.append(s)

    return cleaned


def build_google_maps_link(
    origin: str,
    destination: str,
    travel_mode: str = "driving",
    waypoints: Optional[List[str]] = None,
) -> str:
    """
    Classic Google Maps Directions URL (fallback).
    - origin / destination – matn
    - waypoints – "via:...." ko‘rinishidagi ro‘yxat (max ~20 ta)
    """
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }

    cleaned = _normalize_waypoints_for_directions(
        waypoints,
        add_via_prefix=True,
        max_points=20,
    )
    if cleaned:
        # `via:...|via:...` ko‘rinishidagi qator
        params["waypoints"] = "|".join(cleaned)

    # safe="|:" – via: va | belgilarini URL-encoding qilmaslik uchun
    return f"https://www.google.com/maps/dir/?{urlencode(params, safe='|:')}"


async def build_google_maps_link_smart(
    origin: str,
    destination: str,
    travel_mode: str = "driving",
    waypoints: Optional[List[str]] = None,
) -> str:
    """
    Smart Google Maps Directions URL:
    - waypointlar avval postprocess (Ramp, via: va h.k.)
    - agar MAPS_API_KEY bo'lsa, har bir waypointni Geocoding API orqali
      lat,lng ga o'giramiz va 'via:lat,lng' formatida yuboramiz.
    - agar geocoding ANIQ shu waypoint uchun topolmasa, o'sha waypointni SKIP qilamiz
      (matn ko'rinishida via:... qilib qo'shmaymiz).
    """

    # 0) LLMdan kelgan waypointlarni yakuniy tozalash
    safe_waypoints = postprocess_waypoints_for_gmaps(waypoints)

    # Agar MAPS_API_KEY yo'q bo'lsa yoki waypoint yo'q bo'lsa – classic link
    if not GOOGLE_MAPS_EMBED_API_KEY or not safe_waypoints:
        return build_google_maps_link(origin, destination, travel_mode, safe_waypoints)

    # 1) via: qo'ymagan, tozalangan waypointlar (matn ko'rinishida)
    cleaned = _normalize_waypoints_for_directions(
        safe_waypoints,
        add_via_prefix=False,
        max_points=20,
    )
    if not cleaned:
        return build_google_maps_link(origin, destination, travel_mode, safe_waypoints)

    geo_waypoints: List[str] = []

    # 2) Har bir waypointni Geocoding API orqali lat,lng ga aylantiramiz
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"

    async with httpx.AsyncClient(timeout=20) as client:
        for w in cleaned:
            try:
                params = {
                    "address": w,
                    "key": GOOGLE_MAPS_EMBED_API_KEY,  # MAPS_API_KEY bilan ishlayapmiz
                }
                resp = await client.get(geocode_url, params=params)
                if resp.status_code != 200:
                    # API xato bo'lsa – bu waypointni SKIP qilamiz
                    continue

                j = resp.json()
                results = j.get("results") or []
                if not results:
                    # topilmadi – SKIP
                    continue

                loc = results[0]["geometry"]["location"]
                lat = loc.get("lat")
                lng = loc.get("lng")
                if lat is None or lng is None:
                    # noto'g'ri format – SKIP
                    continue

                # Eng toza ko'rinish: via:lat,lng
                geo_waypoints.append(f"via:{lat},{lng}")
            except Exception:
                # Xatolarni yutamiz, lekin servisni sindirmaymiz – SKIP
                continue

    # Agar geocodingdan keyin ham bo'sh bo'lib qolsa – classic link
    if not geo_waypoints:
        return build_google_maps_link(origin, destination, travel_mode, safe_waypoints)

    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
        # `via:lat,lng|via:lat,lng` ko'rinishida
        "waypoints": "|".join(geo_waypoints),
    }

    # safe='|:,' – via: va | va lat,lng dagi vergul URL-encode bo'lmasin
    return f"https://www.google.com/maps/dir/?{urlencode(params, safe='|:,')}"


async def validate_directions_with_api(
    origin: str,
    destination: str,
    waypoints: Optional[List[str]],
    travel_mode: str,
) -> bool:
    """
    Google Directions API orqali tekshiradi:
    - status == "OK" va routes[] bo'lsa → True
    - aks holda → False (Google Maps route chizolmaydi deb hisoblaymiz)
    """
    if not GOOGLE_MAPS_EMBED_API_KEY:
        # API kalit yo'q bo'lsa, validatsiya qila olmaymiz → "OK" deb qabul qilamiz
        return True

    safe_waypoints = postprocess_waypoints_for_gmaps(waypoints)
    params: Dict[str, Any] = {
        "origin": origin,
        "destination": destination,
        "mode": travel_mode,
        "key": GOOGLE_MAPS_EMBED_API_KEY,
    }
    if safe_waypoints:
        params["waypoints"] = "|".join(safe_waypoints)

    url = "https://maps.googleapis.com/maps/api/directions/json"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params=params)

    if resp.status_code != 200:
        return False

    try:
        j = resp.json()
    except Exception:
        return False

    status = j.get("status")
    routes = j.get("routes") or []
    if status == "OK" and routes:
        return True
    return False


def build_google_maps_embed_url(
    origin: str,
    destination: str,
    travel_mode: str = "driving",
    waypoints: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Google Maps Embed API (iframe uchun) Directions URL.
    Bu yerda API KEY ishlatiladi va faqat backendda qoladi.
    Frontend faqat `map_embed_url` ni oladi.
    """
    if not HAS_EMBED_KEY:
        return None

    # Embed uchun ham waypointlarni oldin safe qilib olamiz
    safe_waypoints = postprocess_waypoints_for_gmaps(waypoints)

    params: Dict[str, Any] = {
        "key": GOOGLE_MAPS_EMBED_API_KEY,
        "origin": origin,
        "destination": destination,
        "mode": travel_mode,
    }

    # Embed Directions API uchun via: shart emas, shunchaki waypointlar yetarli
    cleaned = _normalize_waypoints_for_directions(
        safe_waypoints,
        add_via_prefix=False,  # bu yerda "via:" qo‘shmaymiz
        max_points=20,
    )
    if cleaned:
        # "Wichita Falls, TX|Childress, TX|..." kabi
        params["waypoints"] = "|".join(cleaned)

    # `|` belgisi saqlanib qolishi uchun safe="|"
    return f"https://www.google.com/maps/embed/v1/directions?{urlencode(params, safe='|')}"


# --------- Gemini logika ---------

async def analyze_route_with_gemini(
    start_address: str,
    end_address: str,
    permits: Optional[List[UploadFile]],
) -> Dict[str, Any]:
    """
    Logika:
    - Agar permits yo‘q:
        - ikkala address ham bo‘lishi shart
        - Gemini chaqirilmaydi.
    - Agar permits mavjud:
        - Gemini yo‘q bo‘lsa (API key bo‘lmasa) -> faqat addresslardan foydalanamiz.
        - Aks holda:
            - 15–20 ta permit PDF (multi-state, multi-segment) ni o‘qib:
              origin / destination / waypoints / segments ni chiqaradi.
    """

    permits = permits or []
    start_address = (start_address or "").strip()
    end_address = (end_address or "").strip()

    # 1) Umuman permit yo‘q → to‘g‘ridan-to‘g‘ri address rejimi
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

    # 2) Permits bor, lekin GEMINI yo‘q
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

    # 3) Permits + GEMINI → to‘liq AI tahlil
    parts: List[dict] = []
    any_pdf = False

    # 🔥 Monstr prompt – ROUTE + MILES + ketma-ketlik + to‘liq segmentlar
    prompt = f"""
You are a senior logistics & dispatch assistant.

You receive up to ~20 permit PDF files (TX PERMIT, CO PERMIT, Rate Confirm, etc.)
for ONE oversize/overweight load. Each permit describes ROUTE + MILES that the
truck is ALLOWED to travel inside that jurisdiction.

User high-level input (optional):
- Global starting address A1: "{start_address or "not provided"}"
- Global final destination A2: "{end_address or "not provided"}"

========================
 CORE LOGIC
========================

1) You MUST work from the PERMIT TEXT – ROUTE and MILES – not from your own idea
   of a shortcut. Do NOT simplify or optimize the route.
   The goal is to MATCH the permit's legal route, not the shortest one.

2) Build a single continuous route from A1 to A2 by stitching ALL relevant permits
   in order (e.g., TX → OK → CO → NM → CO). Ignore any permit that clearly belongs
   to a different, unrelated load.

3) CITY / STATE ORDER (VERY IMPORTANT):

   - When you list towns / cities (for waypoints or gmaps_query), you MUST follow
     the **actual travel order** as described in the PERMIT ROUTE and MILES text.
   - Do NOT randomize or reorder towns by state or alphabet.
   - Think of the trip as a timeline: TX town A → TX town B → OK town C → CO town D.
   - Your waypoints and segments must respect this order.
   - Do NOT invent towns, exits, or addresses that are not clearly implied by the permits.
     Every waypoint MUST be traceable back to some ROUTE or CITY mention inside the PDFs.

========================
 GOOGLE MAPS QUERY RULES
========================

Your output will be consumed by a backend that calls:

  https://www.google.com/maps/dir/?api=1
    &origin=...
    &destination=...
    &waypoints=via:WAYPOINT1|via:WAYPOINT2|...

So EVERY string in "waypoints" and every "gmaps_query" inside "segments"
MUST be a short, Google-Maps-friendly query of ONE of these forms:

  (A) "<ROUTE> Exit <NUMBER>, <State or City>"
  (B) "<ROUTE> near <Town>, <State>"
      "<ROUTE> near <Landmark>"
      "<ROUTE1 & ROUTE2> near <Town>, <State>"
  (C) "<house number> <street>, <City>, <State> <ZIP>, USA"

Examples:
  - "I-287 Exit 15, New Jersey"
  - "I-287 Exit 9A, Brewster, NY"
  - "US-287 near Etter, TX"
  - "US-287 near Kerrick, TX"
  - "I-40 Business near Shamrock, TX"
  - "Loop 335 near Amarillo, TX"
  - "US-385 near the Oklahoma state line, CO"
  - "CO-96 near Boone, CO"
  - "US-287 & SH-114 near Rhome, TX"
  - "NY-120 near Westchester County Airport"
  - "113 King St, Armonk, NY 10504, USA"

IMPORTANT:
- If an EXIT number (like "I-78 Exit 29" or "NJ-57 Exit 31") is NOT clearly in the permit text,
  do NOT invent it. Only use EXIT numbers that are explicitly present in the PDFs.

========================
 INTERNAL CODE NORMALIZATION
========================

TX/CO permits use internal codes like:
- "BI40J w [WEST 12TH STREET] (to SHAMROCK TX)"
- "BI40D nw (to YARNALL TX)"
- "via:BI-40D nw Yarnall, TX"
- "SL335 Ramp n (to MAYER TX)"
- "US87EFR n [DUMAS DRIVEEFR] (AMARILLO TX)"
- "US287 Ramp w (to ETTER  TX)"
- "US287WFR n", "US287EFR n"
- "US 385 OK Line"
- "CO-96, 2.8mi from BOONE"
- "5.0mi SE of SH114 & FM 718 (RHOME  TX)"
- "I-684 Ramp" or "via:I-684 Ramp"

You MUST convert these internal notations into the CLEAN patterns above.
NEVER keep raw codes like "BI40D", "SL335 Ramp n", "US87EFR", etc. in your
final waypoints or gmaps_query.

A) HIGHWAY NAME NORMALIZATION

  - "IH40", "IH 40", "IH40NFR", "IH40 Ramp w"        → "I-40"
  - "BI40J ...", "BI40D ...", "BI-40J ...", "BI-40D ..."  → "I-40 Business"
  - "SL335 ...", "SL 335 ...", "SL-335 ..."          → "Loop 335"
  - "US87EFR n", "US87WFR n", "US87 Ramp n/w/e/s"   → "US-87"
  - "US287EFR n", "US287WFR n", "US287 Ramp w/n/e/s"→ "US-287"
  - "US 385 OK Line"                                → "US-385 near the Oklahoma state line, CO"

B) DROP THESE SUFFIXES FROM FINAL STRINGS

They may appear in the permit text, but MUST NOT appear in the final
Google query that you output:

  - "EFR", "WFR", "NFR", "SFR"
  - "Ramp", "Ramp n", "Ramp w", "Ramp e", "Ramp s"
  - trailing ", n", ", w", ", e", ", s"
  - " nw", " ne", " sw", " se"
  - raw "OK Line" (replace with "near the Oklahoma state line, CO")
  - leading "via:" (e.g. "via:BI-40D nw Yarnall, TX" → "I-40 Business near Yarnall, TX")

FINAL STRINGS MUST NEVER END WITH "Ramp" OR ONLY BE "I-684 Ramp" etc.

Concrete examples you MUST follow:

  - "via:BI-40D nw Yarnall, TX"
      → "I-40 Business near Yarnall, TX"
  - "BI-40D nw (to YARNALL TX)"
      → "I-40 Business near Yarnall, TX"
  - "BI40J W near SHAMROCK TX"
      → "I-40 Business near Shamrock, TX"
  - "SL-335 Ramp n (to MAYER TX)"
      → "Loop 335 near Mayer, TX"
  - "US87EFR n [DUMAS DRIVEEFR] (AMARILLO TX)"
      → "US-87 near Amarillo, TX"
  - "US287 Ramp w (to ETTER TX)"
      → "US-287 near Etter, TX"
  - "US 385 OK Line"
      → "US-385 near the Oklahoma state line, CO"
  - "SH114 & FM 718 (RHOME TX)"
      → "SH-114 near Rhome, TX"

C) “TOWARDS” / RAMP-ONLY PATTERNS

If you see patterns like:
  - "I-87 E towards I-287 White Plains/Rye"
  - "I-684 Ramp"
  - "via:I-684 Ramp"

You MUST output something like:
  - "I-87 & I-287 near White Plains, NY"
  - "I-684 near Brewster, NY"
  - or "I-684 near White Plains, NY"

General rule:
  - Turn any "X towards Y City/Route" or "ROUTE Ramp" text into either:
      "<ROUTE1 & ROUTE2> near <City>, <State>"
    or:
      "<ROUTE> near <City>, <State>"

D) BAD vs GOOD EXAMPLES

BAD (never output):
  - "BI-40D nw near Yarnall, TX"
  - "via:BI-40D nw Yarnall, TX"
  - "SL-335 Ramp n near Mayer, TX"
  - "US-87EFR n near Amarillo, TX"
  - "US-287 Ramp w near Etter, TX"
  - "US 385 OK Line"
  - "I-87 E towards I-287 White Plains/Rye"
  - "I-684 Ramp"

GOOD (what you MUST output):
  - "I-40 Business near Yarnall, TX"
  - "I-40 Business near Shamrock, TX"
  - "Loop 335 near Mayer, TX"  (or "Loop 335 near Amarillo, TX")
  - "US-87 near Amarillo, TX"
  - "US-287 near Etter, TX"
  - "US-385 near the Oklahoma state line, CO"
  - "I-87 & I-287 near White Plains, NY"
  - "I-684 near Brewster, NY"

========================
 JSON OUTPUT FORMAT
========================

Return ONLY one JSON object, no markdown, no comments. It must be valid JSON:

  {{
    "origin": "<Google Maps friendly origin>",
    "destination": "<Google Maps friendly destination>",
    "notes": "short explanation of how you stitched the route from the permits",
    "waypoints": [
      "<EXIT / NEAR / ADDRESS query in strict travel order from the permits>",
      "... up to about 15–20 items max ..."
    ],
    "segments": [
      {{
        "order": 1,
        "state": "TX",
        "route": "US287 N",
        "from": "<from description from permit>",
        "to": "<to description from permit>",
        "miles": 90.0,
        "gmaps_query": "<same style Google Maps query>"
      }}
      // additional segments in strict travel order...
    ]
  }}

STRICT RULES FOR waypoints AND gmaps_query:
- Every string MUST be exactly one of:
    (A) "<ROUTE> Exit <NUMBER>, <State or City>"
    (B) "<ROUTE> near <Town>, <State>"
        "<ROUTE> near <Landmark>"
        "<ROUTE1 & ROUTE2> near <Town>, <State>"
    (C) a full normal address like "113 King St, Armonk, NY 10504, USA"
- Do NOT output raw codes like "BI40D", "SL335 Ramp n", "US87EFR", "US287WFR",
  "US 385 OK Line", "I-684 Ramp", or "towards I-287 White Plains/Rye".
- Do NOT leave a bare code like "BI-40D nw Yarnall, TX" or "via:BI-40D nw Yarnall, TX".
  Always convert it into a proper Google Maps query like
  "I-40 Business near Yarnall, TX".

The JSON MUST be syntactically valid (double quotes, no trailing commas, no ```).
"origin" = first pickup city in the trip, aligned with A1 if reasonable.
"destination" = final delivery city, aligned with A2 if reasonable.
"""

    parts.append({"text": prompt})

    # Har bir permit faylini qo‘shamiz
    for idx, permit in enumerate(permits, start=1):
        content = await permit.read()
        if not content:
            continue

        any_pdf = True

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

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload)

    if r.status_code != 200:
        raise HTTPException(500, f"Gemini error: {r.text}")

    try:
        resp_json = r.json()
        raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise HTTPException(500, f"Gemini response format is invalid: {r.text}")

    # ```json ... ``` bo‘lsa, tozalab olamiz
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
        text = text[start_idx: end_idx + 1].strip()

    try:
        data = json.loads(text)
    except Exception as e:
        raise HTTPException(
            500,
            f"Gemini did not return valid JSON: {e}. Raw text: {text}",
        )

    origin = (data.get("origin") or start_address).strip()
    destination = (data.get("destination") or end_address).strip()
    notes = (data.get("notes") or "").strip() or (
        "Origin/destination were determined from permits (ROUTE+MILES) and user input."
    )

    waypoints = data.get("waypoints") or []
    if not isinstance(waypoints, list):
        waypoints = []

    segments = data.get("segments") or []
    if not isinstance(segments, list):
        segments = []

    # Agar waypoints bo‘sh bo‘lsa, segmentlardan yig‘ib olamiz
    if not waypoints and segments:
        try:
            segments_sorted = sorted(
                segments,
                key=lambda s: s.get("order", 0),
            )
        except Exception:
            segments_sorted = segments

        tmp: List[str] = []
        for seg in segments_sorted:
            q = (seg.get("gmaps_query") or "").strip()
            if q:
                tmp.append(q)
        waypoints = tmp

    # LLM-dan kelgan waypoint/gmaps_query’larni ham normalizatsiya qilib qo’yamiz
    waypoints = postprocess_waypoints_for_gmaps(waypoints)

    # segment ichidagi gmaps_querylarni ham tozalaymiz
    for seg in segments:
        q = (seg.get("gmaps_query") or "").strip()
        if q:
            cleaned_q_list = postprocess_waypoints_for_gmaps([q])
            seg["gmaps_query"] = cleaned_q_list[0] if cleaned_q_list else q

    return {
        "origin": origin,
        "destination": destination,
        "notes": notes,
        "used_gemini": True,
        "waypoints": waypoints,
        "segments": segments,
    }


async def refine_waypoints_with_gemini(
    base_data: Dict[str, Any],
    bad_link: str,
) -> Dict[str, Any]:
    """
    Directions API route topolmadi.
    Shu uchun eski JSON (+ yomon link) ni Gemini'ga yuborib,
    faqat waypoint/gmaps_query'larni tozalab qayta olishga urinib ko'ramiz.
    """
    if not HAS_GEMINI:
        return base_data

    # eski JSONni matnga aylantiramiz
    prev_json_text = json.dumps(base_data, ensure_ascii=False)

    prompt = f"""
You previously produced the following JSON for a trucking route:

{prev_json_text}

Then we built this Google Maps directions link from it:
{bad_link}

When we called the Google Directions API with the same origin, destination,
and waypoints, it FAILED to produce a route (status != OK).

Your task NOW:

1) Keep the SAME overall route and legal logic from the permits (do NOT invent a new shortcut).
2) FIX ONLY:
   - "waypoints" array
   - and, if needed, each segment's "gmaps_query"
   so that Google Maps Directions will be able to draw the route.

3) Use the SAME strict rules as before:
   - waypoints and gmaps_query MUST be one of:
       (A) "<ROUTE> Exit <NUMBER>, <State or City>"
       (B) "<ROUTE> near <Town>, <State>"
           "<ROUTE> near <Landmark>"
           "<ROUTE1 & ROUTE2> near <Town>, <State>"
       (C) full address like "113 King St, Armonk, NY 10504, USA"
   - DO NOT output raw internal codes like "BI40D", "SL335 Ramp n", "US87EFR",
     "US287WFR", "US 385 OK Line", "I-684 Ramp", or "towards I-287 White Plains/Rye".

4) VERY IMPORTANT:
   - Preserve the travel order of cities/towns from the original route.
   - If in doubt, prefer town-level waypoints (e.g. "US-287 near Etter, TX")
     instead of complicated ramps or "5.0mi SE of ..." forms.

Return ONLY the corrected JSON object in the SAME structure.
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt}
                ],
            }
        ]
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload)

    if r.status_code != 200:
        # refine urinish fail bo'lsa – eski datani qaytaramiz
        return base_data

    try:
        resp_json = r.json()
        raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return base_data

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
        text = text[start_idx: end_idx + 1].strip()

    try:
        new_data = json.loads(text)
    except Exception:
        return base_data

    # minimal guard – agar origin/destination bo'sh bo'lib qolsa, eski datadan olamiz
    if not (new_data.get("origin") and new_data.get("destination")):
        new_data["origin"] = base_data.get("origin")
        new_data["destination"] = base_data.get("destination")

    return new_data


async def build_link_with_retries(
    data: Dict[str, Any],
    travel_mode: str,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """
    1) data (origin, destination, waypoints, segments) dan link yasaydi
    2) Directions API bilan tekshiradi
    3) Agar FAIL bo'lsa:
       - bad_link va eski JSONni Gemini'ga berib waypoint/gmaps_query'larni refine qiladi
       - qayta link yasab, yana Directions API bilan tekshiradi
    4) max_attempts marta urunib ko'radi
    Natijada:
      - { "link": ..., "origin": ..., "destination": ..., "waypoints": ... } qaytaradi
    """
    origin = (data.get("origin") or "").strip()
    destination = (data.get("destination") or "").strip()
    waypoints = data.get("waypoints") or []

    last_link = None

    for attempt in range(max_attempts):
        # 1) link yasaymiz
        link = await build_google_maps_link_smart(
            origin,
            destination,
            travel_mode,
            waypoints,
        )
        last_link = link

        # 2) Directions API bilan tekshiramiz
        ok = await validate_directions_with_api(
            origin,
            destination,
            waypoints,
            travel_mode,
        )
        if ok:
            # OK bo'ldi – shu linkni ishlatamiz
            return {
                "link": link,
                "origin": origin,
                "destination": destination,
                "waypoints": waypoints,
            }

        # 3) FAIL bo'ldi → agar haliyam attempt qolaetgan bo'lsa, Gemini bilan refine
        if attempt < max_attempts - 1:
            data = await refine_waypoints_with_gemini(data, link)
            origin = (data.get("origin") or origin).strip()
            destination = (data.get("destination") or destination).strip()
            waypoints = data.get("waypoints") or waypoints

    # 3 ta urinishdan keyin ham bo'lmasa – oxirgi linkni qaytaramiz
    return {
        "link": last_link,
        "origin": origin,
        "destination": destination,
        "waypoints": waypoints,
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
    waypoints = data.get("waypoints") or []
    segments = data.get("segments") or []

    if not origin or not destination:
        raise HTTPException(500, f"Could not determine origin/destination: {data}")

    # 🔥 Linkni 3 marta attempt + background check bilan yasaymiz
    link_result = await build_link_with_retries(
        {
            "origin": origin,
            "destination": destination,
            "notes": notes,
            "used_gemini": used_gemini,
            "waypoints": waypoints,
            "segments": segments,
        },
        travel_mode,
        max_attempts=3,
    )

    origin = link_result["origin"]
    destination = link_result["destination"]
    waypoints = link_result["waypoints"]
    link = link_result["link"]

    # iframe uchun Embed API URL (yakuniy waypointlar bilan)
    embed_url = build_google_maps_embed_url(origin, destination, travel_mode, waypoints)

    return JSONResponse(
        {
            "success": True,
            "origin": origin,
            "destination": destination,
            "notes": notes,
            "google_maps_link": link,
            "map_embed_url": embed_url,  # frontend shu bilan preview qiladi
            "travel_mode": travel_mode,
            "used_gemini": used_gemini,
            "waypoints": waypoints,
            "segments": segments,
        }
    )


@app.get("/api/config")
def get_config():
    return {
        "google_maps_js_api_key": GOOGLE_MAPS_JS_API_KEY,
    }

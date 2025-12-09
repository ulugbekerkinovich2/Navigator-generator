// function buildGoogleMapsDirUrl(origin, destination, waypoints, travelMode) {
//   origin = (origin || "").trim();
//   destination = (destination || "").trim();
//   if (!origin || !destination) return null;

//   const params = new URLSearchParams({
//     api: "1",
//     origin,
//     destination,
//     travelmode: (travelMode || "driving").toLowerCase(),
//   });

//   if (Array.isArray(waypoints) && waypoints.length) {
//     const cleaned = waypoints
//       .map((w) => (w || "").toString().trim())
//       .filter(Boolean)
//       .slice(0, 20)
//       .map((w) => w.replace(/^via:/i, ""));

//     if (cleaned.length) {
//       params.set("waypoints", cleaned.join("|"));
//     }
//   }

//   return `https://www.google.com/maps/dir/?${params.toString()}`;
// }

// // ===== Google Maps JS API globals =====
// let map;
// let directionsService;
// let directionsRenderer;

// // UI elementlar
// const startTextInput = document.getElementById("start-text");
// const endTextInput = document.getElementById("end-text");
// const permitsInput = document.getElementById("permits");
// const permitsLabel = document.getElementById("permits-label");
// const fileTags = document.getElementById("file-tags");

// const submitBtn = document.getElementById("submit-btn");
// const clearBtn = document.getElementById("clear-btn");
// const btnIcon = document.getElementById("btn-icon");
// const btnSpinner = document.getElementById("btn-spinner");
// const errorBox = document.getElementById("error-box");

// const emptyState = document.getElementById("empty-state");
// const resultCard = document.getElementById("result-card");
// const originText = document.getElementById("origin-text");
// const destinationText = document.getElementById("destination-text");
// const notesText = document.getElementById("notes-text");
// const mapsLink = document.getElementById("maps-link");
// const copyLinkBtn = document.getElementById("copy-link");
// const llmBadge = document.getElementById("llm-badge");

// const waypointsList = document.getElementById("waypoints-list");
// const waypointsCount = document.getElementById("waypoints-count");

// const segmentsList = document.getElementById("segments-list");
// const segmentsCount = document.getElementById("segments-count");

// const mapWrapper = document.getElementById("map-wrapper");
// const mapEmpty = document.getElementById("map-empty");

// const toggleAdvancedBtn = document.getElementById("toggle-advanced");
// const toggleAdvancedIcon = document.getElementById("toggle-advanced-icon");
// const advancedPanel = document.getElementById("advanced-panel");
// const travelModeLabel = document.getElementById("travel-mode-label");
// const travelModeButtons = document.querySelectorAll(".travel-mode-btn");

// let currentTravelMode = "driving";

// // ===== Map init (Google callback buni chaqiradi) =====
// window.initMap = function () {
//   // HTML: <div id="map-canvas" class="w-full h-full"></div>
//   const mapEl = document.getElementById("map-canvas");
//   if (!mapEl) {
//     console.error("Map element #map-canvas topilmadi");
//     return;
//   }

//   map = new google.maps.Map(mapEl, {
//     center: { lat: 39.5, lng: -98.35 },
//     zoom: 4,
//     mapTypeId: google.maps.MapTypeId.ROADMAP,
//   });

//   directionsService = new google.maps.DirectionsService();
//   directionsRenderer = new google.maps.DirectionsRenderer({
//     map,
//     suppressMarkers: false,
//     preserveViewport: false,
//     polylineOptions: {
//       strokeColor: "#22c55e", // yashil chiziq
//       strokeOpacity: 0.9,
//       strokeWeight: 4,
//     },
//   });
// };

// // ===== helpers =====

// function renderFileTags() {
//   fileTags.innerHTML = "";
//   const files = Array.from(permitsInput.files || []);
//   if (!files.length) return;

//   const maxVisible = 3;
//   files.slice(0, maxVisible).forEach((file) => {
//     const span = document.createElement("span");
//     span.className =
//       "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-200 border border-slate-600";
//     span.textContent = file.name;
//     fileTags.appendChild(span);
//   });

//   if (files.length > maxVisible) {
//     const more = document.createElement("span");
//     more.className =
//       "inline-flex items-center px-2 py-0.5 rounded-full bg-slate-900 text-slate-300 border border-dashed border-slate-600 text-[11px]";
//     more.textContent = `+${files.length - maxVisible} more`;
//     fileTags.appendChild(more);
//   }
// }

// permitsInput.addEventListener("change", () => {
//   const count = permitsInput.files.length;
//   if (!count) {
//     permitsLabel.textContent = "No files selected yet";
//   } else if (count === 1) {
//     permitsLabel.textContent = permitsInput.files[0].name;
//   } else {
//     permitsLabel.textContent = `${count} PDF files selected`;
//   }
//   renderFileTags();
// });

// function setLoading(isLoading) {
//   submitBtn.disabled = isLoading;
//   btnIcon.classList.toggle("hidden", isLoading);
//   btnSpinner.classList.toggle("hidden", !isLoading);
// }

// function resetForm() {
//   startTextInput.value = "";
//   endTextInput.value = "";
//   permitsInput.value = "";
//   permitsLabel.textContent = "No files selected yet";
//   fileTags.innerHTML = "";

//   errorBox.classList.add("hidden");
//   errorBox.textContent = "";

//   originText.textContent = "";
//   destinationText.textContent = "";
//   notesText.textContent = "";
//   llmBadge.classList.add("hidden");

//   waypointsCount.textContent = "0";
//   waypointsList.innerHTML =
//     '<span class="text-slate-500">No waypoints yet.</span>';

//   segmentsCount.textContent = "0";
//   segmentsList.innerHTML = '<p class="text-slate-500">No segments yet.</p>';

//   resultCard.classList.add("hidden");
//   emptyState.classList.remove("hidden");

//   // Mapni tozalash
//   if (directionsRenderer) {
//     directionsRenderer.set("directions", null);
//   }
//   mapWrapper.classList.add("hidden");
//   mapEmpty.classList.remove("hidden");

//   copyLinkBtn.disabled = true;
//   copyLinkBtn.textContent = "Copy link";
// }

// clearBtn.addEventListener("click", (e) => {
//   e.preventDefault();
//   resetForm();
// });

// // Advanced options toggle
// toggleAdvancedBtn.addEventListener("click", () => {
//   const isHidden = advancedPanel.classList.contains("hidden");
//   advancedPanel.classList.toggle("hidden", !isHidden);
//   toggleAdvancedIcon.textContent = isHidden ? "▾" : "▸";
//   toggleAdvancedBtn.querySelector("span:nth-child(2)").textContent = isHidden
//     ? "Hide advanced options"
//     : "Show advanced options";
// });

// // Travel mode pills
// travelModeButtons.forEach((btn) => {
//   btn.addEventListener("click", () => {
//     currentTravelMode = btn.dataset.mode || "driving";
//     travelModeButtons.forEach((b) => {
//       if (b === btn) {
//         b.classList.add(
//           "bg-blue-500",
//           "text-slate-950",
//           "font-medium",
//           "shadow-sm"
//         );
//         b.classList.remove("text-slate-200", "hover:bg-slate-800");
//       } else {
//         b.classList.remove(
//           "bg-blue-500",
//           "text-slate-950",
//           "font-medium",
//           "shadow-sm"
//         );
//         b.classList.add("text-slate-200", "hover:bg-slate-800");
//       }
//     });
//     travelModeLabel.textContent =
//       currentTravelMode.charAt(0).toUpperCase() + currentTravelMode.slice(1);
//   });
// });

// // ===== Directions chizish (JS API) =====
// function drawRouteOnMap(data, fallbackTravelMode) {
//   if (!window.google || !map || !directionsService || !directionsRenderer) {
//     console.warn("Google Maps JS API hali tayyor emas.");
//     return;
//   }

//   const origin = (data.origin || "").trim();
//   const destination = (data.destination || "").trim();
//   if (!origin || !destination) return;

//   const wps = Array.isArray(data.waypoints) ? data.waypoints : [];
//   const waypointObjects = wps
//     .slice(0, 20)
//     .map((w) => (w || "").toString().trim())
//     .filter(Boolean)
//     .map((w) => ({
//       location: w.replace(/^via:/i, ""),
//       stopover: true,
//     }));

//   const modeKey = (data.travel_mode || fallbackTravelMode || "driving")
//     .toString()
//     .toUpperCase();
//   const travelMode =
//     google.maps.TravelMode[modeKey] || google.maps.TravelMode.DRIVING;

//   const request = {
//     origin,
//     destination,
//     waypoints: waypointObjects,
//     travelMode,
//     optimizeWaypoints: false,
//   };

//   directionsService.route(request, (result, status) => {
//     if (status === "OK") {
//       directionsRenderer.setDirections(result);
//       mapEmpty.classList.add("hidden");
//       mapWrapper.classList.remove("hidden");
//     } else {
//       console.error("Directions request failed:", status);
//       mapWrapper.classList.add("hidden");
//       mapEmpty.classList.remove("hidden");
//     }
//   });
// }

// // ===== Submit handler =====
// async function handleSubmit() {
//   errorBox.classList.add("hidden");
//   errorBox.textContent = "";

//   const start = startTextInput.value.trim();
//   const end = endTextInput.value.trim();
//   const hasPermits = !!permitsInput.files.length;

//   if (!hasPermits && !(start && end)) {
//     errorBox.textContent =
//       "Please upload at least one permit PDF or provide both starting and destination addresses.";
//     errorBox.classList.remove("hidden");
//     return;
//   }

//   const formData = new FormData();
//   formData.append("start_address", start);
//   formData.append("end_address", end);
//   formData.append("travel_mode", currentTravelMode);

//   Array.from(permitsInput.files).forEach((file) => {
//     formData.append("permits", file);
//   });

//   setLoading(true);

//   try {
//     const res = await fetch(
//       "http://127.0.0.1:8003/api/generate-navigation-link",
//       {
//         method: "POST",
//         body: formData,
//       }
//     );

//     const raw = await res.text();
//     if (!raw) {
//       throw new Error("Server returned an empty response.");
//     }

//     let data;
//     try {
//       data = JSON.parse(raw);
//     } catch (e) {
//       console.error("JSON parse error. Raw:", raw);
//       throw new Error("Server did not return valid JSON.");
//     }

//     if (!res.ok || !data.success) {
//       throw new Error(data.detail || "Server error.");
//     }

//     originText.textContent = data.origin || "-";
//     destinationText.textContent = data.destination || "-";
//     notesText.textContent = data.notes || "";

//     // External Google Maps link – frontendan qayta quramiz
//     const dirUrl = buildGoogleMapsDirUrl(
//       data.origin || start,
//       data.destination || end,
//       data.waypoints || [],
//       data.travel_mode || currentTravelMode
//     );

//     mapsLink.href = dirUrl || data.google_maps_link || "#";

//     // LLMBadge (endi to'g'ri id bilan)
//     if (data.used_gemini === true) {
//       llmBadge.textContent = "LLM: Gemini (permits used)";
//       llmBadge.classList.remove("hidden");
//     } else {
//       llmBadge.textContent = "LLM: direct addresses";
//       llmBadge.classList.remove("hidden");
//     }

//     // Waypoints
//     const wps = Array.isArray(data.waypoints) ? data.waypoints : [];
//     waypointsList.innerHTML = "";
//     if (wps.length) {
//       waypointsCount.textContent = String(wps.length);
//       wps.forEach((wp, idx) => {
//         const chip = document.createElement("span");
//         chip.className =
//           "inline-flex items-center gap-1 rounded-full bg-slate-800/80 border border-slate-600/80 px-2 py-0.5 text-[11px] text-slate-100";
//         chip.innerHTML = `<span class="text-[9px] text-slate-400">${
//           idx + 1
//         }</span> ${wp}`;
//         waypointsList.appendChild(chip);
//       });
//     } else {
//       waypointsCount.textContent = "0";
//       waypointsList.innerHTML =
//         '<span class="text-slate-500">No waypoints detected – direct route.</span>';
//     }

//     // Segments
//     const segs = Array.isArray(data.segments) ? data.segments.slice() : [];
//     segmentsList.innerHTML = "";
//     if (segs.length) {
//       segs.sort((a, b) => (a.order || 0) - (b.order || 0));
//       segmentsCount.textContent = String(segs.length);

//       segs.forEach((seg) => {
//         const row = document.createElement("div");
//         row.className =
//           "flex items-start gap-2 rounded-md bg-slate-900/70 border border-slate-700/60 px-2 py-1";

//         const badge = document.createElement("span");
//         badge.className =
//           "mt-[1px] inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-800 text-[10px] text-slate-200";
//         badge.textContent = seg.order ?? "?";

//         const body = document.createElement("div");
//         body.className = "flex-1 space-y-0.5";

//         const topLine = document.createElement("div");
//         topLine.className = "flex flex-wrap items-center gap-1";
//         const state = (seg.state || "").toString().trim();
//         const route = (seg.route || "").toString().trim();
//         if (state) {
//           const s = document.createElement("span");
//           s.className =
//             "inline-flex items-center px-1.5 py-0.5 rounded-full bg-slate-800/80 text-[10px] text-slate-200 border border-slate-600/70";
//           s.textContent = state;
//           topLine.appendChild(s);
//         }
//         if (route) {
//           const r = document.createElement("span");
//           r.className = "text-[11px] font-medium text-slate-100";
//           r.textContent = route;
//           topLine.appendChild(r);
//         }

//         const midLine = document.createElement("div");
//         midLine.className = "text-[11px] text-slate-300";
//         const from = (seg.from || "").toString().trim();
//         const to = (seg.to || "").toString().trim();
//         midLine.textContent =
//           from && to ? `${from} → ${to}` : from || to || "";

//         const bottomLine = document.createElement("div");
//         bottomLine.className =
//           "flex flex-wrap items-center gap-2 text-[10px] text-slate-400";
//         if (typeof seg.miles === "number" || seg.miles) {
//           const mi = document.createElement("span");
//           mi.textContent = `Miles: ${seg.miles}`;
//           bottomLine.appendChild(mi);
//         }
//         if (seg.gmaps_query) {
//           const gq = document.createElement("span");
//           gq.textContent = seg.gmaps_query;
//           bottomLine.appendChild(gq);
//         }

//         body.appendChild(topLine);
//         if (from || to) body.appendChild(midLine);
//         if (bottomLine.childNodes.length) body.appendChild(bottomLine);

//         row.appendChild(badge);
//         row.appendChild(body);
//         segmentsList.appendChild(row);
//       });
//     } else {
//       segmentsCount.textContent = "0";
//       segmentsList.innerHTML =
//         '<p class="text-slate-500">No segments from permits.</p>';
//     }

//     emptyState.classList.add("hidden");
//     resultCard.classList.remove("hidden");

//     // Copy buttonni Google Maps linkiga qarab yoqamiz
//     copyLinkBtn.disabled = !mapsLink.href || mapsLink.href === "#";

//     // 🔥 Asosiy joy: route chizish
//     drawRouteOnMap(data, currentTravelMode);
//   } catch (err) {
//     console.error(err);
//     errorBox.textContent = err.message || "Unknown error occurred.";
//     errorBox.classList.remove("hidden");
//   } finally {
//     setLoading(false);
//   }
// }

// submitBtn.addEventListener("click", (e) => {
//   e.preventDefault();
//   handleSubmit();
// });

// // Enter bosilganda ham submit
// [startTextInput, endTextInput].forEach((input) => {
//   input.addEventListener("keydown", (e) => {
//     if (e.key === "Enter") {
//       e.preventDefault();
//       handleSubmit();
//     }
//   });
// });

// copyLinkBtn.addEventListener("click", async () => {
//   const url = mapsLink.href;
//   if (!url || url === "#" || copyLinkBtn.disabled) return;
//   try {
//     await navigator.clipboard.writeText(url);
//     copyLinkBtn.textContent = "Copied!";
//     setTimeout(() => (copyLinkBtn.textContent = "Copy link"), 1200);
//   } catch {
//     // ignore
//   }
// });


// ===== Google Maps JS API globals =====
let map;
let directionsService;
let directionsRenderer;

// UI elementlar
const startTextInput = document.getElementById("start-text");
const endTextInput = document.getElementById("end-text");
const permitsInput = document.getElementById("permits");
const permitsLabel = document.getElementById("permits-label");
const fileTags = document.getElementById("file-tags");

const submitBtn = document.getElementById("submit-btn");
const clearBtn = document.getElementById("clear-btn");
const btnIcon = document.getElementById("btn-icon");
const btnSpinner = document.getElementById("btn-spinner");
const errorBox = document.getElementById("error-box");

const emptyState = document.getElementById("empty-state");
const resultCard = document.getElementById("result-card");
const originText = document.getElementById("origin-text");
const destinationText = document.getElementById("destination-text");
const notesText = document.getElementById("notes-text");
const mapsLink = document.getElementById("maps-link");
const copyLinkBtn = document.getElementById("copy-link");
const llmBadge = document.getElementById("llm-badge");

const waypointsList = document.getElementById("waypoints-list");
const waypointsCount = document.getElementById("waypoints-count");

const segmentsList = document.getElementById("segments-list");
const segmentsCount = document.getElementById("segments-count");

const mapWrapper = document.getElementById("map-wrapper");
const mapEmpty = document.getElementById("map-empty");

const toggleAdvancedBtn = document.getElementById("toggle-advanced");
const toggleAdvancedIcon = document.getElementById("toggle-advanced-icon");
const advancedPanel = document.getElementById("advanced-panel");
const travelModeLabel = document.getElementById("travel-mode-label");
const travelModeButtons = document.querySelectorAll(".travel-mode-btn");

let currentTravelMode = "driving";

// ===== initMap — Google callback =====
window.initMap = function () {
  const canvas = document.getElementById("map-canvas");
  if (!canvas) {
    console.error("map-canvas element not found");
    return;
  }

  map = new google.maps.Map(canvas, {
    center: { lat: 39.5, lng: -98.35 },
    zoom: 4,
    mapTypeId: google.maps.MapTypeId.ROADMAP,
  });

  directionsService = new google.maps.DirectionsService();
  directionsRenderer = new google.maps.DirectionsRenderer({
    map,
    suppressMarkers: false,
    preserveViewport: false,
    polylineOptions: {
      strokeColor: "#22c55e",
      strokeOpacity: 0.9,
      strokeWeight: 4,
    },
  });
};

// ===== helpers =====

function renderFileTags() {
  fileTags.innerHTML = "";
  const files = Array.from(permitsInput.files || []);
  if (!files.length) return;

  const maxVisible = 3;
  files.slice(0, maxVisible).forEach((file) => {
    const span = document.createElement("span");
    span.className =
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-200 border border-slate-600";
    span.textContent = file.name;
    fileTags.appendChild(span);
  });

  if (files.length > maxVisible) {
    const more = document.createElement("span");
    more.className =
      "inline-flex items-center px-2 py-0.5 rounded-full bg-slate-900 text-slate-300 border border-dashed border-slate-600 text-[11px]";
    more.textContent = `+${files.length - maxVisible} more`;
    fileTags.appendChild(more);
  }
}

permitsInput.addEventListener("change", () => {
  const count = permitsInput.files.length;
  if (!count) {
    permitsLabel.textContent = "No files selected yet";
  } else if (count === 1) {
    permitsLabel.textContent = permitsInput.files[0].name;
  } else {
    permitsLabel.textContent = `${count} PDF files selected`;
  }
  renderFileTags();
});

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  btnIcon.classList.toggle("hidden", isLoading);
  btnSpinner.classList.toggle("hidden", !isLoading);
}

function resetForm() {
  startTextInput.value = "";
  endTextInput.value = "";
  permitsInput.value = "";
  permitsLabel.textContent = "No files selected yet";
  fileTags.innerHTML = "";

  errorBox.classList.add("hidden");
  errorBox.textContent = "";

  originText.textContent = "";
  destinationText.textContent = "";
  notesText.textContent = "";
  llmBadge.classList.add("hidden");

  waypointsCount.textContent = "0";
  waypointsList.innerHTML =
    '<span class="text-slate-500">No waypoints yet.</span>';

  segmentsCount.textContent = "0";
  segmentsList.innerHTML = '<p class="text-slate-500">No segments yet.</p>';

  resultCard.classList.add("hidden");
  emptyState.classList.remove("hidden");

  if (directionsRenderer) {
    directionsRenderer.setDirections({ routes: [] });
  }
  mapWrapper.classList.add("hidden");
  mapEmpty.classList.remove("hidden");

  copyLinkBtn.disabled = true;
  copyLinkBtn.textContent = "Copy link";
}

clearBtn.addEventListener("click", (e) => {
  e.preventDefault();
  resetForm();
});

// Advanced options toggle
toggleAdvancedBtn.addEventListener("click", () => {
  const isHidden = advancedPanel.classList.contains("hidden");
  advancedPanel.classList.toggle("hidden", !isHidden);
  toggleAdvancedIcon.textContent = isHidden ? "▾" : "▸";
  toggleAdvancedBtn.querySelector("span:nth-child(2)").textContent = isHidden
    ? "Hide advanced options"
    : "Show advanced options";
});

// Travel mode pills
travelModeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    currentTravelMode = btn.dataset.mode || "driving";
    travelModeButtons.forEach((b) => {
      if (b === btn) {
        b.classList.add(
          "bg-blue-500",
          "text-slate-950",
          "font-medium",
          "shadow-sm"
        );
        b.classList.remove("text-slate-200", "hover:bg-slate-800");
      } else {
        b.classList.remove(
          "bg-blue-500",
          "text-slate-950",
          "font-medium",
          "shadow-sm"
        );
        b.classList.add("text-slate-200", "hover:bg-slate-800");
      }
    });
    travelModeLabel.textContent =
      currentTravelMode.charAt(0).toUpperCase() + currentTravelMode.slice(1);
  });
});

// ===== Directions chizish (JS API) =====
function drawRouteOnMap(data, fallbackTravelMode) {
  if (!window.google || !map || !directionsService || !directionsRenderer) {
    console.warn("Google Maps JS API is not ready yet.");
    return;
  }

  const origin = (data.origin || "").trim();
  const destination = (data.destination || "").trim();
  if (!origin || !destination) return;

  const wps = Array.isArray(data.waypoints) ? data.waypoints : [];
  const waypointObjects = wps
    .slice(0, 20)
    .map((w) => (w || "").toString().trim())
    .filter(Boolean)
    .map((w) => ({
      location: w.replace(/^via:/i, ""),
      stopover: true,
    }));

  const modeKey = (data.travel_mode || fallbackTravelMode || "driving")
    .toString()
    .toUpperCase();
  const travelMode =
    google.maps.TravelMode[modeKey] || google.maps.TravelMode.DRIVING;

  const request = {
    origin,
    destination,
    waypoints: waypointObjects,
    travelMode,
    optimizeWaypoints: false,
  };

  directionsService.route(request, (result, status) => {
    if (status === "OK") {
      directionsRenderer.setDirections(result);
      mapEmpty.classList.add("hidden");
      mapWrapper.classList.remove("hidden");
    } else {
      console.error("Directions request failed:", status);
      mapWrapper.classList.add("hidden");
      mapEmpty.classList.remove("hidden");
    }
  });
}

// ===== Submit handler =====
async function handleSubmit() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";

  const start = startTextInput.value.trim();
  const end = endTextInput.value.trim();
  const hasPermits = !!permitsInput.files.length;

  if (!hasPermits && !(start && end)) {
    errorBox.textContent =
      "Please upload at least one permit PDF or provide both starting and destination addresses.";
    errorBox.classList.remove("hidden");
    return;
  }

  const formData = new FormData();
  formData.append("start_address", start);
  formData.append("end_address", end);
  formData.append("travel_mode", currentTravelMode);

  Array.from(permitsInput.files).forEach((file) => {
    formData.append("permits", file);
  });

  setLoading(true);

  try {
    const res = await fetch(
      "https://nav-api.misterdev.uz/api/generate-navigation-link",
      {
        method: "POST",
        body: formData,
      }
    );

    const raw = await res.text();
    if (!raw) {
      throw new Error("Server returned an empty response.");
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      console.error("JSON parse error. Raw:", raw);
      throw new Error("Server did not return valid JSON.");
    }

    if (!res.ok || !data.success) {
      throw new Error(data.detail || "Server error.");
    }

    originText.textContent = data.origin || "-";
    destinationText.textContent = data.destination || "-";
    notesText.textContent = data.notes || "";

    mapsLink.href = data.google_maps_link || "#";

    if (data.used_gemini === true) {
      llmBadge.textContent = "LLM: Gemini (permits used)";
      llmBadge.classList.remove("hidden");
    } else {
      llmBadge.textContent = "LLM: direct addresses";
      llmBadge.classList.remove("hidden");
    }

    // Waypoints
    const wps = Array.isArray(data.waypoints) ? data.waypoints : [];
    waypointsList.innerHTML = "";
    if (wps.length) {
      waypointsCount.textContent = wps.length;
      wps.forEach((wp, idx) => {
        const chip = document.createElement("span");
        chip.className =
          "inline-flex items-center gap-1 rounded-full bg-slate-800/80 border border-slate-600/80 px-2 py-0.5 text-[11px] text-slate-100";
        chip.innerHTML = `<span class="text-[9px] text-slate-400">${
          idx + 1
        }</span> ${wp}`;
        waypointsList.appendChild(chip);
      });
    } else {
      waypointsCount.textContent = "0";
      waypointsList.innerHTML =
        '<span class="text-slate-500">No waypoints detected – direct route.</span>';
    }

    // Segments
    const segs = Array.isArray(data.segments) ? data.segments.slice() : [];
    segmentsList.innerHTML = "";
    if (segs.length) {
      segs.sort((a, b) => (a.order || 0) - (b.order || 0));
      segmentsCount.textContent = segs.length;

      segs.forEach((seg) => {
        const row = document.createElement("div");
        row.className =
          "flex items-start gap-2 rounded-md bg-slate-900/70 border border-slate-700/60 px-2 py-1";

        const badge = document.createElement("span");
        badge.className =
          "mt-[1px] inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-800 text-[10px] text-slate-200";
        badge.textContent = seg.order ?? "?";

        const body = document.createElement("div");
        body.className = "flex-1 space-y-0.5";

        const topLine = document.createElement("div");
        topLine.className = "flex flex-wrap items-center gap-1";
        const state = (seg.state || "").toString().trim();
        const route = (seg.route || "").toString().trim();
        if (state) {
          const s = document.createElement("span");
          s.className =
            "inline-flex items-center px-1.5 py-0.5 rounded-full bg-slate-800/80 text-[10px] text-slate-200 border border-slate-600/70";
          s.textContent = state;
          topLine.appendChild(s);
        }
        if (route) {
          const r = document.createElement("span");
          r.className = "text-[11px] font-medium text-slate-100";
          r.textContent = route;
          topLine.appendChild(r);
        }

        const midLine = document.createElement("div");
        midLine.className = "text-[11px] text-slate-300";
        const from = (seg.from || "").toString().trim();
        const to = (seg.to || "").toString().trim();
        midLine.textContent =
          from && to ? `${from} → ${to}` : from || to || "";

        const bottomLine = document.createElement("div");
        bottomLine.className =
          "flex flex-wrap items-center gap-2 text-[10px] text-slate-400";
        if (typeof seg.miles === "number" || seg.miles) {
          const mi = document.createElement("span");
          mi.textContent = `Miles: ${seg.miles}`;
          bottomLine.appendChild(mi);
        }
        if (seg.gmaps_query) {
          const gq = document.createElement("span");
          gq.textContent = seg.gmaps_query;
          bottomLine.appendChild(gq);
        }

        body.appendChild(topLine);
        if (from || to) body.appendChild(midLine);
        if (bottomLine.childNodes.length) body.appendChild(bottomLine);

        row.appendChild(badge);
        row.appendChild(body);
        segmentsList.appendChild(row);
      });
    } else {
      segmentsCount.textContent = "0";
      segmentsList.innerHTML =
        '<p class="text-slate-500">No segments from permits.</p>';
    }

    emptyState.classList.add("hidden");
    resultCard.classList.remove("hidden");

    copyLinkBtn.disabled = !data.google_maps_link;

    // Preview — polyline
    drawRouteOnMap(data, currentTravelMode);
  } catch (err) {
    console.error(err);
    errorBox.textContent = err.message || "Unknown error occurred.";
    errorBox.classList.remove("hidden");
  } finally {
    setLoading(false);
  }
}

submitBtn.addEventListener("click", (e) => {
  e.preventDefault();
  handleSubmit();
});

[startTextInput, endTextInput].forEach((input) => {
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  });
});

copyLinkBtn.addEventListener("click", async () => {
  const url = mapsLink.href;
  if (!url || url === "#" || copyLinkBtn.disabled) return;
  try {
    await navigator.clipboard.writeText(url);
    copyLinkBtn.textContent = "Copied!";
    setTimeout(() => (copyLinkBtn.textContent = "Copy link"), 1200);
  } catch {
    // ignore
  }
});

// ===== GOOGLE MAPS SCRIPTNI DYNAMIC ULASH (.env → backend → config) =====
function loadGoogleMapsScript(apiKey) {
  if (!apiKey) {
    console.error("Google Maps JS API key is missing in config.");
    return;
  }
  const existing = document.querySelector(
    'script[data-role="gmap-js-loader"]'
  );
  if (existing) return;

  const script = document.createElement("script");
  script.dataset.role = "gmap-js-loader";
  script.async = true;
  script.defer = true;
  script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
    apiKey
  )}&callback=initMap`;
  document.head.appendChild(script);
}

async function bootstrapGoogleMaps() {
  try {
    // const res = await fetch("http://127.0.0.1:8003/api/config");
    const res = await fetch("https://nav-api.misterdev.uz/api/config");
    if (!res.ok) throw new Error("Config endpoint error");
    const cfg = await res.json();
    // Backenddan masalan: { "google_maps_js_api_key": "XXX" } keladi
    loadGoogleMapsScript(cfg.google_maps_js_api_key);
  } catch (err) {
    console.error("Failed to load Google Maps config:", err);
  }
}

// Sahifa load bo‘lishi bilan config + script
bootstrapGoogleMaps();

// The "search region" is the primitive for region_search tasks: either an NBN
// edge {type:"edge", a, b} or an anchor neighbourhood {type:"expand", a}.
// Persisted in localStorage so it survives polling re-renders and reloads.
const STORAGE_KEY = "llm4add.frontend.region-selection.v1";

function normalizeRegion(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const type = String(value.type || "").trim();
  const a = String(value.a || "").trim();
  if ((type !== "edge" && type !== "expand") || !a) {
    return null;
  }
  const region = { type, a };
  if (type === "edge") {
    const b = String(value.b || "").trim();
    if (!b || b === a) {
      return null;
    }
    region.b = b;
  }
  if (value.distance !== undefined && value.distance !== null) {
    region.distance = Number(value.distance);
  }
  return region;
}

export function loadRegionSelection() {
  try {
    return normalizeRegion(JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null"));
  } catch (_) {
    return null;
  }
}

export function saveRegionSelection(region) {
  const normalized = normalizeRegion(region);
  if (normalized) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
  return normalized;
}

export function clearRegionSelection() {
  window.localStorage.removeItem(STORAGE_KEY);
  return null;
}

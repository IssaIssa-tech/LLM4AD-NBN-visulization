const STORAGE_KEY = "llm4add.frontend.favorite-node-ids.v2";

export function loadFavoriteNodeIds() {
  try {
    const payload = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(payload)) {
      return [];
    }
    return payload.filter((item) => typeof item === "string" && item);
  } catch (_) {
    return [];
  }
}

export function saveFavoriteNodeIds(ids) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}

export function toggleFavoriteNodeId(ids, nodeId) {
  const next = new Set(ids);
  if (next.has(nodeId)) {
    next.delete(nodeId);
  } else {
    next.add(nodeId);
  }
  return [...next];
}

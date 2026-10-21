// The "task basket" is a dedicated multi-select set of graph node ids, used as
// input for the EoH-evolve and prompt-generate task entries. It is deliberately
// separate from favorites so that "collecting nodes for a task" does not get
// tangled up with "bookmarking interesting nodes". Persisted in localStorage so
// it survives polling-driven re-renders and page reloads.
const STORAGE_KEY = "llm4add.frontend.task-basket-node-ids.v1";

export function loadTaskBasketNodeIds() {
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

export function saveTaskBasketNodeIds(ids) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}

export function toggleTaskBasketNodeId(ids, nodeId) {
  const next = new Set(ids);
  if (next.has(nodeId)) {
    next.delete(nodeId);
  } else {
    next.add(nodeId);
  }
  return [...next];
}

export function clearTaskBasket() {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify([]));
  return [];
}

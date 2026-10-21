import { patchPage, resetSelectionState } from "../core/state.js";

export function selectGraphNode(nodeId) {
  patchPage({
    selectedGraphNodeId: nodeId || null,
  });
}

export function clearGraphSelection() {
  resetSelectionState();
}

export function syncGraphSelection(graphContent, selectedGraphNodeId) {
  const nodes = Array.isArray(graphContent?.nodes) ? graphContent.nodes : [];
  const stillExists = nodes.some((node) => node?.id === selectedGraphNodeId);
  if (!stillExists) {
    clearGraphSelection();
  }
}

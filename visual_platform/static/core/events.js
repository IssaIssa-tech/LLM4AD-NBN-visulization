const listeners = new Map();

export const EVENTS = {
  WORKSPACE_SELECTED: "workspace:selected",
  REVISION_SELECTED: "revision:selected",
  REVISION_DELETE_REQUESTED: "revision:delete-requested",
  REVISION_RENAME_REQUESTED: "revision:rename-requested",
  GRAPH_REQUESTED: "graph:requested",
  GRAPH_ARTIFACT_SELECTED: "graph:artifact-selected",
  GRAPH_NODE_SELECTED: "graph:node-selected",
  GRAPH_NODE_FAVORITE_TOGGLED: "graph:node-favorite-toggled",
  TASK_BASKET_TOGGLED: "graph:task-basket-toggled",
  TASK_BASKET_CLEARED: "graph:task-basket-cleared",
  REGION_SELECTED: "graph:region-selected",
  REGION_CLEARED: "graph:region-cleared",
  JOB_CANCEL_REQUESTED: "job:cancel-requested",
  EOH_EVOLVE_SUBMITTED: "job:eoh-evolve-submitted",
  PROMPT_GEN_SUBMITTED: "job:prompt-gen-submitted",
  REGION_SEARCH_SUBMITTED: "job:region-search-submitted",
  HISTORY_IMPORT_SUBMITTED: "job:history-import-submitted",
  EXPERT_IMPORT_SUBMITTED: "job:expert-import-submitted",
  GRAPH_BUILD_SUBMITTED: "job:graph-build-submitted",
  WORKSPACE_CREATED: "workspace:created",
  WORKSPACES_REFRESH_REQUESTED: "workspace:refresh-requested",
  THEME_TOGGLED: "prefs:theme-toggled",
  PANEL_TOGGLED: "prefs:panel-toggled",
};

export function on(eventName, handler) {
  if (!listeners.has(eventName)) {
    listeners.set(eventName, new Set());
  }
  listeners.get(eventName).add(handler);
  return () => listeners.get(eventName)?.delete(handler);
}

export function emit(eventName, payload = {}) {
  listeners.get(eventName)?.forEach((handler) => handler(payload));
}

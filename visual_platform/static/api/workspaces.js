import { apiRequest } from "./client.js";

export function listWorkspaces() {
  return apiRequest("/api/workspaces");
}

export function getWorkspace(workspaceId) {
  return apiRequest(`/api/workspaces/${encodeURIComponent(workspaceId)}`);
}

export function createWorkspace(name) {
  return apiRequest("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function updateWorkspace(workspaceId, payload) {
  return apiRequest(`/api/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listWorkspaceRevisions(workspaceId) {
  return apiRequest(`/api/workspaces/${encodeURIComponent(workspaceId)}/revisions`);
}

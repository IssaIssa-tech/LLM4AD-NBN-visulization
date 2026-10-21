import { apiRequest, buildQuery } from "./client.js";

export function getRevision(revisionId) {
  return apiRequest(`/api/revisions/${encodeURIComponent(revisionId)}`);
}

export function getRevisionEvents(revisionId, { limit = 100 } = {}) {
  return apiRequest(
    buildQuery(`/api/revisions/${encodeURIComponent(revisionId)}/events`, {
      limit,
    }),
  );
}

export function deleteRevision(revisionId, { force = false } = {}) {
  const suffix = force ? "?force=true" : "";
  return apiRequest(`/api/revisions/${encodeURIComponent(revisionId)}${suffix}`, { method: "DELETE" });
}

export function renameRevision(revisionId, displayName) {
  return apiRequest(`/api/revisions/${encodeURIComponent(revisionId)}`, {
    method: "PATCH",
    body: JSON.stringify({ displayName: displayName ?? "" }),
  });
}

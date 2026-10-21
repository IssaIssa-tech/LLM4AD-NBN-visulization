import { apiRequest, buildQuery } from "./client.js";

export function listRevisionArtifacts(revisionId, filters = {}) {
  return apiRequest(
    buildQuery(`/api/revisions/${encodeURIComponent(revisionId)}/artifacts`, filters),
  );
}

export function getArtifactContent(artifactId) {
  return apiRequest(`/api/artifacts/${encodeURIComponent(artifactId)}/content`);
}

export function getNodeCode(nodeId, artifactId) {
  return apiRequest(
    buildQuery(`/api/nodes/${encodeURIComponent(nodeId)}/code`, { artifactId }),
  );
}

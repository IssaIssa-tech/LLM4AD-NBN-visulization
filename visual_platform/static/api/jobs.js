import { apiRequest, buildQuery } from "./client.js";

export function submitJob(payload) {
  return apiRequest("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getJob(jobId) {
  return apiRequest(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function getJobEvents(jobId, { limit = 20, afterSeq = null } = {}) {
  return apiRequest(
    buildQuery(`/api/jobs/${encodeURIComponent(jobId)}/events`, {
      limit,
      afterSeq,
    }),
  );
}

export function cancelJob(jobId) {
  return apiRequest(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
}

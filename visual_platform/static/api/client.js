export async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (_) {
    throw new Error(`接口未返回 JSON: ${path}`);
  }

  if (!response.ok) {
    const message = payload?.error?.message || payload?.error || `请求失败: ${response.status}`;
    const error = new Error(String(message));
    error.status = response.status;
    error.code = payload?.error?.code;
    error.details = payload?.error?.details;
    error.payload = payload;
    throw error;
  }
  if (payload?.ok === false) {
    const error = new Error(String(payload?.error?.message || payload?.error || "请求失败"));
    error.code = payload?.error?.code;
    error.details = payload?.error?.details;
    error.payload = payload;
    throw error;
  }
  return payload?.ok === true && payload?.data !== undefined ? payload.data : payload;
}

export function buildQuery(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });
  return `${url.pathname}${url.search}`;
}

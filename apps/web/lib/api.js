const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      if (Array.isArray(body.detail)) detail = body.detail.map((item) => item.msg).join(", ");
    } catch {
      // Keep the status-based fallback for non-JSON errors.
    }
    if (response.status === 401) {
      detail = "Sign in to Atlas before managing records.";
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

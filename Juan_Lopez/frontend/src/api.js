// Browser requests use the same-origin API; keep credentials and LLM keys server-side.
export async function getRuns(signal) {
  const response = await fetch('/api/v1/runs', { signal });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || 'The API is unavailable. Start the backend and retry.');
  }
  return response.json();
}

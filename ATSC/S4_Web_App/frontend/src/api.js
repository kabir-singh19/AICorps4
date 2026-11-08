import { useEffect, useState } from 'react';

// Credentials and model execution stay server-side.
export async function request(path, signal, options = {}) {
  const response = await fetch(path, { ...options, signal, credentials: 'same-origin', headers: { Accept: 'application/json', ...options.headers } });
  const data = await response.json().catch(() => null);
  if (!response.ok || data === null) {
    const error = new Error(data?.message || 'The service is unavailable. Please refresh or try again later.');
    error.status = response.status;
    throw error;
  }
  return data;
}

export const postJson = (path, body, signal) => request(path, signal, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });

export const getRuns = signal => request('/api/v1/runs', signal);
export const runPath = (resource, runId) => runId ? `/api/v1/${resource}?run_id=${encodeURIComponent(runId)}` : null;

export function useApi(path) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({ path: null, revision: -1, data: null, error: '', loading: false });
  useEffect(() => {
    if (!path) {
      setState({ path: null, revision, data: null, error: '', loading: false });
      return;
    }
    const controller = new AbortController();
    setState({ path, revision, data: null, error: '', loading: true });
    request(path, controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ path, revision, data, error: '', loading: false }); })
      .catch(error => { if (!controller.signal.aborted) setState({ path, revision, data: null, error: error.message, loading: false }); });
    return () => controller.abort();
  }, [path, revision]);
  // Do not show the preceding run's results while a new request starts.
  const current = path && state.path === path && state.revision === revision;
  return { data: current ? state.data : null, error: current ? state.error : '', loading: Boolean(path) && (!current || state.loading), refresh: () => setRevision(value => value + 1) };
}

import React, { useEffect, useRef, useState } from 'react';
import { postJson, useApi } from '../api.js';

export default function Assistant({ run, sites, selectedSite, onSelectSite }) {
  const connection = useApi('/api/v1/assistant/status');
  const session = useApi('/api/v1/auth/session');
  const [password, setPassword] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const controller = useRef(null);
  const operation = useRef(0);
  const siteId = selectedSite?.properties.site_id || null;
  const runId = run?.run_id || null;
  useEffect(() => {
    operation.current += 1;
    controller.current?.abort();
    setAnswer(null);
    setError('');
    setBusy(false);
    return () => { operation.current += 1; controller.current?.abort(); };
  }, [runId, siteId]);

  async function login(event) {
    event.preventDefault();
    const id = ++operation.current;
    controller.current?.abort();
    controller.current = new AbortController();
    setBusy(true); setError('');
    try {
      await postJson('/api/v1/auth/login', { password }, controller.current.signal);
      if (id === operation.current) { setPassword(''); session.refresh(); }
    } catch (failure) { if (id === operation.current && failure.name !== 'AbortError') setError(failure.message); }
    finally { if (id === operation.current) setBusy(false); }
  }

  async function logout() {
    const id = ++operation.current;
    controller.current?.abort();
    controller.current = new AbortController();
    setBusy(true); setError(''); setAnswer(null);
    try { await postJson('/api/v1/auth/logout', {}, controller.current.signal); if (id === operation.current) session.refresh(); }
    catch (failure) { if (id === operation.current && failure.name !== 'AbortError') setError(failure.message); }
    finally { if (id === operation.current) setBusy(false); }
  }

  async function ask(event) {
    event.preventDefault();
    const id = ++operation.current;
    controller.current?.abort();
    controller.current = new AbortController();
    setBusy(true); setError(''); setAnswer(null);
    try {
      const result = await postJson('/api/v1/assistant/chat', { question: question.trim(), run_id: runId, site_id: siteId }, controller.current.signal);
      if (id === operation.current) setAnswer(result);
    } catch (failure) {
      if (id === operation.current && failure.name !== 'AbortError') {
        setError(failure.message);
        if (failure.status === 401) session.refresh();
      }
    } finally { if (id === operation.current) setBusy(false); }
  }

  const ready = Boolean(connection.data?.available && session.data?.authenticated);
  return <div className="assistant-layout">
    <section className="card" aria-label="Assistant connection">
      <div className="details-heading"><div><p className="eyebrow">EVIDENCE BEFORE ANSWERS</p><h2>Traffic-safety assistant</h2></div><button onClick={() => { connection.refresh(); session.refresh(); }} disabled={busy}>Refresh connection</button></div>
      <p>Explore published results, understand model comparisons, and prepare questions for engineering review.</p>
      <div className="connection-row"><span className={`connection-dot ${connection.data?.available ? 'connected' : ''}`} aria-hidden="true"/><strong>{connection.loading ? 'Checking connection…' : connection.data?.available ? `${connection.data.provider} connected` : 'AI connection not enabled'}</strong></div>
      {connection.error && <p role="alert" className="api-error">{connection.error}</p>}
      {session.error && <p role="alert" className="api-error">{session.error}</p>}
      {connection.data && !connection.data.available && <p className="map-note">The deployment owner must configure the AI service and project access before questions can be sent.</p>}
      {session.data?.authenticated ? <div className="details-heading"><p>Project access is active for this session.</p><button onClick={logout} disabled={busy}>Sign out</button></div> : session.data?.configured ? <form onSubmit={login} className="access-form"><label htmlFor="project-password">Project access password</label><p className="map-note">Use the password shared by the project owner. This is not a university account sign-in.</p><div className="form-row"><input id="project-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required maxLength={512} /><button disabled={busy || !password}>Sign in</button></div></form> : null}
    </section>
    <section className="card" aria-label="Ask about traffic safety">
      <label htmlFor="assistant-site">Evidence scope</label>
      <select id="assistant-site" value={siteId || ''} disabled={!run || !sites.length || busy} onChange={event => onSelectSite(event.target.value)}><option value="">{run ? 'Run summary — up to 10 highest-ranked sites' : 'Project workflow — no model run selected'}</option>{sites.map(site => <option key={site.properties.site_id} value={site.properties.site_id}>{site.properties.road_name} · {site.properties.site_id}</option>)}</select>
      <p className="map-note">{run ? `Run: ${run.run_id}. Published evidence will be sent to the configured AI provider when you submit.` : 'Select a published model run for questions about risk values or individual sites.'}</p>
      <form onSubmit={ask}><label htmlFor="assistant-question">Your question</label><textarea id="assistant-question" placeholder="What does the selected site's risk result mean?" value={question} onChange={event => setQuestion(event.target.value)} rows={4} maxLength={2000} required disabled={!ready || busy}/><div className="details-heading"><span className="map-note">{question.length}/2,000 characters</span><button className="primary-button" disabled={!ready || busy || !question.trim()}>{busy ? 'Working…' : 'Ask assistant'}</button></div></form>
      {busy && <p role="status">Waiting for the service…</p>}
      {error && <p role="alert" className="api-error">{error}</p>}
      {answer && <article className="assistant-answer" aria-label="AI draft answer"><p className="eyebrow">AI DRAFT · REVIEW REQUIRED</p>{answer.is_demo && <p className="demo-label">This answer uses synthetic example data.</p>}<p className="memo-text">{answer.answer}</p><h3>Evidence provided</h3><ul>{answer.sources.map(source => <li key={source.id}>{source.label} <code>{source.id}</code></li>)}</ul><p className="map-note">Provider: {answer.provider} · Model: {answer.model}. Responses are drafts and are not published as engineering memos.</p></article>}
    </section>
  </div>;
}

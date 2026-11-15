import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, FilePlus2, FlaskConical, RefreshCw, Save, ShieldCheck } from 'lucide-react';
import { API_BASE, authFetch } from './authClient';
import './workspace-content-lab.css';

type Role = 'admin' | 'editor' | 'creator' | 'reviewer';
type Workspace = { id: string; name: string; role: Role };
type Draft = { id: string; title: string; channel: string; version: number };
type Version = { id: string; number: number; content: string; created_at: string };
type Detail = Draft & { current: Version; versions: Version[] };
type Finding = { id: string; rule_code: string; category?: string; title: string; matched_text: string; start: number; end: number; suggestion: string };
type Run = { run_id?: string; id?: string; version_id?: string; version_number?: number; checked_rules: number; findings: Finding[]; disclaimer?: string };
type Activity = { id: string; type: string; version_id?: string; created_at: string };
type Rule = { code: string; title: string; category: string; pattern: string; replacement: string; active: number };
const esc = encodeURIComponent;
const writable = (role?: Role) => role === 'admin' || role === 'editor' || role === 'creator';

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authFetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
const post = (body?: unknown): RequestInit => ({ method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

function highlightedParts(content: string, findings: Finding[]) {
  const ordered = findings
    .filter(f => Number.isInteger(f.start) && Number.isInteger(f.end) && f.start >= 0 && f.end <= content.length && f.end > f.start && content.slice(f.start, f.end) === f.matched_text)
    .sort((a, b) => a.start - b.start || b.end - a.end);
  const parts: { text: string; finding?: Finding }[] = [];
  let position = 0;
  for (const f of ordered) {
    if (f.start < position) continue;
    if (f.start > position) parts.push({ text: content.slice(position, f.start) });
    parts.push({ text: content.slice(f.start, f.end), finding: f });
    position = f.end;
  }
  if (position < content.length) parts.push({ text: content.slice(position) });
  return parts;
}

export default function WorkspaceContentLab({ onOpenReview }: { onOpenReview?: (workspaceId: string, draftId: string) => void }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState('');
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [draftId, setDraftId] = useState('');
  const [detail, setDetail] = useState<Detail | null>(null);
  const [editor, setEditor] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [newChannel, setNewChannel] = useState('social');
  const [rules, setRules] = useState<Rule[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [showingSavedRun, setShowingSavedRun] = useState(false);
  const [selectedFinding, setSelectedFinding] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reload, setReload] = useState(0);
  const current = workspaces.find(w => w.id === workspaceId);
  const base = `/workspaces/${esc(workspaceId)}`;
  const canWrite = writable(current?.role);
  const dirty = detail ? editor !== detail.current.content : false;
  const parts = useMemo(() => highlightedParts(detail?.current.content || '', run?.findings || []), [detail, run]);
  const sourceMatchesRun = !!detail && !!run && !dirty && (!run.version_id || run.version_id === detail.current.id);

  const execute = async (fn: () => Promise<void>) => {
    setBusy(true); setError(''); setNotice('');
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const refreshDrafts = useCallback(async (wid: string) => {
    const result = await api<Draft[]>(`/workspaces/${esc(wid)}/drafts`);
    setDrafts(result);
    return result;
  }, []);

  useEffect(() => {
    let valid = true;
    api<Workspace[]>('/workspaces').then(ws => {
      if (!valid) return;
      setWorkspaces(ws);
      setWorkspaceId(old => ws.some(w => w.id === old) ? old : (ws[0]?.id || ''));
    }).catch(e => { if (valid) setError(String(e)); }).finally(() => { if (valid) setLoading(false); });
    return () => { valid = false; };
  }, []);

  useEffect(() => {
    setDraftId(''); setDetail(null); setEditor(''); setRun(null); setRules([]); setSelectedFinding('');
    if (!workspaceId) { setDrafts([]); return; }
    let valid = true;
    Promise.all([api<Draft[]>(`${base}/drafts`), api<Rule[]>(`${base}/rules`)]).then(([items, ruleItems]) => {
      if (!valid) return;
      setDrafts(items); setRules(ruleItems);
    }).catch(e => { if (valid) setError(String(e)); });
    return () => { valid = false; };
  }, [workspaceId, reload]);

  async function openDraft(id: string) {
    const d = await api<Detail>(`${base}/drafts/${esc(id)}`);
    const activity = await api<Activity[]>(`${base}/drafts/${esc(id)}/activity`);
    const latest = activity.filter(a => a.type === 'policy_test' && a.version_id === d.current.id)
      .sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id.localeCompare(a.id))[0];
    let prior: Run | null = null;
    if (latest) prior = await api<Run>(`${base}/runs/${esc(latest.id.replace(/^test:/, ''))}`);
    setDraftId(id); setDetail(d); setEditor(d.current.content); setRun(prior);
    setShowingSavedRun(!!prior); setSelectedFinding('');
  }

  function chooseDraft(id: string) {
    if (dirty && !window.confirm('Discard your unsaved editor changes?')) return;
    if (!id) { setDraftId(''); setDetail(null); setEditor(''); setRun(null); return; }
    void execute(() => openDraft(id));
  }

  async function checkLatestVersionStillCurrent() {
    if (!detail) throw new Error('Select a draft first.');
    const latest = await api<Detail>(`${base}/drafts/${esc(detail.id)}`);
    if (latest.current.id !== detail.current.id) {
      setDetail(latest); setEditor(latest.current.content); setRun(null);
      throw new Error('Another member saved a newer version. The editor was refreshed; review their changes before editing.');
    }
  }

  async function saveVersion() {
    if (!detail || !dirty || !canWrite) return;
    await execute(async () => {
      await checkLatestVersionStillCurrent();
      const result = await api<{ number: number }>(`${base}/drafts/${esc(detail.id)}/revisions`, post({ content: editor, expected_version: detail.current.number }));
      await openDraft(detail.id);
      await refreshDrafts(workspaceId);
      setNotice(`Saved Version ${result.number}. Run policy checks again before requesting approval.`);
    });
  }

  async function createDraft() {
    if (!canWrite || !newTitle.trim() || !editor.trim()) return;
    await execute(async () => {
      const result = await api<{ id: string }>(`${base}/drafts`, post({ title: newTitle.trim(), channel: newChannel, content: editor }));
      setNewTitle('');
      await refreshDrafts(workspaceId);
      await openDraft(result.id);
      setNotice('New workspace draft saved in PostgreSQL.');
    });
  }

  async function evaluate() {
    if (!detail || !canWrite) return;
    await execute(async () => {
      if (dirty) throw new Error('Save the updated content as a new version before running policy checks.');
      await checkLatestVersionStillCurrent();
      const result = await api<Run>(`${base}/drafts/${esc(detail.id)}/run`, post());
      setRun(result); setShowingSavedRun(false); setSelectedFinding('');
      setNotice(`${result.findings.length} finding(s) across ${result.checked_rules} configured rules. Results apply to this saved version only.`);
    });
  }

  function applySuggestion(f: Finding) {
    if (!detail || !sourceMatchesRun || !canWrite || !f.suggestion) return;
    if (editor.slice(f.start, f.end) !== f.matched_text) {
      setError('The highlighted text has changed. Retest the saved version before applying this suggestion.'); return;
    }
    setEditor(old => old.slice(0, f.start) + f.suggestion + old.slice(f.end));
    setSelectedFinding(''); setNotice('Suggestion applied in the editor only. Save a new version, then retest.');
  }

  function applyAll() {
    if (!detail || !sourceMatchesRun || !canWrite || !run) return;
    let changed = editor;
    const ranges = run.findings.filter(f => !!f.suggestion).sort((a, b) => b.start - a.start);
    let lastStart = editor.length;
    for (const f of ranges) {
      if (f.end > lastStart || changed.slice(f.start, f.end) !== f.matched_text) continue;
      changed = changed.slice(0, f.start) + f.suggestion + changed.slice(f.end);
      lastStart = f.start;
    }
    setEditor(changed);
    setSelectedFinding(''); setNotice('Suggestions applied locally. Save the new version and retest.');
  }

  return <section className="wcl-root" aria-label="Workspace Content Lab">
    <div className="wcl-top"><div><span className="kicker">GLITCHLAB_ / WORKSPACE CONTENT INSPECTION</span><h2>Content Lab</h2><p>Edit, inspect and retest real PostgreSQL draft versions. No automatic approvals or AI fact certification.</p></div><button className="ghost" disabled={busy || !workspaceId} onClick={() => setReload(n => n + 1)}><RefreshCw size={16}/> Refresh list</button></div>
    <div className="wcl-banner"><ShieldCheck size={18}/><span>Authenticated workspace-scoped API · Role: <b>{current?.role || '—'}</b> · Only saved versions can be evaluated.</span></div>
    {error && <p className="wcl-error" role="alert"><AlertTriangle size={16}/>{error}</p>}
    {notice && <p className="wcl-notice" role="status"><CheckCircle2 size={16}/>{notice}</p>}
    {loading ? <p>Loading workspaces…</p> : workspaces.length === 0 ? <p>No authorized workspaces available.</p> : <>
      <div className="wcl-pickers"><label>Workspace<select value={workspaceId} onChange={e => { if (!dirty || window.confirm('Discard unsaved changes?')) setWorkspaceId(e.target.value); }}>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}</select></label>
      <label>Saved draft<select value={draftId} onChange={e => chooseDraft(e.target.value)}><option value="">New draft</option>{drafts.map(d => <option key={d.id} value={d.id}>{d.title} · v{d.version}</option>)}</select></label></div>
      <div className="wcl-columns">
        <section className="wcl-panel"><div className="wcl-heading"><span>01 / THE DRAFT</span><h3>{detail ? detail.title : 'Create a workspace draft'}</h3></div>
          {!detail && <div className="wcl-pickers wcl-new"><label>Title<input value={newTitle} maxLength={120} onChange={e => setNewTitle(e.target.value)} placeholder="Campaign announcement"/></label><label>Channel<select value={newChannel} onChange={e => setNewChannel(e.target.value)}><option value="social">Social</option><option value="email">Email</option><option value="website">Website</option><option value="general">General</option></select></label></div>}
          {detail && <p className="wcl-meta">{detail.channel} · Saved version {detail.current.number} · {detail.versions.length} version(s)</p>}
          <label className="wcl-editor-label" htmlFor="wcl-editor">CONTENT / LIVE EDITOR <small>{editor.length} characters{dirty ? ' · unsaved changes' : ''}</small></label>
          <textarea id="wcl-editor" className="wcl-editor" rows={12} maxLength={12000} value={editor} readOnly={!canWrite} placeholder="Write authorized sample brand content…" onChange={e => { setEditor(e.target.value); setSelectedFinding(''); }}/>
          <div className="wcl-buttons">{!detail ? <button className="primary" disabled={busy || !canWrite || !newTitle.trim() || !editor.trim()} onClick={() => void createDraft()}><FilePlus2 size={16}/> Save draft</button> : <><button className="ghost" disabled={busy || !canWrite || !dirty || !editor.trim()} onClick={() => void saveVersion()}><Save size={16}/> Save new version</button><button className="primary" disabled={busy || !canWrite || dirty} onClick={() => void evaluate()}><FlaskConical size={16}/> Run policy checks</button></>}</div>
          {!canWrite && <p className="wcl-meta">Your role has read-only access to content editing and testing.</p>}
          {detail && onOpenReview && <button className="wcl-link" type="button" onClick={() => onOpenReview(workspaceId, detail.id)}>Open version history & review in Workspace Control →</button>}
        </section>
        <section className="wcl-panel"><div className="wcl-heading"><span>02 / THE INSPECTION</span><h3>What broke?</h3></div>
          {!detail ? <p className="wcl-empty">Save or select a draft to inspect it.</p> : !run ? <p className="wcl-empty">No policy run loaded for this version. Run checks on the saved content.</p> : <>
            <div className="wcl-result"><b>{run.findings.length} finding(s) · {run.checked_rules} rules evaluated</b>{showingSavedRun && <small>Most recent stored run for this version</small>}{dirty && <small>Editor changed since last evaluation. Results refer to saved text only.</small>}{run.checked_rules === 0 && <small>No configured rules were checked. This is not a passing compliance assessment.</small>}</div>
            {run.findings.length === 0 ? <p className="wcl-meta">No configured-rule matches. Factual correctness has not been verified.</p> : <>
              <div className="wcl-preview" aria-label="Annotated saved content">{parts.map((p, i) => p.finding ? <button key={i} type="button" className={selectedFinding === p.finding.id ? 'wcl-highlight selected' : 'wcl-highlight'} title={`${p.finding.rule_code}: ${p.finding.title}`} onClick={() => setSelectedFinding(p.finding!.id)}>{p.text}</button> : <span key={i}>{p.text}</span>)}</div>
              {canWrite && <button className="ghost" disabled={busy || !sourceMatchesRun || !run.findings.some(f => !!f.suggestion)} onClick={applyAll}>Apply all suggested replacements</button>}
              <div className="wcl-findings">{run.findings.map(f => <article key={f.id} className={selectedFinding === f.id ? 'wcl-finding selected' : 'wcl-finding'}><span>{f.rule_code} · {f.category || 'policy'}</span><h4>{f.title}</h4><blockquote>“{f.matched_text}”</blockquote><p>Suggested replacement: <b>{f.suggestion || 'Manual revision required'}</b></p>{canWrite && <button type="button" className="wcl-action" disabled={busy || !sourceMatchesRun || !f.suggestion} onClick={() => applySuggestion(f)}>Apply this suggestion</button>}</article>)}</div>
            </>}
            <p className="wcl-meta">Pattern-rule results only; no factual, legal or accessibility certification.</p>
          </>}
          <div className="wcl-rules"><strong>{rules.filter(r => !!r.active).length} active workspace rule(s)</strong><p>Rule definitions are owned by the workspace. Policy editing and releases will be handled in Protocol Studio.</p></div>
        </section>
      </div>
    </>}
  </section>;
}

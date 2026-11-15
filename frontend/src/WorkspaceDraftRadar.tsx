
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { API_BASE, authFetch } from './authClient';
import './workspace-draft-radar.css';

type Workspace = {
  id: string;
  name: string;
  role: string;
};

type Draft = {
  id: string;
  title: string;
  channel: string;
  version: number;
  created_at: string;
};

type Detail = {
  current: {
    id: string;
    number: number;
  };
  versions: {
    id: string;
    number: number;
  }[];
};

type Review = {
  version_id: string;
  decision: string;
  created_at: string;
};

type Activity = {
  id: string;
  type: string;
  version_id?: string;
  created_at: string;
};

type Run = {
  checked_rules: number;
  findings: { id: string }[];
};

type Status =
  | 'approved'
  | 'legacy'
  | 'issues'
  | 'clear'
  | 'untested'
  | 'unknown';

type Entry = {
  draft: Draft;
  status: Status;
  findings?: number;
  checked?: number;
  latestTest?: string;
  error?: string;
};

async function read<T>(path: string): Promise<T> {
  const response = await authFetch(`${API_BASE}${path}`);

  if (!response.ok) {
    const value = await response.json().catch(() => null);

    throw new Error(
      typeof value?.detail === 'string'
        ? value.detail
        : `Request failed (${response.status})`
    );
  }

  return response.json() as Promise<T>;
}

const esc = encodeURIComponent;

const format = (value?: string): string => {
  if (!value) return '—';

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
};

const labels: Record<Status, string> = {
  approved: 'Approved latest version',
  legacy: 'Historical approval · needs verification',
  issues: 'Needs fixes',
  clear: 'Ready for review',
  untested: 'Not tested',
  unknown: 'Unavailable',
};

export default function WorkspaceDraftRadar({
  onOpen,
}: {
  onOpen: (workspaceId: string, draftId: string) => void;
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [active, setActive] = useState('');
  const [rows, setRows] = useState<Entry[]>([]);

  const [search, setSearch] = useState('');
  const [channel, setChannel] = useState('all');
  const [status, setStatus] = useState('all');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const loadWorkspaces = useCallback(async () => {
    try {
      const data = await read<Workspace[]>('/workspaces');

      setWorkspaces(data);
      setActive(old =>
        data.some(w => w.id === old)
          ? old
          : data[0]?.id || ''
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  useEffect(() => {
    if (!active) {
      setRows([]);
      setLoading(false);
      return;
    }

    let cancelled = false;

    setLoading(true);
    setError('');
    setRows([]);

    const base = `/workspaces/${esc(active)}`;

    async function loadDraftRecords() {
      const drafts = await read<Draft[]>(`${base}/drafts`);
      const entries: Entry[] = [];

      // Process up to four drafts concurrently.
      for (let i = 0; i < drafts.length; i += 4) {
        const batch = await Promise.all(
          drafts.slice(i, i + 4).map(async (draft): Promise<Entry> => {
            try {
              const id = esc(draft.id);

              const [detail, reviews, activity] = await Promise.all([
                read<Detail>(`${base}/drafts/${id}`),
                read<Review[]>(`${base}/drafts/${id}/reviews`),
                read<Activity[]>(`${base}/drafts/${id}/activity`),
              ]);

              const version = detail.current.id;

              const latestRun = activity
                .filter(
                  item =>
                    item.type === 'policy_test' &&
                    item.version_id === version
                )
                .sort(
                  (a, b) =>
                    b.created_at.localeCompare(a.created_at) ||
                    b.id.localeCompare(a.id)
                )[0];

              let reviewStatus: Status = 'untested';
              let findings: number | undefined;
              let checked: number | undefined;

              if (latestRun) {
                const runId = latestRun.id.replace(/^test:/, '');

                const run = await read<Run>(
                  `${base}/runs/${esc(runId)}`
                );

                findings = run.findings.length;
                checked = run.checked_rules;

                if (findings > 0) {
                  reviewStatus = 'issues';
                } else if (checked > 0) {
                  reviewStatus = 'clear';
                }
              }

              const hasApproval = reviews.some(
                review =>
                  review.version_id === version &&
                  review.decision === 'approved'
              );

              // A historical approval is not a verified passing
              // review if no eligible policy check was recorded.
              if (hasApproval) {
                if (
                  latestRun &&
                  checked !== undefined &&
                  checked > 0 &&
                  findings === 0
                ) {
                  reviewStatus = 'approved';
                } else {
                  reviewStatus = 'legacy';
                }
              }

              return {
                draft,
                status: reviewStatus,
                findings,
                checked,
                latestTest: latestRun?.created_at,
              };
            } catch (e) {
              return {
                draft,
                status: 'unknown',
                error: e instanceof Error ? e.message : String(e),
              };
            }
          })
        );

        entries.push(...batch);
      }

      if (!cancelled) {
        setRows(entries);
      }
    }

    void loadDraftRecords()
      .catch(e => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [active, refreshKey]);

  const visible = useMemo(
    () =>
      rows.filter(
        entry =>
          (
            !search.trim() ||
            entry.draft.title
              .toLowerCase()
              .includes(search.trim().toLowerCase())
          ) &&
          (
            channel === 'all' ||
            entry.draft.channel === channel
          ) &&
          (
            status === 'all' ||
            entry.status === status
          )
      ),
    [rows, search, channel, status]
  );

  const current = workspaces.find(w => w.id === active);

  return (
    <section className="wdr-root" aria-label="Workspace Draft Radar">
      <header className="wdr-header">
        <div>
          <span className="kicker">
            WORKSPACE-SCOPED CONTENT REGISTRY
          </span>

          <h2>Draft Radar</h2>

          <p>
            Live drafts, checks, and review history from
            an authorized PostgreSQL workspace.
          </p>
        </div>

        <button
          type="button"
          className="ghost"
          disabled={loading || !active}
          onClick={() => setRefreshKey(n => n + 1)}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </header>

      <div className="wdr-controls">
        <label>
          Workspace

          <select
            aria-label="Choose workspace"
            value={active}
            onChange={e => setActive(e.target.value)}
          >
            {workspaces.map(workspace => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name} · {workspace.role}
              </option>
            ))}
          </select>
        </label>

        <label>
          Find drafts

          <div className="wdr-search">
            <Search size={17} />

            <input
              aria-label="Search drafts"
              placeholder="Search by title"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </label>

        <label>
          Channel

          <select
            aria-label="Channel filter"
            value={channel}
            onChange={e => setChannel(e.target.value)}
          >
            <option value="all">All channels</option>
            <option value="social">Social</option>
            <option value="email">Email</option>
            <option value="website">Website</option>
            <option value="general">General</option>
          </select>
        </label>

        <label>
          Review state

          <select
            aria-label="Review state filter"
            value={status}
            onChange={e => setStatus(e.target.value)}
          >
            <option value="all">All states</option>

            {(Object.keys(labels) as Status[]).map(state => (
              <option key={state} value={state}>
                {labels[state]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <p className="wdr-error" role="alert">
          {error}
        </p>
      )}

      <div className="wdr-summary">
        <span>
          <strong>{rows.length}</strong>
          {' '}workspace drafts
        </span>

        <span>
          <strong>
            {rows.filter(r => r.status === 'issues').length}
          </strong>
          {' '}with findings
        </span>

        <span>
          <strong>
            {rows.filter(r => r.status === 'approved').length}
          </strong>
          {' '}current-version approvals
        </span>
      </div>

      {loading ? (
        <p className="wdr-empty">
          Loading authorized workspace records…
        </p>
      ) : !current ? (
        <p className="wdr-empty">
          No workspace available for this account.
        </p>
      ) : visible.length === 0 ? (
        <p className="wdr-empty">
          No matching workspace drafts.
        </p>
      ) : (
        <div className="wdr-table-wrap">
          <table className="wdr-table">
            <thead>
              <tr>
                <th>Draft</th>
                <th>Channel</th>
                <th>Version</th>
                <th>Latest policy check</th>
                <th>Review state</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {visible.map(entry => (
                <tr key={entry.draft.id}>
                  <td>
                    <strong>{entry.draft.title}</strong>
                    <small>
                      Created {format(entry.draft.created_at)}
                    </small>
                  </td>

                  <td>{entry.draft.channel}</td>

                  <td>v{entry.draft.version}</td>

                  <td>
                    {entry.findings === undefined
                      ? '—'
                      : `${entry.findings} finding(s) / ${entry.checked} rule(s)`}

                    <small>{format(entry.latestTest)}</small>
                  </td>

                  <td>
                    <span className={`wdr-state wdr-${entry.status}`}>
                      {labels[entry.status]}
                    </span>

                    {entry.error && (
                      <small title={entry.error}>
                        Could not load status
                      </small>
                    )}
                  </td>

                  <td>
                    <button
                      className="wdr-open"
                      type="button"
                      onClick={() =>
                        onOpen(active, entry.draft.id)
                      }
                    >
                      Open
                      <ArrowRight size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="wdr-note">
        <ShieldCheck size={16} />
        Records are retrieved through authenticated, workspace-scoped routes.
        {' '}“Ready for review” means the latest configured policy check
        returned no findings with at least one rule evaluated.
        It does not establish factual accuracy or guarantee compliance.
        Historical approvals with insufficient test evidence are labelled
        separately.
      </p>
    </section>
  );
}

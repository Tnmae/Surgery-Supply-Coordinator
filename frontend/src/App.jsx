import { useEffect, useMemo, useState } from 'react';
import { checkReadiness, fetchAudit, fetchSurgery, fetchSurgeries, submitBlockerDecision } from './api';

const roles = ['OR_COORDINATOR', 'SUPPLY_ADMIN', 'BLOOD_BANK_TECH', 'VIEWER'];

function statusClass(status) {
  if (status === 'READY') return 'chip chip-ready';
  if (status === 'BLOCKED') return 'chip chip-blocked';
  if (status === 'RESOLVED') return 'chip chip-ready';
  if (status === 'HALT_DUE_TO_BLOCKER') return 'chip chip-blocked';
  return 'chip chip-warning';
}

/** Map a decision value to its display label. */
function decisionLabel(d) {
  if (d === 'ACCEPT') return 'Accepted — Status: Resolved';
  if (d === 'REJECT') return 'Rejected — Status: Halted';
  return 'Pending review';
}

/** Human-readable label for the overall review status. */
function reviewStatusLabel(status) {
  if (status === 'RESOLVED') return 'All blockers resolved';
  if (status === 'HALT_DUE_TO_BLOCKER') return 'Halted — blocker rejected';
  if (status === 'PENDING_REVIEW') return 'Awaiting review';
  return status || 'Awaiting review';
}

/** Small pill shown on each surgery card in the list. */
function reviewPill(surgery) {
  const rs = surgery.readiness_review_status;
  const hasReport = !!surgery.readiness_report;
  if (!hasReport) return null;
  if (rs === 'RESOLVED') return { label: 'Resolved', cls: 'pill-resolved' };
  if (rs === 'HALT_DUE_TO_BLOCKER') return { label: 'Halted', cls: 'pill-halted' };
  if (rs === 'PENDING_REVIEW') return { label: 'Pending Review', cls: 'pill-pending' };
  return null;
}

export default function App() {
  const [role, setRole] = useState('OR_COORDINATOR');
  const [surgeries, setSurgeries] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [surgeryDetail, setSurgeryDetail] = useState(null);
  const [readiness, setReadiness] = useState(null);
  // blockerDecisions: { [idx]: 'ACCEPT' | 'REJECT' }  — seeded from stored decisions on load
  const [blockerDecisions, setBlockerDecisions] = useState({});
  const [auditTrail, setAuditTrail] = useState([]);
  const [auditLimit, setAuditLimit] = useState(100);
  const [activeTab, setActiveTab] = useState('surgeries');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // live review status shown on the readiness tab, kept in sync after every decision
  const [reviewStatus, setReviewStatus] = useState(null);

  const selectedSurgery = useMemo(
    () => surgeries.find((s) => s.surgery_id === selectedId),
    [surgeries, selectedId]
  );

  async function loadSurgeries() {
    setError('');
    try {
      const data = await fetchSurgeries(role);
      setSurgeries(data.surgeries || []);
      if (!selectedId && data.surgeries?.length) {
        setSelectedId(data.surgeries[0].surgery_id);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadSurgeryDetail(id) {
    if (!id) return;
    setError('');
    try {
      const data = await fetchSurgery(role, id);
      const detail = data.surgery || null;
      setSurgeryDetail(detail);

      // If we already have a readiness report loaded for this surgery,
      // re-hydrate the per-blocker decision badges from the stored record
      // so they survive tab switches or page refreshes.
      if (detail && readiness && readiness.blockers) {
        const stored = detail.blocker_decisions || [];
        const seeded = {};
        readiness.blockers.forEach((b, idx) => {
          const match = stored.find(
            (d) =>
              d.category === b.category &&
              d.message === b.message &&
              d.severity === (b.severity || null)
          );
          if (match) seeded[idx] = match.decision;
        });
        setBlockerDecisions(seeded);
      }

      // Sync the live review status badge
      if (detail?.readiness_review_status) {
        setReviewStatus(detail.readiness_review_status);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function runReadiness(id, forceRerun = false) {
    if (!id) return;
    setBusy(true);
    setError('');
    try {
      const data = await checkReadiness(role, id, forceRerun);
      setReadiness(data);

      // Seed per-blocker decisions from the stored blocker_decisions list
      // (populated for both cached reports and live runs where decisions already exist)
      const storedDecisions = data.blocker_decisions || [];
      if (data.blockers?.length && storedDecisions.length) {
        const seeded = {};
        data.blockers.forEach((b, idx) => {
          const match = storedDecisions.find(
            (d) => d.category === b.category && d.message === b.message,
          );
          if (match) seeded[idx] = match.decision;
        });
        setBlockerDecisions(seeded);
      } else {
        setBlockerDecisions({});
      }

      // Derive review status: prefer what the backend stored, fall back to pipeline status
      const rs = data.readiness_review_status
        || (data.readiness_status === 'READY' ? 'RESOLVED' : 'PENDING_REVIEW');
      setReviewStatus(rs);

      setActiveTab('readiness');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function decideBlocker(blocker, idx, decision) {
    setError('');
    try {
      const result = await submitBlockerDecision(role, selectedId, blocker, decision);
      // Update the per-blocker badge immediately
      setBlockerDecisions((prev) => ({ ...prev, [idx]: decision }));
      // Update the overall review status from what the backend computed
      if (result.readiness_review_status) {
        setReviewStatus(result.readiness_review_status);
      }
      // Refresh the surgery detail so the stored decisions stay in sync
      await loadSurgeryDetail(selectedId);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadAudit() {
    if (!selectedId) return;
    setBusy(true);
    setError('');
    try {
      const data = await fetchAudit(role, selectedId, auditLimit);
      setAuditTrail(data.audit_trail || []);
      setActiveTab('audit');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadSurgeries();
  }, [role]);

  useEffect(() => {
    // Reset readiness state when switching surgery so stale decisions don't bleed over
    setReadiness(null);
    setBlockerDecisions({});
    setReviewStatus(null);
    loadSurgeryDetail(selectedId);
  }, [selectedId, role]);

  return (
    <div className="app-shell">
      <div className="noise-layer" aria-hidden="true" />
      <header className="hero">
        <div className="hero-left">
          <p className="kicker">Critical Ops Dashboard</p>
          <h1>Critical Surgery Supply Coordinator</h1>
          <p className="subtitle">
            Decision-support only. Every readiness output requires qualified clinical review.
          </p>
        </div>
        <div className="hero-right">
          <label className="role-label" htmlFor="role">Role</label>
          <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
            {roles.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
      </header>

      <section className="disclaimer-banner">
        This system is for decision-support only. It does not authorize surgery, transfusion,
        organ allocation, or any medical procedure.
      </section>

      {error && <section className="error-banner">{error}</section>}

      <nav className="tabbar">
        <button className={activeTab === 'surgeries' ? 'tab active' : 'tab'} onClick={() => setActiveTab('surgeries')}>Surgeries</button>
        <button className={activeTab === 'readiness' ? 'tab active' : 'tab'} onClick={() => setActiveTab('readiness')}>Readiness</button>
        <button className={activeTab === 'audit' ? 'tab active' : 'tab'} onClick={() => setActiveTab('audit')}>Audit Trail</button>
      </nav>

      {activeTab === 'surgeries' && (
        <section className="panel-grid">
          <article className="panel">
            <div className="panel-header">
              <h2>Pending Surgeries</h2>
              <button className="btn ghost" onClick={loadSurgeries}>Refresh</button>
            </div>
            <div className="surgery-list">
              {surgeries.map((s) => {
                const pill = reviewPill(s);
                return (
                  <button
                    key={s.surgery_id}
                    className={s.surgery_id === selectedId ? 'surgery-card selected' : 'surgery-card'}
                    onClick={() => setSelectedId(s.surgery_id)}
                  >
                    <div className="surgery-card-main">
                      <p className="surgery-id">{s.surgery_id}</p>
                      <p className="surgery-meta">{s.surgery_type}</p>
                      <p className="surgery-meta">{new Date(s.scheduled_time).toLocaleString()}</p>
                    </div>
                    <div className="surgery-card-right">
                      <div className="tiny-pill">{s.required_blood_type} · {s.required_blood_units}u</div>
                      {pill && (
                        <span className={`review-pill ${pill.cls}`}>{pill.label}</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </article>

          <article className="panel">
            <div className="panel-header">
              <h2>Selected Surgery</h2>
              <div className="header-chips">
                {surgeryDetail?.readiness_review_status && surgeryDetail?.readiness_report && (
                  <span className={statusClass(surgeryDetail.readiness_review_status)}>
                    {reviewStatusLabel(surgeryDetail.readiness_review_status)}
                  </span>
                )}
                <button
                  className="btn"
                  disabled={!selectedId || busy}
                  onClick={() => runReadiness(selectedId)}
                >
                  {busy ? 'Running...' : 'Run Readiness Check'}
                </button>
              </div>
            </div>
            {surgeryDetail ? (
              <div>
                <div className="detail-grid">
                  <p><strong>ID:</strong> {surgeryDetail.surgery_id}</p>
                  <p><strong>Patient:</strong> {surgeryDetail.patient_id}</p>
                  <p><strong>Type:</strong> {surgeryDetail.surgery_type}</p>
                  <p><strong>Scheduled:</strong> {new Date(surgeryDetail.scheduled_time).toLocaleString()}</p>
                  <p><strong>Blood:</strong> {surgeryDetail.required_blood_type} ({surgeryDetail.required_blood_units} units)</p>
                  <p><strong>Duration:</strong> {surgeryDetail.estimated_duration_minutes} minutes</p>
                </div>
                {surgeryDetail.readiness_report && (
                  <div className="cached-notice">
                    <span>A readiness report exists for this surgery.</span>
                    <button
                      className="btn-rerun"
                      disabled={busy}
                      onClick={() => runReadiness(selectedId, true)}
                    >
                      {busy ? 'Running...' : 'Force Re-run'}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <p className="muted">Select a surgery to view details.</p>
            )}
          </article>
        </section>
      )}

      {activeTab === 'readiness' && (
        <section className="panel single">
          <div className="panel-header">
            <h2>Readiness Report</h2>
            <div className="header-chips">
              {readiness?.readiness_status && (
                <span className={statusClass(readiness.readiness_status)}>
                  {readiness.readiness_status}
                </span>
              )}
              {reviewStatus && (
                <span className={`chip review-status-chip ${statusClass(reviewStatus).replace('chip ', '')}`}>
                  {reviewStatusLabel(reviewStatus)}
                </span>
              )}
              {readiness?.cached && (
                <span className="chip chip-cached">Cached report</span>
              )}
            </div>
          </div>

          {!readiness && <p className="muted">Run a readiness check from Surgeries.</p>}

          {readiness && (
            <>
              {readiness.cached && (
                <div className="cached-report-notice">
                  <span>
                    This report was completed on{' '}
                    <strong>
                      {surgeryDetail?.last_updated
                        ? new Date(surgeryDetail.last_updated).toLocaleString()
                        : 'a previous session'}
                    </strong>
                    . The pipeline was not re-run.
                  </span>
                  <button
                    className="btn-rerun"
                    disabled={busy}
                    onClick={() => runReadiness(selectedId, true)}
                  >
                    {busy ? 'Running...' : 'Force Re-run'}
                  </button>
                </div>
              )}

              <p className="lead">{readiness.message || 'Readiness report generated.'}</p>

              {readiness.blockers?.length > 0 && (
                <div className="stack">
                  <h3>Critical Blockers</h3>
                  {readiness.blockers.map((b, idx) => {
                    const decision = blockerDecisions[idx];
                    const isResolved = decision === 'ACCEPT';
                    const isHalted = decision === 'REJECT';
                    return (
                      <article
                        key={`${b.category}-${idx}`}
                        className={`blocker-card ${isResolved ? 'blocker-resolved' : isHalted ? 'blocker-halted' : ''}`}
                      >
                        <div className="blocker-card-header">
                          <p className="blocker-title">[{b.category}] {b.message}</p>
                          {decision && (
                            <span className={`blocker-status-tag ${isResolved ? 'tag-resolved' : 'tag-halted'}`}>
                              {isResolved ? '✓ Status: Resolved' : '✕ Status: Halted'}
                            </span>
                          )}
                        </div>
                        <p className="blocker-meta">Severity: {b.severity || 'N/A'}</p>
                        <p className="blocker-meta">Action: {b.suggested_action || 'N/A'}</p>
                        <div className="decision-actions">
                          <button
                            className="btn-accept"
                            disabled={!!decision}
                            onClick={() => decideBlocker(b, idx, 'ACCEPT')}
                          >
                            Accept
                          </button>
                          <button
                            className="btn-reject"
                            disabled={!!decision}
                            onClick={() => decideBlocker(b, idx, 'REJECT')}
                          >
                            Reject
                          </button>
                          <span className={`decision-badge ${decision ? decision.toLowerCase() : 'pending'}`}>
                            {decisionLabel(decision)}
                          </span>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}

              {/* Overall review outcome banner — shown once all blockers have a decision */}
              {readiness.blockers?.length > 0 &&
                Object.keys(blockerDecisions).length === readiness.blockers.length && (
                  <div className={`review-outcome-banner ${reviewStatus === 'RESOLVED' ? 'outcome-resolved' : 'outcome-halted'}`}>
                    {reviewStatus === 'RESOLVED'
                      ? '✓ All blockers have been reviewed and resolved. Cleared for clinical sign-off.'
                      : '✕ One or more blockers were rejected. Surgery is halted pending further review.'}
                  </div>
              )}

              {readiness.warnings?.length > 0 && (
                <div className="stack">
                  <h3>Warnings</h3>
                  {readiness.warnings.map((w, idx) => (
                    <article key={`warn-${idx}`} className="warning-card">{w}</article>
                  ))}
                </div>
              )}

              {readiness.blood_status && (
                <div className="stack">
                  <h3>Blood Bank</h3>
                  <article className="info-card">
                    <p><strong>Status:</strong> {readiness.blood_status.status}</p>
                    <p><strong>Details:</strong> {readiness.blood_status.details}</p>
                  </article>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {activeTab === 'audit' && (
        <section className="panel single">
          <div className="panel-header">
            <h2>Audit Trail</h2>
            <div className="audit-controls">
              <input
                type="number"
                min="10"
                max="500"
                value={auditLimit}
                onChange={(e) => setAuditLimit(Number(e.target.value || 100))}
              />
              <button className="btn" disabled={!selectedId || busy} onClick={loadAudit}>
                {busy ? 'Loading...' : 'Load Audit'}
              </button>
            </div>
          </div>

          {!auditTrail.length && <p className="muted">No entries loaded yet.</p>}

          {auditTrail.map((entry) => (
            <details key={entry.entry_id || `${entry.timestamp}-${entry.action}`} className="audit-item">
              <summary>
                <span>{entry.timestamp || 'N/A'}</span>
                <span>{entry.action || 'N/A'}</span>
              </summary>
              <pre>{JSON.stringify(entry, null, 2)}</pre>
            </details>
          ))}
        </section>
      )}
    </div>
  );
}

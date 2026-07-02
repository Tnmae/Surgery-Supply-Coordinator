import { useEffect, useMemo, useState } from 'react';
import { checkReadiness, fetchAudit, fetchSurgery, fetchSurgeries, submitBlockerDecision } from './api';

const roles = ['OR_COORDINATOR', 'SUPPLY_ADMIN', 'BLOOD_BANK_TECH', 'VIEWER'];

function statusClass(status) {
  if (status === 'READY') return 'chip chip-ready';
  if (status === 'BLOCKED') return 'chip chip-blocked';
  return 'chip chip-warning';
}

export default function App() {
  const [role, setRole] = useState('OR_COORDINATOR');
  const [surgeries, setSurgeries] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [surgeryDetail, setSurgeryDetail] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [blockerDecisions, setBlockerDecisions] = useState({});
  const [auditTrail, setAuditTrail] = useState([]);
  const [auditLimit, setAuditLimit] = useState(100);
  const [activeTab, setActiveTab] = useState('surgeries');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
      setSurgeryDetail(data.surgery || null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function runReadiness(id) {
    if (!id) return;
    setBusy(true);
    setError('');
    try {
      const data = await checkReadiness(role, id);
      setReadiness(data);
      setBlockerDecisions({});
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
      await submitBlockerDecision(role, selectedId, blocker, decision);
      setBlockerDecisions((prev) => ({ ...prev, [idx]: decision }));
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
              {surgeries.map((s) => (
                <button
                  key={s.surgery_id}
                  className={s.surgery_id === selectedId ? 'surgery-card selected' : 'surgery-card'}
                  onClick={() => setSelectedId(s.surgery_id)}
                >
                  <div>
                    <p className="surgery-id">{s.surgery_id}</p>
                    <p className="surgery-meta">{s.surgery_type}</p>
                    <p className="surgery-meta">{new Date(s.scheduled_time).toLocaleString()}</p>
                  </div>
                  <div className="tiny-pill">{s.required_blood_type} · {s.required_blood_units}u</div>
                </button>
              ))}
            </div>
          </article>

          <article className="panel">
            <div className="panel-header">
              <h2>Selected Surgery</h2>
              <button className="btn" disabled={!selectedId || busy} onClick={() => runReadiness(selectedId)}>
                {busy ? 'Running...' : 'Run Readiness Check'}
              </button>
            </div>
            {surgeryDetail ? (
              <div className="detail-grid">
                <p><strong>ID:</strong> {surgeryDetail.surgery_id}</p>
                <p><strong>Patient:</strong> {surgeryDetail.patient_id}</p>
                <p><strong>Type:</strong> {surgeryDetail.surgery_type}</p>
                <p><strong>Scheduled:</strong> {new Date(surgeryDetail.scheduled_time).toLocaleString()}</p>
                <p><strong>Blood:</strong> {surgeryDetail.required_blood_type} ({surgeryDetail.required_blood_units} units)</p>
                <p><strong>Duration:</strong> {surgeryDetail.estimated_duration_minutes} minutes</p>
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
            {readiness?.readiness_status && (
              <span className={statusClass(readiness.readiness_status)}>{readiness.readiness_status}</span>
            )}
          </div>

          {!readiness && <p className="muted">Run a readiness check from Surgeries.</p>}

          {readiness && (
            <>
              <p className="lead">{readiness.message || 'Readiness report generated.'}</p>

              {readiness.blockers?.length > 0 && (
                <div className="stack">
                  <h3>Critical Blockers</h3>
                  {readiness.blockers.map((b, idx) => {
                    const decision = blockerDecisions[idx];
                    return (
                      <article key={`${b.category}-${idx}`} className="blocker-card">
                        <p className="blocker-title">[{b.category}] {b.message}</p>
                        <p className="blocker-meta">Severity: {b.severity || 'N/A'}</p>
                        <p className="blocker-meta">Action: {b.suggested_action || 'N/A'}</p>
                        <div className="decision-actions">
                          <button
                            className="btn-accept"
                            disabled={decision === 'ACCEPT'}
                            onClick={() => decideBlocker(b, idx, 'ACCEPT')}
                          >
                            Accept
                          </button>
                          <button
                            className="btn-reject"
                            disabled={decision === 'REJECT'}
                            onClick={() => decideBlocker(b, idx, 'REJECT')}
                          >
                            Reject
                          </button>
                          <span className={`decision-badge ${decision ? decision.toLowerCase() : 'pending'}`}>
                            {decision === 'ACCEPT' ? 'Accepted' : decision === 'REJECT' ? 'Rejected' : 'Pending review'}
                          </span>
                        </div>
                      </article>
                    );
                  })}
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

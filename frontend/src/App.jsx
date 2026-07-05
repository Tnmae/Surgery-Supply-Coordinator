import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Stethoscope,
  ShieldCheck,
  ClipboardList,
  Activity,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Droplets,
  AlertTriangle,
  ShieldAlert,
  UserCog,
  Calendar,
  Clock,
  User,
  Hash,
  Syringe,
  Timer,
  Loader2,
  Info,
} from 'lucide-react';
import { checkReadiness, fetchAudit, fetchSurgery, fetchSurgeries, submitBlockerDecision } from './api';
import DNAHelix from './DNAHelix';

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

/* ── Animation Variants ────────────────────────────────────────────── */

const pageVariants = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2, ease: 'easeIn' } },
};

const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.05,
    },
  },
};

const cardVariant = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] } },
};

const panelVariant = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] } },
};

const blockerVariant = {
  initial: { opacity: 0, x: -12 },
  animate: { opacity: 1, x: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
};

const badgeVariant = {
  initial: { scale: 0, opacity: 0 },
  animate: { scale: 1, opacity: 1, transition: { type: 'spring', stiffness: 400, damping: 20 } },
};

/* ── Tab Definitions ───────────────────────────────────────────────── */

const tabDefs = [
  { key: 'surgeries', label: 'Surgeries', icon: Stethoscope },
  { key: 'readiness', label: 'Readiness', icon: ShieldCheck },
  { key: 'audit', label: 'Audit Trail', icon: ClipboardList },
];

/* ── Cursor Glow Component ─────────────────────────────────────────── */

function CursorGlow() {
  const glowRef = useRef(null);

  useEffect(() => {
    const el = glowRef.current;
    if (!el) return;

    let raf;
    const onMove = (e) => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        el.style.left = e.clientX + 'px';
        el.style.top = e.clientY + 'px';
        el.style.opacity = '1';
      });
    };

    const onLeave = () => {
      el.style.opacity = '0';
    };

    window.addEventListener('mousemove', onMove, { passive: true });
    document.addEventListener('mouseleave', onLeave);

    return () => {
      window.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseleave', onLeave);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return <div ref={glowRef} className="cursor-glow" aria-hidden="true" />;
}

/* ── GlassPanel — panel with cursor-tracking internal glow ─────────── */

function GlassPanel({ children, className = '', variants, ...motionProps }) {
  const panelRef = useRef(null);

  const handleMouseMove = useCallback((e) => {
    const el = panelRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    el.style.setProperty('--mouse-x', x + '%');
    el.style.setProperty('--mouse-y', y + '%');
  }, []);

  return (
    <motion.article
      ref={panelRef}
      className={`panel ${className}`}
      variants={variants}
      onMouseMove={handleMouseMove}
      {...motionProps}
    >
      <div className="panel-glow" />
      {children}
    </motion.article>
  );
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
  const [refreshing, setRefreshing] = useState(false);

  const selectedSurgery = useMemo(
    () => surgeries.find((s) => s.surgery_id === selectedId),
    [surgeries, selectedId]
  );

  async function loadSurgeries() {
    setError('');
    setRefreshing(true);
    try {
      const data = await fetchSurgeries(role);
      setSurgeries(data.surgeries || []);
      if (!selectedId && data.surgeries?.length) {
        setSelectedId(data.surgeries[0].surgery_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
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
      <DNAHelix />
      <CursorGlow />

      {/* ── Hero Header ───────────────────────────────────────────── */}
      <motion.header
        className="hero"
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="hero-left">
          <motion.p
            className="kicker"
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15, duration: 0.4 }}
          >
            <Activity size={13} /> Critical Ops Dashboard
          </motion.p>
          <h1>Critical Surgery Supply Coordinator</h1>
          <p className="subtitle">
            Decision-support only. Every readiness output requires qualified clinical review.
          </p>
        </div>
        <div className="hero-right">
          <label className="role-label" htmlFor="role">
            <UserCog size={13} /> Role
          </label>
          <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
            {roles.map((r) => (
              <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>
      </motion.header>

      {/* ── Disclaimer Banner ─────────────────────────────────────── */}
      <motion.section
        className="disclaimer-banner"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.4 }}
      >
        <AlertTriangle size={16} style={{ flexShrink: 0 }} />
        This system is for decision-support only. It does not authorize surgery, transfusion,
        organ allocation, or any medical procedure.
      </motion.section>

      {/* ── Error Banner ──────────────────────────────────────────── */}
      <AnimatePresence>
        {error && (
          <motion.section
            className="error-banner"
            initial={{ opacity: 0, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, height: 'auto', marginBottom: 20 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            transition={{ duration: 0.25 }}
          >
            <XCircle size={16} style={{ flexShrink: 0 }} />
            {error}
          </motion.section>
        )}
      </AnimatePresence>

      {/* ── Tab Bar ───────────────────────────────────────────────── */}
      <motion.nav
        className="tabbar"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.4 }}
      >
        {tabDefs.map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.key;
          return (
            <button
              key={t.key}
              className={isActive ? 'tab active' : 'tab'}
              onClick={() => setActiveTab(t.key)}
              style={{ position: 'relative' }}
            >
              {isActive && (
                <motion.div
                  className="tab-indicator"
                  layoutId="tab-indicator"
                  transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                />
              )}
              <Icon size={16} className="tab-icon" />
              <span style={{ position: 'relative', zIndex: 1 }}>{t.label}</span>
            </button>
          );
        })}
      </motion.nav>

      {/* ── Tab Content ───────────────────────────────────────────── */}
      <AnimatePresence mode="wait">

        {/* ════════════════ SURGERIES TAB ════════════════════════════ */}
        {activeTab === 'surgeries' && (
          <motion.section
            key="surgeries"
            className="panel-grid"
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {/* Left panel — Surgery list */}
            <GlassPanel variants={panelVariant}>
              <div className="panel-header">
                <h2><Stethoscope size={18} /> Pending Surgeries</h2>
                <motion.button
                  className="btn ghost"
                  onClick={loadSurgeries}
                  whileHover={{ scale: 1.04, y: -1 }}
                  whileTap={{ scale: 0.96 }}
                >
                  <RefreshCw size={14} className={refreshing ? 'icon-spin' : ''} />
                  Refresh
                </motion.button>
              </div>
              <motion.div
                className="surgery-list"
                variants={staggerContainer}
                initial="initial"
                animate="animate"
              >
                {surgeries.map((s) => {
                  const pill = reviewPill(s);
                  return (
                    <motion.button
                      key={s.surgery_id}
                      className={s.surgery_id === selectedId ? 'surgery-card selected' : 'surgery-card'}
                      onClick={() => setSelectedId(s.surgery_id)}
                      variants={cardVariant}
                      whileHover={{ scale: 1.015, y: -2 }}
                      whileTap={{ scale: 0.985 }}
                    >
                      <div className="surgery-card-main">
                        <p className="surgery-id">{s.surgery_id}</p>
                        <p className="surgery-meta">{s.surgery_type}</p>
                        <p className="surgery-meta">{new Date(s.scheduled_time).toLocaleString()}</p>
                      </div>
                      <div className="surgery-card-right">
                        <div className="tiny-pill">
                          <Droplets size={11} style={{ marginRight: 3, verticalAlign: 'middle' }} />
                          {s.required_blood_type} · {s.required_blood_units}u
                        </div>
                        {pill && (
                          <span className={`review-pill ${pill.cls}`}>{pill.label}</span>
                        )}
                      </div>
                    </motion.button>
                  );
                })}
              </motion.div>
            </GlassPanel>

            {/* Right panel — Selected surgery detail */}
            <GlassPanel variants={panelVariant}>
              <div className="panel-header">
                <h2><Info size={18} /> Selected Surgery</h2>
                <div className="header-chips">
                  {surgeryDetail?.readiness_review_status && surgeryDetail?.readiness_report && (
                    <motion.span
                      className={statusClass(surgeryDetail.readiness_review_status)}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    >
                      {reviewStatusLabel(surgeryDetail.readiness_review_status)}
                    </motion.span>
                  )}
                  <motion.button
                    className="btn"
                    disabled={!selectedId || busy}
                    onClick={() => runReadiness(selectedId)}
                    whileHover={{ scale: 1.03, y: -1 }}
                    whileTap={{ scale: 0.97 }}
                  >
                    {busy ? (
                      <><Loader2 size={14} className="icon-spin" /> Running...</>
                    ) : (
                      <><Activity size={14} /> Run Readiness Check</>
                    )}
                  </motion.button>
                </div>
              </div>
              {surgeryDetail ? (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className="detail-grid">
                    <p>
                      <Hash size={14} className="detail-icon" />
                      <strong>ID:</strong> {surgeryDetail.surgery_id}
                    </p>
                    <p>
                      <User size={14} className="detail-icon" />
                      <strong>Patient:</strong> {surgeryDetail.patient_id}
                    </p>
                    <p>
                      <Syringe size={14} className="detail-icon" />
                      <strong>Type:</strong> {surgeryDetail.surgery_type}
                    </p>
                    <p>
                      <Calendar size={14} className="detail-icon" />
                      <strong>Scheduled:</strong> {new Date(surgeryDetail.scheduled_time).toLocaleString()}
                    </p>
                    <p>
                      <Droplets size={14} className="detail-icon" />
                      <strong>Blood:</strong> {surgeryDetail.required_blood_type} ({surgeryDetail.required_blood_units} units)
                    </p>
                    <p>
                      <Timer size={14} className="detail-icon" />
                      <strong>Duration:</strong> {surgeryDetail.estimated_duration_minutes} minutes
                    </p>
                  </div>
                  {surgeryDetail.readiness_report && (
                    <motion.div
                      className="cached-notice"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.15, duration: 0.3 }}
                    >
                      <span><Info size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />A readiness report exists for this surgery.</span>
                      <motion.button
                        className="btn-rerun"
                        disabled={busy}
                        onClick={() => runReadiness(selectedId, true)}
                        whileHover={{ scale: 1.04, y: -1 }}
                        whileTap={{ scale: 0.96 }}
                      >
                        {busy ? (
                          <><Loader2 size={12} className="icon-spin" /> Running...</>
                        ) : (
                          <><RefreshCw size={12} /> Force Re-run</>
                        )}
                      </motion.button>
                    </motion.div>
                  )}
                </motion.div>
              ) : (
                <p className="muted">Select a surgery to view details.</p>
              )}
            </GlassPanel>
          </motion.section>
        )}

        {/* ════════════════ READINESS TAB ════════════════════════════ */}
        {activeTab === 'readiness' && (
          <motion.section
            key="readiness"
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <GlassPanel className="single">
              <div className="panel-header">
                <h2><ShieldCheck size={18} /> Readiness Report</h2>
                <div className="header-chips">
                  {readiness?.readiness_status && (
                    <motion.span
                      className={statusClass(readiness.readiness_status)}
                      variants={badgeVariant}
                      initial="initial"
                      animate="animate"
                    >
                      {readiness.readiness_status}
                    </motion.span>
                  )}
                  {reviewStatus && (
                    <motion.span
                      className={`chip review-status-chip ${statusClass(reviewStatus).replace('chip ', '')}`}
                      variants={badgeVariant}
                      initial="initial"
                      animate="animate"
                    >
                      {reviewStatusLabel(reviewStatus)}
                    </motion.span>
                  )}
                  {readiness?.cached && (
                    <motion.span
                      className="chip chip-cached"
                      variants={badgeVariant}
                      initial="initial"
                      animate="animate"
                    >
                      Cached report
                    </motion.span>
                  )}
                </div>
              </div>

              {!readiness && <p className="muted">Run a readiness check from Surgeries.</p>}

              {readiness && (
                <>
                  {readiness.cached && (
                    <motion.div
                      className="cached-report-notice"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1, duration: 0.3 }}
                    >
                      <span>
                        <Clock size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                        This report was completed on{' '}
                        <strong>
                          {surgeryDetail?.last_updated
                            ? new Date(surgeryDetail.last_updated).toLocaleString()
                            : 'a previous session'}
                        </strong>
                        . The pipeline was not re-run.
                      </span>
                      <motion.button
                        className="btn-rerun"
                        disabled={busy}
                        onClick={() => runReadiness(selectedId, true)}
                        whileHover={{ scale: 1.04, y: -1 }}
                        whileTap={{ scale: 0.96 }}
                      >
                        {busy ? (
                          <><Loader2 size={12} className="icon-spin" /> Running...</>
                        ) : (
                          <><RefreshCw size={12} /> Force Re-run</>
                        )}
                      </motion.button>
                    </motion.div>
                  )}

                  <p className="lead">{readiness.message || 'Readiness report generated.'}</p>

                  {readiness.blockers?.length > 0 && (
                    <motion.div
                      className="stack"
                      variants={staggerContainer}
                      initial="initial"
                      animate="animate"
                    >
                      <h3><ShieldAlert size={16} /> Critical Blockers</h3>
                      {readiness.blockers.map((b, idx) => {
                        const decision = blockerDecisions[idx];
                        const isResolved = decision === 'ACCEPT';
                        const isHalted = decision === 'REJECT';
                        return (
                          <motion.article
                            key={`${b.category}-${idx}`}
                            className={`blocker-card ${isResolved ? 'blocker-resolved' : isHalted ? 'blocker-halted' : ''}`}
                            variants={blockerVariant}
                            whileHover={{ y: -1 }}
                          >
                            <div className="blocker-card-header">
                              <p className="blocker-title">
                                <ShieldAlert size={14} style={{ color: isResolved ? 'var(--success)' : 'var(--danger)' }} />
                                [{b.category}] {b.message}
                              </p>
                              <AnimatePresence>
                                {decision && (
                                  <motion.span
                                    className={`blocker-status-tag ${isResolved ? 'tag-resolved' : 'tag-halted'}`}
                                    initial={{ scale: 0, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                                  >
                                    {isResolved ? '✓ Status: Resolved' : '✕ Status: Halted'}
                                  </motion.span>
                                )}
                              </AnimatePresence>
                            </div>
                            <p className="blocker-meta">Severity: {b.severity || 'N/A'}</p>
                            <p className="blocker-meta">Action: {b.suggested_action || 'N/A'}</p>
                            <div className="decision-actions">
                              <motion.button
                                className="btn-accept"
                                disabled={!!decision}
                                onClick={() => decideBlocker(b, idx, 'ACCEPT')}
                                whileHover={{ scale: 1.06, y: -1 }}
                                whileTap={{ scale: 0.94 }}
                              >
                                <CheckCircle2 size={13} /> Accept
                              </motion.button>
                              <motion.button
                                className="btn-reject"
                                disabled={!!decision}
                                onClick={() => decideBlocker(b, idx, 'REJECT')}
                                whileHover={{ scale: 1.06, y: -1 }}
                                whileTap={{ scale: 0.94 }}
                              >
                                <XCircle size={13} /> Reject
                              </motion.button>
                              <AnimatePresence mode="wait">
                                <motion.span
                                  key={decision || 'pending'}
                                  className={`decision-badge ${decision ? decision.toLowerCase() : 'pending'}`}
                                  initial={{ scale: 0, opacity: 0 }}
                                  animate={{ scale: 1, opacity: 1 }}
                                  exit={{ scale: 0, opacity: 0 }}
                                  transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                                >
                                  {decisionLabel(decision)}
                                </motion.span>
                              </AnimatePresence>
                            </div>
                          </motion.article>
                        );
                      })}
                    </motion.div>
                  )}

                  {/* Overall review outcome banner */}
                  <AnimatePresence>
                    {readiness.blockers?.length > 0 &&
                      Object.keys(blockerDecisions).length === readiness.blockers.length && (
                        <motion.div
                          className={`review-outcome-banner ${reviewStatus === 'RESOLVED' ? 'outcome-resolved' : 'outcome-halted'}`}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                        >
                          {reviewStatus === 'RESOLVED' ? (
                            <><CheckCircle2 size={18} /> All blockers have been reviewed and resolved. Cleared for clinical sign-off.</>
                          ) : (
                            <><XCircle size={18} /> One or more blockers were rejected. Surgery is halted pending further review.</>
                          )}
                        </motion.div>
                    )}
                  </AnimatePresence>

                  {readiness.warnings?.length > 0 && (
                    <motion.div
                      className="stack"
                      variants={staggerContainer}
                      initial="initial"
                      animate="animate"
                    >
                      <h3><AlertTriangle size={16} /> Warnings</h3>
                      {readiness.warnings.map((w, idx) => (
                        <motion.article
                          key={`warn-${idx}`}
                          className="warning-card"
                          variants={cardVariant}
                          whileHover={{ y: -1 }}
                        >
                          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                          {w}
                        </motion.article>
                      ))}
                    </motion.div>
                  )}

                  {readiness.blood_status && (
                    <motion.div
                      className="stack"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.15, duration: 0.35 }}
                    >
                      <h3><Droplets size={16} /> Blood Bank</h3>
                      <article className="info-card">
                        <p><strong>Status:</strong> {readiness.blood_status.status}</p>
                        <p><strong>Details:</strong> {readiness.blood_status.details}</p>
                      </article>
                    </motion.div>
                  )}
                </>
              )}
            </GlassPanel>
          </motion.section>
        )}

        {/* ════════════════ AUDIT TAB ════════════════════════════════ */}
        {activeTab === 'audit' && (
          <motion.section
            key="audit"
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <GlassPanel className="single">
              <div className="panel-header">
                <h2><ClipboardList size={18} /> Audit Trail</h2>
                <div className="audit-controls">
                  <input
                    type="number"
                    min="10"
                    max="500"
                    value={auditLimit}
                    onChange={(e) => setAuditLimit(Number(e.target.value || 100))}
                  />
                  <motion.button
                    className="btn"
                    disabled={!selectedId || busy}
                    onClick={loadAudit}
                    whileHover={{ scale: 1.03, y: -1 }}
                    whileTap={{ scale: 0.97 }}
                  >
                    {busy ? (
                      <><Loader2 size={14} className="icon-spin" /> Loading...</>
                    ) : (
                      <><ClipboardList size={14} /> Load Audit</>
                    )}
                  </motion.button>
                </div>
              </div>

              {!auditTrail.length && <p className="muted">No entries loaded yet.</p>}

              <motion.div
                variants={staggerContainer}
                initial="initial"
                animate="animate"
              >
                {auditTrail.map((entry) => (
                  <motion.details
                    key={entry.entry_id || `${entry.timestamp}-${entry.action}`}
                    className="audit-item"
                    variants={cardVariant}
                    style={{ marginBottom: 8 }}
                  >
                    <summary>
                      <span>{entry.timestamp || 'N/A'}</span>
                      <span>{entry.action || 'N/A'}</span>
                    </summary>
                    <pre>{JSON.stringify(entry, null, 2)}</pre>
                  </motion.details>
                ))}
              </motion.div>
            </GlassPanel>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  );
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function headers(role) {
  return {
    'Content-Type': 'application/json',
    'user-role': role,
  };
}

async function parse(res) {
  // Read the body as text first so we can give a useful error if it's not JSON
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    // Got HTML or plain text — the backend URL is likely wrong or unreachable
    throw new Error(
      `Backend returned non-JSON response (HTTP ${res.status}). ` +
      `Check that VITE_API_BASE_URL is set correctly in Vercel environment variables. ` +
      `Received: ${text.slice(0, 120)}`
    );
  }
  if (!res.ok) {
    const message = data?.detail || data?.message || `Request failed with ${res.status}`;
    throw new Error(message);
  }
  // Pipeline failures return HTTP 200 with success:false — surface the detail
  if (data?.success === false) {
    const detail = data?.error
      ? `${data.message} — ${data.error}`
      : data?.message || 'Pipeline returned an error';
    throw new Error(detail);
  }
  return data;
}

export async function fetchSurgeries(role) {
  const res = await fetch(`${API_BASE}/surgeries`, { headers: headers(role) });
  return parse(res);
}

export async function fetchSurgery(role, surgeryId) {
  const res = await fetch(`${API_BASE}/surgeries/${surgeryId}`, { headers: headers(role) });
  return parse(res);
}

export async function checkReadiness(role, surgeryId, forceRerun = false) {
  const res = await fetch(`${API_BASE}/check-readiness`, {
    method: 'POST',
    headers: headers(role),
    body: JSON.stringify({
      surgery_id: surgeryId,
      user_role: role,
      requested_at: new Date().toISOString(),
      force_rerun: forceRerun,
    }),
  });
  return parse(res);
}

export async function fetchAudit(role, surgeryId, limit = 100) {
  const res = await fetch(`${API_BASE}/audit/${surgeryId}?limit=${limit}`, { headers: headers(role) });
  return parse(res);
}

export async function submitBlockerDecision(role, surgeryId, blocker, decision) {
  const res = await fetch(`${API_BASE}/surgeries/${surgeryId}/blockers/decision`, {
    method: 'POST',
    headers: headers(role),
    body: JSON.stringify({
      category: blocker.category,
      message: blocker.message,
      severity: blocker.severity,
      suggested_action: blocker.suggested_action,
      decision,
    }),
  });
  return parse(res);
}

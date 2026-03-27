const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// API kulcs localStorage-ból
export function getApiKey()        { return localStorage.getItem('da-api-key') || '' }
export function setApiKey(key)     { localStorage.setItem('da-api-key', key) }
export function clearApiKey()      { localStorage.removeItem('da-api-key') }

function authHeaders(extra = {}) {
  const key = getApiKey()
  return key ? { 'X-API-Key': key, ...extra } : extra
}

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    signal: opts.signal || AbortSignal.timeout(10000),
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...opts.headers,
    },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const api = {
  dashboard:  ()          => req('/api/dashboard'),
  health:     ()          => req('/api/health'),
  aiInsights: ()          => req('/api/ai-insights', { signal: AbortSignal.timeout(20000) }),

  emails: (status, limit = 50, offset = 0) => {
    const q = new URLSearchParams({ limit, offset, ...(status && { status }) })
    return req(`/api/emails?${q}`)
  },

  deleteEmail: (id) =>
    req(`/api/emails/${id}`, { method: 'DELETE' }),

  updateStatus: (id, status, note = '') =>
    req(`/api/emails/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, note }),
    }),

  classify: (subject, body, sender = '') =>
    req('/api/classify', {
      method: 'POST',
      body: JSON.stringify({ subject, body, sender }),
    }),

  feedback: (email_id, original_ai_decision, new_status, note = '') =>
    req('/api/feedback', {
      method: 'POST',
      body: JSON.stringify({ email_id, original_ai_decision, new_status, note }),
    }),

  upload: (formData) =>
    fetch(`${BASE}/api/upload`, {
      method: 'POST',
      body: formData,
      headers: authHeaders(),
      signal: AbortSignal.timeout(90000),
    }).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }),
}

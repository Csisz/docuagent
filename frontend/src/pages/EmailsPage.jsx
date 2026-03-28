import { useEffect, useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import clsx from 'clsx'
import { api } from '../services/api'
import { useStore } from '../store'
import { StatusBadge, ConfBar, Skeleton } from '../components/ui'
import { useToast } from '../hooks'

const FILTERS = [null, 'NEW', 'AI_ANSWERED', 'NEEDS_ATTENTION', 'CLOSED']
const FILTER_LABELS = { null: 'Összes', NEW: 'NEW', AI_ANSWERED: 'AI_ANSWERED', NEEDS_ATTENTION: 'NEEDS_ATTENTION', CLOSED: 'CLOSED' }
const STATUSES = ['NEW', 'AI_ANSWERED', 'NEEDS_ATTENTION', 'CLOSED']

const SENTIMENT_CFG = {
  angry:     { icon: '😠', label: 'Dühös',    cls: 'bg-red-500/15 text-red-400 border-red-400/25' },
  neutral:   { icon: '😐', label: 'Semleges', cls: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20' },
  satisfied: { icon: '😊', label: 'Elégedett',cls: 'bg-green-500/15 text-green-400 border-green-400/25' },
}

function SentimentBadge({ sentiment }) {
  if (!sentiment || sentiment === 'neutral') return null
  const cfg = SENTIMENT_CFG[sentiment] || SENTIMENT_CFG.neutral
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded border ${cfg.cls}`}>
      {cfg.icon} {cfg.label}
    </span>
  )
}

function SlaBadge({ createdAt, warningH, breachH }) {
  if (!createdAt || !warningH) return null
  const ageH = (Date.now() - new Date(createdAt).getTime()) / 3600000
  if (ageH >= breachH) return (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded border bg-red-500/15 text-red-400 border-red-400/25">
      🔴 {ageH.toFixed(1)}h
    </span>
  )
  if (ageH >= warningH) return (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded border bg-amber-500/15 text-amber-400 border-amber-400/25">
      ⚠ {ageH.toFixed(1)}h
    </span>
  )
  return null
}

export default function EmailsPage({ defaultFilter }) {
  const location = useLocation()
  const { emails, emailTotal, setEmails, updateEmailStatus, deleteEmail, theme } = useStore()
  const toast = useToast()
  const [loading, setLoading]       = useState(false)
  const [expanded, setExpanded]     = useState(null)
  const [selected, setSelected]     = useState(new Set())
  const [bulkStatus, setBulkStatus] = useState('')
  const [confirmModal, setConfirmModal] = useState(null) // { title, message, onConfirm }

  const openConfirm = useCallback((title, message, onConfirm) => {
    setConfirmModal({ title, message, onConfirm })
  }, [])
  const closeConfirm = useCallback(() => setConfirmModal(null), [])
  const [activeFilter, setActiveFilter] = useState(
    location.state?.filter ?? defaultFilter ?? null
  )
  const [slaConfig, setSlaConfig] = useState({ warning_hours: null, breach_hours: null })
  const didMount = useRef(false)

  useEffect(() => {
    api.getSlaConfig().then(cfg => setSlaConfig(cfg)).catch(() => {})
  }, [])

  useEffect(() => { loadEmails(activeFilter) }, []) // eslint-disable-line

  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    const f = location.state?.filter ?? defaultFilter ?? null
    setActiveFilter(f)
    loadEmails(f)
    setExpanded(null)
    setSelected(new Set())
  }, [location.key, defaultFilter]) // eslint-disable-line

  async function loadEmails(filter) {
    setLoading(true)
    try {
      const d = await api.emails(filter)
      setEmails(d.emails || [], d.total || 0)
      setSelected(new Set())
    } catch { toast('Backend nem elérhető', 'err') }
    finally { setLoading(false) }
  }

  function handleFilter(f) {
    setActiveFilter(f)
    loadEmails(f)
    setExpanded(null)
    setSelected(new Set())
  }

  function toggleSelect(id) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    setSelected(selected.size === emails.length ? new Set() : new Set(emails.map(e => e.id)))
  }

  async function handleBulkStatus() {
    if (!bulkStatus || selected.size === 0) return
    let ok = 0
    for (const id of selected) {
      try { await api.updateStatus(id, bulkStatus); updateEmailStatus(id, bulkStatus); ok++ } catch {}
    }
    toast(`✓ ${ok} email → ${bulkStatus}`, 'ok')
    setSelected(new Set())
    setBulkStatus('')
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return
    openConfirm(
      'Tömeges törlés',
      `Biztosan törlöd a kijelölt ${selected.size} emailt? Ez a művelet nem vonható vissza.`,
      async () => {
        let ok = 0
        for (const id of selected) {
          try { await api.deleteEmail(id); deleteEmail(id); ok++ } catch {}
        }
        toast(`✓ ${ok} email törölve`, 'ok')
        setSelected(new Set())
      }
    )
  }

  function handleDelete(emailId) {
    openConfirm(
      'Email törlése',
      'Biztosan törlöd ezt az emailt? Ez a művelet nem vonható vissza.',
      async () => {
        try {
          await api.deleteEmail(emailId)
          deleteEmail(emailId)
          toast('✓ Email törölve', 'ok')
          if (expanded === emailId) setExpanded(null)
        } catch (e) { toast(`Hiba: ${e.message}`, 'err') }
      }
    )
  }

  async function handleStatusChange(email, newStatus, sel) {
    if (email.status === newStatus) return
    try {
      const res = await api.updateStatus(email.id, newStatus)
      updateEmailStatus(email.id, newStatus)
      toast(`✓ ${email.status} → ${newStatus}${res.learning_stored ? ' · 🧠 tanulás' : ''}`, 'ok')
    } catch (e) {
      toast(`Hiba: ${e.message}`, 'err')
      sel.value = email.status
    }
  }

  const isLight = theme === 'light'
  const allSelected = emails.length > 0 && selected.size === emails.length
  const someSelected = selected.size > 0

  return (
    <div className="animate-fade-up">
      <p className="text-[11.5px] text-zinc-500 font-mono mb-3">
        Státusz szerkesztés · Human-in-the-loop tanulás ·{' '}
        <span className="text-orange-400">🧠 LEARNED = AI tanult</span>
      </p>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-[11px] text-zinc-600 font-mono font-semibold">Szűrő:</span>
        {FILTERS.map(f => (
          <button
            key={String(f)}
            onClick={() => handleFilter(f)}
            className={clsx(
              'px-3 py-1 rounded-full text-[11px] font-mono font-medium border transition-all',
              activeFilter === f
                ? 'bg-[#ff7820] border-[#ff7820] text-white'
                : 'bg-white/5 border-white/13 text-zinc-400 hover:border-[#ff7820]/50 hover:text-orange-400'
            )}
          >
            {FILTER_LABELS[String(f)]}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[11px] text-zinc-600">{emails.length} / {emailTotal}</span>
          <button className="btn-ghost text-[11px] px-3 py-1" onClick={() => loadEmails(activeFilter)}>↻</button>
        </div>
      </div>

      {/* Bulk action bar */}
      {someSelected && (
        <div className={clsx(
          'flex items-center gap-3 px-4 py-2.5 rounded-xl mb-3 border transition-all',
          isLight ? 'bg-orange-50 border-orange-200' : 'bg-orange-500/10 border-orange-400/25'
        )}>
          <span className={clsx('text-[12px] font-mono font-semibold', isLight ? 'text-orange-700' : 'text-orange-400')}>
            {selected.size} kijelölve
          </span>
          <div className="flex items-center gap-2 ml-auto flex-wrap">
            <select
              value={bulkStatus}
              onChange={e => setBulkStatus(e.target.value)}
              className={clsx(
                'text-[11px] font-mono border rounded px-2 py-1.5 outline-none transition-colors',
                isLight ? 'bg-white border-slate-300 text-slate-700' : 'bg-white/5 border-white/20 text-zinc-300'
              )}
            >
              <option value="">Státusz módosítás…</option>
              {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button
              onClick={handleBulkStatus}
              disabled={!bulkStatus}
              className="text-[11px] font-mono px-3 py-1.5 rounded bg-[#1a56db] text-white hover:bg-[#1e63f5] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Alkalmaz
            </button>
            <button
              onClick={handleBulkDelete}
              className="flex items-center gap-1.5 text-[11px] font-mono px-3 py-1.5 rounded bg-red-500/15 border border-red-400/30 text-red-400 hover:bg-red-500/25 transition-colors"
            >
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
                <path d="M2 4h10M5 4V2.5h4V4M5.5 6.5v4M8.5 6.5v4M3 4l.7 7.5h6.6L11 4"/>
              </svg>
              Törlés
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className={clsx('text-[12px] px-2 py-1.5 rounded transition-colors', isLight ? 'text-slate-500 hover:text-slate-700' : 'text-zinc-500 hover:text-zinc-300')}
            >✕</button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="glass rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className={clsx('border-b', isLight ? 'border-slate-200' : 'border-white/7')}>
                <th className={clsx('px-3 py-2.5 w-9', isLight ? 'bg-slate-50' : 'bg-white/[.02]')}>
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleSelectAll}
                    className="w-3.5 h-3.5 rounded accent-[#ff7820] cursor-pointer"
                  />
                </th>
                <th className={clsx('px-2 py-2.5 w-9', isLight ? 'bg-slate-50' : 'bg-white/[.02]')} />
                {['Tárgy', 'Feladó', 'Kategória', 'Státusz', 'Konf.', 'Dátum', 'Módosítás'].map(h => (
                  <th key={h} className={clsx('text-left px-3 py-2.5 text-[9.5px] font-bold uppercase tracking-[.08em] font-mono whitespace-nowrap', isLight ? 'bg-slate-50 text-slate-400' : 'bg-white/[.02] text-zinc-500')} style={h==='Státusz'?{minWidth:'160px'}:{}}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className={clsx('border-b', isLight ? 'border-slate-100' : 'border-white/5')}>
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j} className="px-3 py-2.5"><Skeleton className="h-3" /></td>
                    ))}
                  </tr>
                ))
                : emails.length === 0
                ? <tr><td colSpan={9} className="text-center py-12 text-zinc-600">Nincs email</td></tr>
                : emails.map(e => (
                  <EmailRow
                    key={e.id}
                    email={e}
                    expanded={expanded === e.id}
                    selected={selected.has(e.id)}
                    onToggle={() => setExpanded(expanded === e.id ? null : e.id)}
                    onSelect={() => toggleSelect(e.id)}
                    onStatusChange={handleStatusChange}
                    onDelete={handleDelete}
                    theme={theme}
                    slaConfig={slaConfig}
                  />
                ))
              }
            </tbody>
          </table>
        </div>
      </div>
      {confirmModal && (
        <ConfirmModal
          title={confirmModal.title}
          message={confirmModal.message}
          theme={theme}
          onConfirm={() => { confirmModal.onConfirm(); closeConfirm() }}
          onCancel={closeConfirm}
        />
      )}
    </div>
  )
}

function EmailRow({ email: e, expanded, selected, onToggle, onSelect, onStatusChange, onDelete, theme, slaConfig = {} }) {
  const isLight = theme === 'light'
  let aiD = {}
  try { aiD = typeof e.ai_decision === 'string' ? JSON.parse(e.ai_decision) : e.ai_decision || {} } catch {}

  const catColor = { complaint: 'text-red-400', inquiry: 'text-blue-400', other: 'text-zinc-500' }[e.category] || 'text-zinc-500'
  const dt = e.created_at ? new Date(e.created_at).toLocaleString('hu-HU', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'

  const statusBadge = {
    NEW:             <span className="inline-flex items-center gap-1 text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-400/20 whitespace-nowrap">NEW</span>,
    AI_ANSWERED:     <span className="inline-flex items-center gap-1 text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-green-500/15 text-green-400 border border-green-400/20 whitespace-nowrap">✓ AI_ANSWERED</span>,
    NEEDS_ATTENTION: <span className="inline-flex items-center gap-1 text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-400/20 whitespace-nowrap">⚠ NEEDS_ATTENTION</span>,
    CLOSED:          <span className="inline-flex items-center gap-1 text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-zinc-500/15 text-zinc-400 border border-zinc-400/20 whitespace-nowrap">CLOSED</span>,
  }[e.status] || <span className="text-zinc-500 font-mono text-[10px] whitespace-nowrap">{e.status}</span>

  return (
    <>
      <tr className={clsx(
        'border-b transition-colors',
        isLight ? 'border-slate-100' : 'border-white/5',
        selected
          ? (isLight ? 'bg-orange-50' : 'bg-orange-500/[.08]')
          : (isLight ? 'hover:bg-slate-50' : 'hover:bg-orange-500/[.04]')
      )}>

        {/* Checkbox */}
        <td className="px-3 py-2.5 w-9">
          <input
            type="checkbox"
            checked={selected}
            onChange={onSelect}
            className="w-3.5 h-3.5 rounded accent-[#ff7820] cursor-pointer"
          />
        </td>

        {/* Expand button — bigger chevron */}
        <td className="px-2 py-2.5 w-9">
          <button
            onClick={onToggle}
            title={expanded ? 'Bezárás' : 'Megnyitás'}
            className={clsx(
              'w-6 h-6 rounded-md flex items-center justify-center transition-all duration-150',
              expanded
                ? 'bg-orange-500/20 text-orange-400'
                : isLight
                  ? 'text-slate-400 hover:text-slate-700 hover:bg-slate-100'
                  : 'text-zinc-400 hover:text-white hover:bg-white/10'
            )}
            style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}
          >
            <svg viewBox="0 0 12 12" fill="currentColor" className="w-3.5 h-3.5">
              <path d="M4 2.5L8.5 6 4 9.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </td>

        <td className="px-3 py-2.5 max-w-[200px]">
          <div className="flex items-center gap-1.5 flex-wrap">
            {e.urgent && <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />}
            <span className={clsx('font-medium truncate', isLight ? 'text-slate-800' : '')}>{e.subject || '(nincs tárgy)'}</span>
            {aiD.learned_override && (
              <span className="text-[9px] font-bold font-mono px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-400/25 flex-shrink-0">🧠</span>
            )}
            <SentimentBadge sentiment={aiD.sentiment} />
            {['NEW','NEEDS_ATTENTION'].includes(e.status) && (
              <SlaBadge createdAt={e.created_at} warningH={slaConfig.warning_hours} breachH={slaConfig.breach_hours} />
            )}
          </div>
        </td>
        <td className="px-3 py-2.5 max-w-[150px]">
          <span className={clsx('text-[11px] font-mono truncate block', isLight ? 'text-slate-500' : 'text-zinc-500')}>{e.sender || '—'}</span>
        </td>
        <td className="px-3 py-2.5">
          <span className={clsx('text-[11px] font-mono', catColor)}>{e.category || '—'}</span>
        </td>
        <td className="px-3 py-2.5" style={{minWidth:'160px'}}>{statusBadge}</td>
        <td className="px-3 py-2.5"><ConfBar value={e.confidence} /></td>
        <td className="px-3 py-2.5">
          <span className={clsx('text-[11px] font-mono whitespace-nowrap', isLight ? 'text-slate-500' : 'text-zinc-500')}>{dt}</span>
        </td>

        {/* Status select + delete */}
        <td className="px-3 py-2.5">
          <div className="flex items-center gap-2">
            <select
              defaultValue={e.status}
              onChange={ev => onStatusChange(e, ev.target.value, ev.target)}
              className={clsx(
                'text-[11px] font-mono border rounded px-2 py-1.5 outline-none min-w-[140px] transition-colors hover:border-orange-400/50 focus:border-orange-400',
                isLight ? 'bg-white border-slate-300 text-slate-700' : 'bg-white/5 border-white/13 text-zinc-300'
              )}
            >
              {['NEW','AI_ANSWERED','NEEDS_ATTENTION','CLOSED'].map(s => (
                <option key={s} value={s} className={isLight ? 'bg-white text-slate-800' : 'bg-[#0d0d24]'}>{s}</option>
              ))}
            </select>

            {/* Delete — proper trash icon, clearly separated */}
            <button
              onClick={() => onDelete(e.id)}
              title="Email törlése"
              className={clsx(
                'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all border',
                isLight
                  ? 'border-slate-200 text-slate-400 hover:border-red-300 hover:text-red-500 hover:bg-red-50'
                  : 'border-white/15 text-zinc-500 hover:border-red-400/60 hover:text-red-400 hover:bg-red-500/10'
              )}
            >
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-3.5 h-3.5">
                <path d="M2 4h10" strokeLinecap="round"/>
                <path d="M5 4V2.5h4V4" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M5.5 6.5v4M8.5 6.5v4" strokeLinecap="round"/>
                <path d="M3 4l.7 7.5h6.6L11 4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </td>
      </tr>

      {expanded && (
        <tr className={clsx('border-b', isLight ? 'border-slate-100' : 'border-white/5')}>
          <td colSpan={9} className={clsx('px-4 py-3 border-t', isLight ? 'bg-orange-50 border-orange-200' : 'bg-orange-500/[.04] border-orange-400/15')}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div className={clsx('text-[9.5px] font-mono uppercase tracking-[.08em] mb-1', isLight ? 'text-slate-400' : 'text-zinc-500')}>Feladó</div>
                <div className={clsx('text-[13px]', isLight ? 'text-slate-700' : 'text-zinc-300')}>{e.sender || '—'}</div>
                <div className={clsx('text-[9.5px] font-mono uppercase tracking-[.08em] mt-3 mb-1', isLight ? 'text-slate-400' : 'text-zinc-500')}>AI döntés</div>
                <pre className={clsx('text-[11px] font-mono rounded p-2 overflow-auto max-h-24', isLight ? 'bg-slate-100 text-slate-600 border border-slate-200' : 'bg-white/3 text-zinc-400')}>{JSON.stringify(aiD, null, 2)}</pre>
              </div>
              <div>
                <div className={clsx('text-[9.5px] font-mono uppercase tracking-[.08em] mb-1', isLight ? 'text-slate-400' : 'text-zinc-500')}>Email törzse</div>
                <div className={clsx('rounded-lg p-3 text-[12px] leading-relaxed min-h-[60px] max-h-[150px] overflow-auto whitespace-pre-wrap', isLight ? 'bg-white border border-slate-200 text-slate-600' : 'bg-white/3 border border-white/10 text-zinc-400')}>
                  {e.body || <span className={isLight ? 'text-slate-400' : 'text-zinc-600'}>Nincs tartalom</span>}
                </div>
              </div>
              <div>
                <div className={clsx('text-[9.5px] font-mono uppercase tracking-[.08em] mb-1 flex items-center gap-1.5', isLight ? 'text-slate-400' : 'text-zinc-500')}>
                  AI válasz
                  {e.status === 'AI_ANSWERED' && !e.ai_response && (
                    <span className="text-[9px] text-amber-400 font-mono">(generálás folyamatban…)</span>
                  )}
                </div>
                <div className={clsx(
                  'rounded-lg p-3 text-[13px] leading-relaxed min-h-[60px] max-h-[150px] overflow-auto whitespace-pre-wrap',
                  isLight
                    ? (e.ai_response ? 'bg-white border border-green-300 text-slate-700' : 'bg-white border border-slate-200 text-slate-400')
                    : (e.ai_response ? 'bg-white/3 border border-green-400/20 text-zinc-300' : 'bg-white/3 border border-orange-400/15 text-zinc-600')
                )}>
                  {e.ai_response || 'Nincs AI válasz'}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function ConfirmModal({ title, message, onConfirm, onCancel, theme }) {
  const isLight = theme === 'light'

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onCancel])

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backdropFilter: 'blur(4px)', backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={e => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div className={clsx(
        'w-full max-w-sm rounded-2xl shadow-2xl border overflow-hidden',
        'animate-fade-up',
        isLight
          ? 'bg-white border-slate-200'
          : 'bg-[#0d1529] border-white/10'
      )}>
        {/* Header */}
        <div className={clsx(
          'flex items-center gap-3 px-5 py-4 border-b',
          isLight ? 'border-slate-100' : 'border-white/7'
        )}>
          <div className="w-8 h-8 rounded-full bg-red-500/15 border border-red-400/25 flex items-center justify-center flex-shrink-0">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-4 h-4 text-red-400">
              <path d="M3 5h10M6 5V3.5h4V5M6.5 7.5v4M9.5 7.5v4M3.5 5l.8 8h7.4l.8-8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <div className={clsx('text-[14px] font-semibold', isLight ? 'text-slate-800' : 'text-white')}>{title}</div>
          </div>
          <button
            onClick={onCancel}
            className={clsx('ml-auto w-6 h-6 rounded-md flex items-center justify-center transition-colors text-[14px]', isLight ? 'text-slate-400 hover:text-slate-600 hover:bg-slate-100' : 'text-zinc-500 hover:text-white hover:bg-white/10')}
          >✕</button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          <p className={clsx('text-[13px] leading-relaxed', isLight ? 'text-slate-600' : 'text-zinc-400')}>
            {message}
          </p>
        </div>

        {/* Footer */}
        <div className={clsx('flex items-center justify-end gap-2 px-5 py-3 border-t', isLight ? 'border-slate-100 bg-slate-50' : 'border-white/7 bg-white/[.02]')}>
          <button
            onClick={onCancel}
            className={clsx(
              'text-[12px] font-mono px-4 py-2 rounded-lg border transition-colors',
              isLight
                ? 'border-slate-200 text-slate-600 hover:bg-slate-100'
                : 'border-white/13 text-zinc-400 hover:bg-white/5 hover:text-white'
            )}
          >
            Mégse
          </button>
          <button
            onClick={onConfirm}
            className="text-[12px] font-mono px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white transition-colors font-medium"
          >
            Törlés
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

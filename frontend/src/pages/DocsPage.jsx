import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { Skeleton } from '../components/ui'
import clsx from 'clsx'

export default function DocsPage() {
  const [docs, setDocs]       = useState(null)
  const [vectors, setVectors] = useState(0)
  const [dragging, setDragging] = useState(false)

  const loadDocs = () => {
    api.dashboard().then(d => {
      setDocs(d.documents || [])
      setVectors(d.meta?.qdrant_vectors || 0)
    }).catch(() => setDocs([]))
  }

  useEffect(() => {
    loadDocs()
    window.addEventListener('docuagent:uploaded', loadDocs)
    return () => window.removeEventListener('docuagent:uploaded', loadDocs)
  }, [])

  function triggerUpload() {
    document.getElementById('fileIn')?.click()
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const files = e.dataTransfer?.files
    if (!files?.length) return
    // Simulate file input change event with the dropped files
    const input = document.getElementById('fileIn')
    if (!input) return
    // Create a new DataTransfer and set files
    const dt = new DataTransfer()
    Array.from(files).forEach(f => dt.items.add(f))
    input.files = dt.files
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }

  const extColors = {
    docx: { bg: 'bg-blue-500/10',  text: 'text-blue-400' },
    pdf:  { bg: 'bg-red-500/10',   text: 'text-red-400' },
    xlsx: { bg: 'bg-green-500/10', text: 'text-green-400' },
    txt:  { bg: 'bg-zinc-500/10',  text: 'text-zinc-400' },
    csv:  { bg: 'bg-yellow-500/10',text: 'text-yellow-400' },
    md:   { bg: 'bg-purple-500/10',text: 'text-purple-400' },
  }

  return (
    <div className="animate-fade-up">
      <p className="text-[11.5px] text-zinc-500 font-mono mb-3">
        {docs ? `${docs.length} dokumentum · Qdrant: ${vectors} vektor indexelve` : 'Betöltés...'}
      </p>

      {/* ── Drop zone ── */}
      <div
        onClick={triggerUpload}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{
          border: `2px dashed ${dragging ? 'rgba(251,146,60,0.7)' : 'rgba(255,255,255,0.12)'}`,
          borderRadius: 12,
          padding: '28px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          marginBottom: 20,
          background: dragging ? 'rgba(251,146,60,0.05)' : 'rgba(255,255,255,0.02)',
          transition: 'border-color .2s, background .2s',
        }}
      >
        <div style={{ fontSize: 26, marginBottom: 6 }}>📂</div>
        <div style={{ fontSize: 13, fontWeight: 500, color: '#e4e4e7', marginBottom: 3 }}>
          Húzd ide a fájlokat, vagy kattints a tallózáshoz
        </div>
        <div style={{ fontSize: 11, color: '#52525b' }}>
          PDF, DOCX, XLSX, TXT, CSV, MD · max 20MB/fájl · egyszerre több fájl is
        </div>
      </div>

      {/* ── Doc grid ── */}
      {docs === null ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[1,2,3].map(i => (
            <div key={i} className="glass-card">
              <Skeleton className="h-4 mb-2" /><Skeleton className="h-3 w-2/3" />
            </div>
          ))}
        </div>
      ) : docs.length === 0 ? (
        <div className="glass-card text-center py-12">
          <div className="text-3xl mb-3">📄</div>
          <div className="text-zinc-500 text-sm">Még nincs feltöltött dokumentum</div>
          <div className="text-zinc-600 text-xs mt-1">Húzz ide fájlokat vagy kattints a területre fent</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {docs.map(d => {
            const c = extColors[d.ext] || { bg: 'bg-white/5', text: 'text-zinc-500' }
            return (
              <div key={d.id} className="glass-card hover:border-white/13 cursor-pointer group transition-all">
                <span className={clsx('text-[9px] font-bold font-mono px-2 py-0.5 rounded inline-block mb-2', c.bg, c.text)}>
                  {(d.ext || '?').toUpperCase()}
                </span>
                <div className="text-[13.5px] font-medium text-white truncate group-hover:text-orange-400 transition-colors">{d.filename}</div>
                <div className="text-[11px] text-zinc-500 font-mono mt-1">{d.uploader} · {d.size_kb}KB · {d.lang} · {d.date}</div>
                <div className="mt-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400">{d.tag}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

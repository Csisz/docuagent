import { useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar  from './Topbar'
import { useDashboard, useHealth } from '../../hooks'
import { api } from '../../services/api'
import { useToast } from '../../hooks'
import { useStore } from '../../store'

export default function Layout() {
  const fileRef  = useRef()
  const toast    = useToast()
  const { reload } = useDashboard()
  const { theme } = useStore()
  const [uploadQueue, setUploadQueue] = useState([])
  useHealth()

  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme)
  }

  async function handleUpload(e) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    e.target.value = ''

    const queue = files.map(f => ({
      name: f.name,
      size: Math.round(f.size / 1024),
      state: 'waiting',
      info: '',
    }))
    setUploadQueue(queue)

    let doneCount = 0, errCount = 0

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      setUploadQueue(q => q.map((item, idx) =>
        idx === i ? { ...item, state: 'uploading', info: 'Feltöltés...' } : item
      ))

      const fd = new FormData()
      fd.append('file', file)
      fd.append('uploader_name', 'Viktor H.')
      fd.append('tag', 'general')

      try {
        const d = await api.upload(fd)
        setUploadQueue(q => q.map((item, idx) =>
          idx === i ? { ...item, state: 'processing', info: 'Qdrant indexelés...' } : item
        ))
        await new Promise(res => setTimeout(res, 400))
        setUploadQueue(q => q.map((item, idx) =>
          idx === i ? { ...item, state: 'done', info: `${d.size_kb}KB · ${d.lang} · Qdrant: ${d.qdrant ? '✓' : '—'}` } : item
        ))
        doneCount++
      } catch (err) {
        setUploadQueue(q => q.map((item, idx) =>
          idx === i ? { ...item, state: 'error', info: err.message.slice(0, 40) } : item
        ))
        errCount++
      }
    }

    if (doneCount > 0) {
      toast(`✅ ${doneCount} dokumentum feltöltve`, 'ok')
      await reload()
      window.dispatchEvent(new CustomEvent('docuagent:uploaded'))
    }
    if (errCount > 0) toast(`⚠️ ${errCount} fájl feltöltése sikertelen`, 'err')
    if (errCount === 0) setTimeout(() => setUploadQueue([]), 5000)
  }

  const stateIcon  = { waiting: '⏳', uploading: '🔄', processing: '⚙️', done: '✅', error: '❌' }
  const stateColor = { waiting: '#71717a', uploading: '#60a5fa', processing: '#60a5fa', done: '#4ade80', error: '#f87171' }
  const barWidth   = { waiting: '0%', uploading: '55%', processing: '85%', done: '100%', error: '100%' }
  const barBg      = { waiting: '#3f3f46', uploading: '#3b82f6', processing: '#3b82f6', done: '#22c55e', error: '#ef4444' }

  return (
    <div className="flex min-h-screen bg-cinematic bg-dots">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        <Topbar onUpload={() => fileRef.current?.click()} />
        <input
          ref={fileRef} id="fileIn" type="file" className="hidden" multiple
          accept=".pdf,.docx,.xlsx,.txt,.csv,.md"
          onChange={handleUpload}
        />

        {uploadQueue.length > 0 && (
          <div style={{
            margin: '0 24px 8px', background: 'rgba(15,15,40,0.96)',
            border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10,
            padding: '12px 16px', backdropFilter: 'blur(12px)',
          }}>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginBottom: 8, fontFamily: 'monospace' }}>
              FELTÖLTÉSI SOR · {uploadQueue.filter(q => q.state === 'done').length}/{uploadQueue.length} kész
            </div>
            {uploadQueue.map((item, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0',
                borderTop: i > 0 ? '1px solid rgba(255,255,255,0.06)' : 'none',
              }}>
                <span style={{ fontSize: 15, width: 20, textAlign: 'center' }}>{stateIcon[item.state]}</span>
                <span style={{ flex: '0 0 180px', fontSize: 13, color: '#e4e4e7', fontWeight: 500,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                  title={item.name}>{item.name}</span>
                <span style={{ fontSize: 11, color: '#52525b', minWidth: 36 }}>{item.size}KB</span>
                <div style={{ flex: 1, height: 5, background: 'rgba(255,255,255,0.07)', borderRadius: 3, overflow: 'hidden', minWidth: 60 }}>
                  <div style={{
                    height: '100%', borderRadius: 3, background: barBg[item.state],
                    width: barWidth[item.state], transition: 'width 0.4s ease',
                  }} />
                </div>
                <span style={{ fontSize: 11, color: stateColor[item.state], minWidth: 130, textAlign: 'right' }}>
                  {item.info || item.state}
                </span>
              </div>
            ))}
          </div>
        )}

        <main className="flex-1 overflow-y-auto px-4 md:px-6 py-5 pb-16">
          <Outlet />
        </main>
      </div>
      <div id="toast-root" />
    </div>
  )
}

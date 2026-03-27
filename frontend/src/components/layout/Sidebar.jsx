import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { useStore } from '../../store'
import { getApiKey, setApiKey } from '../../services/api'

const NAV = [
  {
    section: 'Főmenü',
    items: [
      { to: '/',          label: 'Dashboard',        icon: GridIcon },
    ]
  },
  {
    section: 'Emailek',
    items: [
      { to: '/emails',    label: 'Összes email',     icon: MailIcon,    badge: 'nb-total' },
      { to: '/attention', label: 'Figyelmet igényel', icon: AlertIcon,  badge: 'nb-att' },
    ]
  },
  {
    section: 'Tartalom',
    items: [
      { to: '/docs',      label: 'Dokumentumok',     icon: DocIcon },
    ]
  },
  {
    section: 'Analitika',
    items: [
      { to: '/insights',  label: 'AI Insights',      icon: ChartIcon },
    ]
  },
]

export default function Sidebar() {
  const { mobileNavOpen, closeMobileNav, theme, toggleTheme, dashData } = useStore()
  const [showApiModal, setShowApiModal] = useState(false)
  const [apiKeyInput, setApiKeyInput]   = useState('')
  const apiKeySet = !!getApiKey()

  function openApiModal() {
    setApiKeyInput(getApiKey())
    setShowApiModal(true)
  }

  function saveApiKey() {
    setApiKey(apiKeyInput.trim())
    setShowApiModal(false)
    window.location.reload()
  }
  const company = dashData?.meta?.company || 'Agentify Kft.'
  const attCount = dashData?.status_breakdown?.NEEDS_ATTENTION || 0
  const totalCount = dashData?.kpis?.emails?.value || 0

  const badges = { 'nb-total': totalCount, 'nb-att': attCount }

  return (
    <>
      {/* Mobile overlay */}
      {mobileNavOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-20 lg:hidden"
          onClick={closeMobileNav}
        />
      )}

      {/* Sidebar */}
      <aside className={clsx(
        'fixed inset-y-0 left-0 z-30 w-[236px] flex flex-col',
        theme === 'light' ? 'bg-[#1e293b] border-r border-slate-700' : 'bg-[#050d18] border-r border-white/7',
        'transition-transform duration-300 ease-in-out',
        // Mobile: slide in/out
        mobileNavOpen ? 'translate-x-0' : '-translate-x-full',
        // Desktop: always visible
        'lg:static lg:translate-x-0 lg:z-auto'
      )}>

        {/* Logo / Brand */}
        <div className="flex items-center gap-3 px-[18px] py-5 border-b border-white/7">
          <div className="w-8 h-8 rounded-lg bg-[#1a56db] flex items-center justify-center flex-shrink-0 shadow-glow">
            <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4">
              <path d="M3 8h5M9 4l4 4-4 4" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="4.5" cy="8" r="1.5" fill="white"/>
            </svg>
          </div>
          <div>
            <div className="text-[14px] font-bold text-white">DocuAgent</div>
            <div className="text-[9px] text-white/50 font-mono mt-0.5">v3.1 · Enterprise</div>
          </div>
          {/* Mobile close */}
          <button
            className="ml-auto lg:hidden text-white/40 hover:text-white text-xl"
            onClick={closeMobileNav}
          >✕</button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {NAV.map(({ section, items }) => (
            <div key={section}>
              <div className="text-[8.5px] text-white/50 uppercase tracking-[.18em] font-mono px-3 py-3 pb-1">
                {section}
              </div>
              {items.map(({ to, label, icon: Icon, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={closeMobileNav}
                  className={({ isActive }) => clsx(
                    'flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13.5px] font-normal',
                    'transition-all duration-150 mb-0.5',
                    isActive
                      ? 'bg-[#1a56db] text-white font-medium shadow-[0_2px_8px_rgba(26,86,219,.35)]'
                      : 'text-white/70 hover:bg-white/8 hover:text-white'
                  )}
                >
                  <Icon className="w-[14px] h-[14px] flex-shrink-0 opacity-80" />
                  <span className="flex-1">{label}</span>
                  {badge && badges[badge] > 0 && (
                    <span className="ml-auto bg-red-500 text-white text-[9.5px] font-mono px-1.5 py-0.5 rounded-full leading-none">
                      {badges[badge]}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* API Key */}
        <div className="px-4 py-1.5 border-t border-white/7">
          <button
            onClick={openApiModal}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors duration-150 group"
          >
            <span className="text-[13px] w-4 text-center leading-none">🔑</span>
            <span className="text-[12px] font-mono flex-1 text-left transition-colors" style={{color: apiKeySet ? '#4ade80' : 'rgba(255,255,255,0.35)'}}>
              {apiKeySet ? 'Kulcs beállítva ✓' : 'API kulcs (nincs)'}
            </span>
          </button>
        </div>

        {/* Theme toggle */}
        <div className="px-4 py-2.5 border-t border-white/7">
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors duration-150 group"
          >
            <span className="text-[13px] w-4 text-center leading-none">
              {theme === 'dark' ? '🌙' : '☀️'}
            </span>
            <span className="text-[12px] text-white/50 font-mono flex-1 text-left group-hover:text-white/70 transition-colors">
              {theme === 'dark' ? 'Dark' : 'Light'}
            </span>
            <div
              onClick={e => { e.stopPropagation(); toggleTheme() }}
              className={clsx(
                'w-9 h-5 rounded-full relative transition-colors duration-200 flex-shrink-0 cursor-pointer',
                theme === 'dark' ? 'bg-[#1a56db]' : 'bg-white/25'
              )}
            >
              <span className={clsx(
                'absolute top-[3px] w-3.5 h-3.5 rounded-full bg-white transition-all duration-200 shadow-sm',
                theme === 'dark' ? 'left-[19px]' : 'left-[3px]'
              )} />
            </div>
          </button>
        </div>

        {/* User */}
        <div className="px-2 py-2 border-t border-white/7">
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer hover:bg-white/5 transition-colors">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#1a56db] to-[#7c3aed] flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0">
              VH
            </div>
            <div>
              <div className="text-[12.5px] text-white/80 font-medium leading-none mb-0.5">{company}</div>
              <div className="text-[9.5px] text-white/30 font-mono">Admin</div>
            </div>
          </div>
        </div>

      </aside>
      {/* API Key Modal */}
      {showApiModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)'}}
          onClick={() => setShowApiModal(false)}
        >
          <div
            className="w-[400px] max-w-[90vw] rounded-xl p-6"
            style={{background: '#0f172a', border: '1px solid rgba(255,255,255,0.12)'}}
            onClick={e => e.stopPropagation()}
          >
            <div className="text-[15px] font-semibold text-white mb-1">API kulcs beállítása</div>
            <div className="text-[12px] text-white/40 mb-4 font-mono">
              Ha a backend DASHBOARD_API_KEY-vel fut, add meg itt.<br/>
              Üresen hagyva az auth ki van kapcsolva.
            </div>
            <input
              type="password"
              placeholder="pl. a3f9c2..."
              value={apiKeyInput}
              onChange={e => setApiKeyInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && saveApiKey()}
              autoFocus
              className="w-full rounded-lg px-3 py-2.5 text-[13px] font-mono mb-4 outline-none"
              style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: '#e2e8f0',
              }}
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowApiModal(false)}
                className="px-4 py-2 rounded-lg text-[13px] text-white/50 hover:text-white/80 transition-colors"
                style={{border: '1px solid rgba(255,255,255,0.1)'}}
              >
                Mégse
              </button>
              <button
                onClick={saveApiKey}
                className="px-4 py-2 rounded-lg text-[13px] font-medium text-white transition-colors"
                style={{background: '#1a56db'}}
              >
                Mentés
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// SVG Icons
function GridIcon({ className }) {
  return <svg className={className} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="1" y="1" width="5" height="5" rx="1"/><rect x="8" y="1" width="5" height="5" rx="1"/><rect x="1" y="8" width="5" height="5" rx="1"/><rect x="8" y="8" width="5" height="5" rx="1"/></svg>
}
function MailIcon({ className }) {
  return <svg className={className} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="1" y="2" width="12" height="10" rx="1.2"/><path d="M1 5h12M5 2v3"/></svg>
}
function AlertIcon({ className }) {
  return <svg className={className} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="7" cy="7" r="5.5"/><path d="M7 4.5v3M7 9.5v.5"/></svg>
}
function DocIcon({ className }) {
  return <svg className={className} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M3 2h6l3 3v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"/><path d="M9 2v3h3"/></svg>
}
function ChartIcon({ className }) {
  return <svg className={className} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4"><path d="M2 10l3-4 2.5 2.5 2.5-4.5 2 2"/><path d="M1 13h12"/></svg>
}

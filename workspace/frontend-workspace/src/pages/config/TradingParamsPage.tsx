/**
 * TradingParamsPage — Group A settings
 * Signal scoring, regime detection, timeframes, strategy thresholds.
 * Versioned — every save creates a new version in DB.
 */
import { useEffect, useState } from 'react'
import type { TradingParams, ParamsVersionHistory } from '../../types/config'

export function TradingParamsPage() {
  const [params, setParams] = useState<TradingParams | null>(null)
  const [history, setHistory] = useState<ParamsVersionHistory[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [versionTag, setVersionTag] = useState(() => {
    // Auto-generate a default version tag based on current date
    const now = new Date()
    return `v${now.getFullYear()}.${String(now.getMonth()+1).padStart(2,'0')}.${String(now.getDate()).padStart(2,'0')}`
  })
  const [versionNote, setVersionNote] = useState('')
  const [showHistory, setShowHistory] = useState(false)

  useEffect(() => {
    Promise.all([
      fetch('/api/config/trading').then(r => r.json()),
      fetch('/api/config/trading/history').then(r => r.json()),
    ]).then(([p, h]) => {
      setParams(p)
      setHistory(Array.isArray(h) ? h : [])
      setLoading(false)
    })
  }, [])

  async function handleSave() {
    if (!params || !versionTag.trim()) {
      setSaveMsg('✗ Version tag is required (e.g. "v1.1-aggressive")')
      return
    }
    setSaving(true)
    setSaveMsg(null)
    try {
      const res = await fetch('/api/config/trading', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...params, version_tag: versionTag, version_note: versionNote }),
      })
      const data = await res.json()
      if (res.ok) {
        setSaveMsg(`✓ Saved as ${data.version_tag}`)
        setVersionTag('')
        setVersionNote('')
        // Refresh history
        fetch('/api/config/trading/history').then(r => r.json()).then(h => setHistory(h))
      } else {
        setSaveMsg(`✗ ${data.detail}`)
      }
    } catch {
      setSaveMsg('✗ Network error')
    } finally {
      setSaving(false)
    }
  }

  async function handleActivateVersion(id: string, tag: string) {
    const res = await fetch(`/api/config/trading/${id}/activate`, { method: 'POST' })
    if (res.ok) {
      setSaveMsg(`✓ Rolled back to ${tag}`)
      fetch('/api/config/trading').then(r => r.json()).then(setParams)
      fetch('/api/config/trading/history').then(r => r.json()).then(setHistory)
    }
  }

  if (loading || !params) {
    return <div className="text-center py-12 text-gray-500">Loading trading parameters...</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Trading Parameters</h1>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          {showHistory ? 'Hide' : 'Show'} Version History ({history.length})
        </button>
      </div>

      {/* Version History */}
      {showHistory && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-3">Version History</h2>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {history.map(v => (
              <div key={v.id} className={`flex items-center gap-3 px-3 py-2 rounded-lg ${v.is_active ? 'bg-green-900/20 border border-green-800' : 'bg-gray-800'}`}>
                <div className="flex-1">
                  <span className="text-sm font-mono text-white">{v.version_tag}</span>
                  {v.version_note && <span className="text-xs text-gray-500 ml-2">{v.version_note}</span>}
                  <div className="text-xs text-gray-600">{new Date(v.created_at).toLocaleString()}</div>
                </div>
                {v.is_active ? (
                  <span className="text-xs text-green-400 bg-green-900/30 px-2 py-0.5 rounded">ACTIVE</span>
                ) : (
                  <button
                    onClick={() => handleActivateVersion(v.id, v.version_tag)}
                    className="text-xs text-gray-400 hover:text-white bg-gray-700 hover:bg-gray-600 px-2 py-0.5 rounded transition-colors"
                  >
                    Activate
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {saveMsg && (
        <div className={`text-sm px-3 py-2 rounded-lg ${saveMsg.startsWith('✓') ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
          {saveMsg}
        </div>
      )}

      {/* Signal Scoring */}
      <Section title="Signal Scoring Thresholds">
        <div className="grid grid-cols-2 gap-4">
          <NumField label="ALERT threshold (≥ this = ALERT)" value={params.score_alert_threshold}
            onChange={v => setParams({ ...params, score_alert_threshold: v })} min={50} max={100} />
          <NumField label="WATCH threshold (≥ this = WATCH)" value={params.score_watch_threshold}
            onChange={v => setParams({ ...params, score_watch_threshold: v })} min={30} max={90} />
        </div>
        <p className="text-xs text-gray-600 mt-1">
          Score formula: final = min(round(raw × regime_multiplier / 125 × 100), 100)
        </p>
      </Section>

      {/* Regime Detection */}
      <Section title="Regime Detection">
        <div className="grid grid-cols-2 gap-4">
          <NumField label="ADX Trending threshold (> = TRENDING)" value={params.adx_trending_threshold}
            onChange={v => setParams({ ...params, adx_trending_threshold: v })} step={0.5} />
          <NumField label="ADX Choppy threshold (< = CHOPPY)" value={params.adx_choppy_threshold}
            onChange={v => setParams({ ...params, adx_choppy_threshold: v })} step={0.5} />
          <NumField label="ATR Parabolic multiplier (× rolling avg)" value={params.atr_parabolic_multiplier}
            onChange={v => setParams({ ...params, atr_parabolic_multiplier: v })} step={0.1} min={1.5} />
          <NumField label="PARABOLIC score multiplier" value={params.parabolic_score_multiplier}
            onChange={v => setParams({ ...params, parabolic_score_multiplier: v })} step={0.05} min={0.1} max={1} />
        </div>
      </Section>

      {/* Timeframes */}
      <Section title="Timeframes">
        <div className="grid grid-cols-3 gap-4">
          <TFField label="Trigger (signal detection)" value={params.trigger_timeframe}
            onChange={v => setParams({ ...params, trigger_timeframe: v })} />
          <TFField label="Context (HTF bias)" value={params.context_timeframe}
            onChange={v => setParams({ ...params, context_timeframe: v })} />
          <NumField label="Signal expiry (candles)" value={params.time_invalidation_candles}
            onChange={v => setParams({ ...params, time_invalidation_candles: v })} min={5} max={50} />
        </div>
      </Section>

      {/* Strategy Thresholds */}
      <Section title="Strategy Thresholds">
        <div className="grid grid-cols-2 gap-4">
          <NumField label="OB impulse ATR multiplier" value={params.ob_atr_multiplier}
            onChange={v => setParams({ ...params, ob_atr_multiplier: v })} step={0.1} min={1} />
          <NumField label="Pinbar tail:body ratio" value={params.pinbar_tail_ratio}
            onChange={v => setParams({ ...params, pinbar_tail_ratio: v })} step={0.1} min={1.5} />
          <NumField label="TP1 R:R ratio" value={params.tp1_rr_ratio}
            onChange={v => setParams({ ...params, tp1_rr_ratio: v })} step={0.1} min={1} />
          <NumField label="TP2 R:R ratio" value={params.tp2_rr_ratio}
            onChange={v => setParams({ ...params, tp2_rr_ratio: v })} step={0.1} min={1} />
        </div>
      </Section>

      {/* Risk */}
      <Section title="Risk Management">
        <div className="grid grid-cols-2 gap-4">
          <NumField label="Correlation threshold (> = same group)" value={params.correlation_threshold}
            onChange={v => setParams({ ...params, correlation_threshold: v })} step={0.05} min={0.5} max={1} />
          <NumField label="Max correlated group risk (%)" value={params.max_correlated_risk_pct}
            onChange={v => setParams({ ...params, max_correlated_risk_pct: v })} step={0.5} min={1} />
          <NumField label="Portfolio heat limit (%)" value={params.portfolio_heat_limit_pct}
            onChange={v => setParams({ ...params, portfolio_heat_limit_pct: v })} step={0.5} min={2} />
          <NumField label="Max concurrent positions" value={params.max_concurrent_positions}
            onChange={v => setParams({ ...params, max_concurrent_positions: v })} min={1} max={10} />
          <NumField label="Max daily loss (%)" value={params.max_daily_loss_pct}
            onChange={v => setParams({ ...params, max_daily_loss_pct: v })} step={0.5} min={1} />
        </div>
      </Section>

      {/* Save with version */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">Save New Version</h2>
        <p className="text-xs text-gray-500">
          Fill in a version tag below, then click Save. Each save creates a new versioned snapshot — you can rollback anytime.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Version Tag <span className="text-red-400">*</span>
              <span className="text-gray-600 ml-1">(required to enable Save)</span>
            </label>
            <input
              type="text"
              value={versionTag}
              onChange={e => setVersionTag(e.target.value)}
              placeholder="e.g. v1.1-aggressive"
              className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Version Note (optional)</label>
            <input
              type="text"
              value={versionNote}
              onChange={e => setVersionNote(e.target.value)}
              placeholder="Why this change?"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
            />
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !versionTag.trim()}
          className="w-full py-2.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-lg transition-colors"
        >
          {saving ? 'Saving...' : versionTag.trim() ? `Save & Activate "${versionTag}"` : 'Enter a version tag above to save'}
        </button>
        <p className="text-xs text-gray-600">
          Previous version is kept in history. You can rollback anytime from the Version History panel above.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shared UI helpers
// ---------------------------------------------------------------------------

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d']
const inputClass = "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-gray-500"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">{title}</h2>
      {children}
    </div>
  )
}

function NumField({ label, value, onChange, min, max, step = 1 }: {
  label: string; value: number; onChange: (v: number) => void
  min?: number; max?: number; step?: number
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input
        type="number"
        value={value}
        onChange={e => onChange(+e.target.value)}
        min={min} max={max} step={step}
        className={inputClass}
      />
    </div>
  )
}

function TFField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)} className={inputClass}>
        {TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}</option>)}
      </select>
    </div>
  )
}

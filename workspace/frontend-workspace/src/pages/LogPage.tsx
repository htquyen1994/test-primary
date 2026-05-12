/**
 * LogPage — Real-time System Log
 * Shows every candle scoring cycle with full breakdown:
 * - Regime state (ADX, ATR)
 * - Per-module scores (Order Flow, SMC, VSA, Context)
 * - Why conditions were met or missed
 * - Why signal didn't reach ALERT threshold
 *
 * Uses /ws/logs WebSocket — separate from alerts pipeline.
 * Performance: zero impact on scoring — logs are fire-and-forget.
 */
import { useEffect, useRef, useState } from 'react'

interface ScoreBreakdown {
  order_flow: number
  smc: number
  vsa: number
  context: number
  bonus: number
  raw: number
  final: number
}

interface LogEntry {
  type: string
  timestamp: string
  symbol: string
  timeframe: string
  candle_timestamp: string
  regime: string
  regime_multiplier: number
  adx: number
  atr: number
  scores: ScoreBreakdown
  classification: 'ALERT' | 'WATCH' | 'IGNORE'
  conditions_met: string[]
  conditions_missed: string[]
  why_not_alert: string
  delta: number
  funding_rate: number
  portfolio_heat: number
  htf_bias: string
}

const REGIME_COLORS: Record<string, string> = {
  TRENDING: 'text-green-400',
  RANGING: 'text-yellow-400',
  PARABOLIC: 'text-red-400',
  CHOPPY: 'text-gray-400',
}

const CLASS_COLORS: Record<string, string> = {
  ALERT: 'bg-green-900/50 text-green-400 border-green-800',
  WATCH: 'bg-yellow-900/50 text-yellow-400 border-yellow-800',
  IGNORE: 'bg-gray-800/50 text-gray-500 border-gray-700',
}

const MAX_LOGS = 100

export function LogPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const [filter, setFilter] = useState<'ALL' | 'ALERT' | 'WATCH' | 'IGNORE'>('ALL')
  const [symbolFilter, setSymbolFilter] = useState('')
  const [paused, setPaused] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [triggerTf, setTriggerTf] = useState('15m')  // loaded from config
  const wsRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const pausedRef = useRef(false)

  pausedRef.current = paused

  // Load trigger timeframe from config
  useEffect(() => {
    fetch('/api/config/trading')
      .then(r => r.json())
      .then(data => {
        if (data?.trigger_timeframe) setTriggerTf(data.trigger_timeframe)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/logs`
    let backoff = 1000

    function connect() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        backoff = 1000
      }

      ws.onmessage = (event) => {
        if (pausedRef.current) return
        try {
          const entry: LogEntry = JSON.parse(event.data)
          if (entry.type !== 'scoring_log') return
          setLogs(prev => {
            const next = [entry, ...prev]
            return next.slice(0, MAX_LOGS)
          })
        } catch {
          // ignore malformed
        }
      }

      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, backoff)
        backoff = Math.min(backoff * 2, 30000)
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => wsRef.current?.close()
  }, [])

  const filtered = logs.filter(log => {
    if (filter !== 'ALL' && log.classification !== filter) return false
    if (symbolFilter && !log.symbol.toLowerCase().includes(symbolFilter.toLowerCase())) return false
    return true
  })

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-white">System Log</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${connected ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
            {connected ? '● Live' : '○ Disconnected'}
          </span>
          <span className="text-xs text-gray-500">{filtered.length} entries</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Symbol filter */}
          <input
            type="text"
            value={symbolFilter}
            onChange={e => setSymbolFilter(e.target.value)}
            placeholder="Filter symbol..."
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1 text-sm text-white placeholder-gray-500 w-36 focus:outline-none"
          />

          {/* Classification filter */}
          {(['ALL', 'ALERT', 'WATCH', 'IGNORE'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                filter === f
                  ? 'bg-blue-700 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {f}
            </button>
          ))}

          {/* Pause */}
          <button
            onClick={() => setPaused(p => !p)}
            className={`px-3 py-1 text-xs rounded-lg transition-colors ${
              paused ? 'bg-yellow-700 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {paused ? '▶ Resume' : '⏸ Pause'}
          </button>

          {/* Clear */}
          <button
            onClick={() => setLogs([])}
            className="px-3 py-1 text-xs rounded-lg bg-gray-800 text-gray-400 hover:bg-gray-700 transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Log entries */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-3xl mb-3">📋</p>
          <p>Waiting for scoring cycles...</p>
          <p className="text-xs mt-1 text-gray-600">
            Trigger timeframe: <span className="text-gray-400 font-mono">{triggerTf}</span>
            {' '}— logs appear after each candle close
          </p>
          <div className="mt-4 text-xs text-gray-700 max-w-sm mx-auto text-left bg-gray-900 rounded-lg p-3 space-y-1">
            <p className="text-gray-500 font-medium mb-2">Why no logs yet?</p>
            <p>① Exchange WebSocket not connected (no OHLCV data flowing)</p>
            <p>② Celery worker not running scoring tasks</p>
            <p>③ Waiting for next candle close on {triggerTf} timeframe</p>
            <p className="mt-2 text-gray-600">
              Test with:{' '}
              <code className="text-gray-400 bg-gray-800 px-1 rounded">python test-log.py</code>
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((log, idx) => {
            const id = `${log.symbol}-${log.timestamp}-${idx}`
            const isExpanded = expandedId === id
            return (
              <div
                key={id}
                className={`border rounded-xl overflow-hidden cursor-pointer transition-all ${CLASS_COLORS[log.classification]}`}
                onClick={() => setExpandedId(isExpanded ? null : id)}
              >
                {/* Summary row */}
                <div className="flex items-center gap-3 px-4 py-2.5 flex-wrap">
                  <span className="font-mono text-xs text-gray-500 w-20 shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="font-bold text-white text-sm w-24 shrink-0">{log.symbol}</span>
                  <span className="text-xs text-gray-400">{log.timeframe}</span>

                  {/* Regime */}
                  <span className={`text-xs font-medium ${REGIME_COLORS[log.regime] ?? 'text-gray-400'}`}>
                    {log.regime} (ADX={log.adx})
                  </span>

                  {/* Score bar */}
                  <div className="flex items-center gap-1.5 flex-1 min-w-0">
                    <div className="flex-1 bg-gray-900 rounded-full h-1.5 min-w-16">
                      <div
                        className={`h-1.5 rounded-full ${
                          log.scores.final >= 75 ? 'bg-green-500' :
                          log.scores.final >= 55 ? 'bg-yellow-500' : 'bg-gray-600'
                        }`}
                        style={{ width: `${log.scores.final}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold text-white w-8 text-right">{log.scores.final}</span>
                  </div>

                  {/* Classification badge */}
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                    log.classification === 'ALERT' ? 'bg-green-700 text-white' :
                    log.classification === 'WATCH' ? 'bg-yellow-700 text-white' :
                    'bg-gray-700 text-gray-300'
                  }`}>
                    {log.classification}
                  </span>

                  <span className="text-gray-600 text-xs ml-auto">{isExpanded ? '▲' : '▼'}</span>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="border-t border-gray-700/50 px-4 py-3 space-y-3 bg-gray-900/50">
                    {/* Score breakdown */}
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Score Breakdown</p>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        {[
                          { label: 'Order Flow', val: log.scores.order_flow, max: 35 },
                          { label: 'SMC', val: log.scores.smc, max: 30 },
                          { label: 'VSA+Vol', val: log.scores.vsa, max: 30 },
                          { label: 'Context', val: log.scores.context, max: 15 },
                          { label: 'Confluence', val: log.scores.bonus, max: 15 },
                          { label: 'Raw Total', val: log.scores.raw, max: 125 },
                        ].map(({ label, val, max }) => (
                          <div key={label} className="bg-gray-800 rounded-lg px-2 py-1.5">
                            <div className="text-gray-500 text-xs">{label}</div>
                            <div className="font-mono text-white">
                              {val.toFixed(1)}<span className="text-gray-600">/{max}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Conditions met */}
                    {log.conditions_met.length > 0 && (
                      <div>
                        <p className="text-xs text-green-500 uppercase tracking-wide mb-1">✓ Conditions Met</p>
                        <ul className="space-y-0.5">
                          {log.conditions_met.map((c, i) => (
                            <li key={i} className="text-xs text-green-400 flex items-start gap-1">
                              <span className="shrink-0">✓</span> {c}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Conditions missed */}
                    {log.conditions_missed.length > 0 && (
                      <div>
                        <p className="text-xs text-red-500 uppercase tracking-wide mb-1">✗ Conditions Missed</p>
                        <ul className="space-y-0.5">
                          {log.conditions_missed.map((c, i) => (
                            <li key={i} className="text-xs text-red-400 flex items-start gap-1">
                              <span className="shrink-0">✗</span> {c}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Why not ALERT */}
                    {log.why_not_alert && (
                      <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-lg px-3 py-2">
                        <p className="text-xs text-yellow-400">
                          ⚠ {log.why_not_alert}
                        </p>
                      </div>
                    )}

                    {/* Market context */}
                    <div className="flex gap-4 text-xs text-gray-500 flex-wrap">
                      <span>HTF Bias: <span className="text-white">{log.htf_bias}</span></span>
                      <span>Delta: <span className="text-white">{log.delta > 0 ? '+' : ''}{log.delta}</span></span>
                      <span>Funding: <span className="text-white">{(log.funding_rate * 100).toFixed(4)}%</span></span>
                      <span>Portfolio Heat: <span className="text-white">{log.portfolio_heat.toFixed(2)}%</span></span>
                      <span>ATR: <span className="text-white">{log.atr}</span></span>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}

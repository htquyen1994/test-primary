/** Signal Audit — all scored signals with post-hoc outcome analysis. */

import { useCallback, useEffect, useState } from 'react'
import { fetchAuditPerformance, fetchAuditSignalDetail, fetchAuditSignals } from '../../api/monitorApi'
import type { PaginatedSignalAudit, PerformanceReport, SignalAuditDetail, SignalAuditItem } from '../../types/monitor'

type ResultFilter = 'all' | 'SIGNAL' | 'NO_SIGNAL'

function blockReasonBadge(reason: string | null) {
  if (!reason) return null
  const map: Record<string, string> = {
    MTF_BLOCK: 'bg-purple-900/40 text-purple-400',
    BTC_GUARD: 'bg-orange-900/40 text-orange-400',
    CB_LOCKED: 'bg-red-900/40 text-red-400',
    REGIME: 'bg-yellow-900/40 text-yellow-400',
    LOW_SCORE: 'bg-gray-800 text-gray-500',
  }
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${map[reason] ?? 'bg-gray-800 text-gray-500'}`}>
      {reason}
    </span>
  )
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 75 ? 'bg-green-500' : score >= 55 ? 'bg-yellow-500' : 'bg-gray-700'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 bg-gray-800 rounded-full h-1.5 flex-shrink-0">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`font-mono text-xs ${score >= 75 ? 'text-green-400' : score >= 55 ? 'text-yellow-400' : 'text-gray-500'}`}>
        {score}
      </span>
    </div>
  )
}

function OutcomeIndicators({ detail }: { detail: SignalAuditDetail }) {
  const indicators = [
    { label: 'SL', hit: detail.would_have_hit_sl, color: 'text-red-400' },
    { label: 'TP1', hit: detail.would_have_hit_tp1, color: 'text-green-400' },
    { label: 'TP2', hit: detail.would_have_hit_tp2, color: 'text-emerald-400' },
  ]
  return (
    <div className="flex gap-2 mt-2">
      {indicators.map(({ label, hit, color }) => (
        <span key={label} className={`text-xs ${hit === true ? color : hit === false ? 'text-gray-700 line-through' : 'text-gray-600'}`}>
          {label}: {hit === true ? '✓' : hit === false ? '✗' : '?'}
        </span>
      ))}
      {detail.max_favorable_excursion !== null && (
        <span className="text-xs text-gray-500 ml-2">
          MFE: <span className="text-green-400">+{(detail.max_favorable_excursion * 100).toFixed(2)}%</span>
          {' '}MAE: <span className="text-red-400">-{((detail.max_adverse_excursion ?? 0) * 100).toFixed(2)}%</span>
        </span>
      )}
    </div>
  )
}

function SignalRow({ item, onExpand }: { item: SignalAuditItem; onExpand: (id: number) => void }) {
  return (
    <tr
      className="border-b border-gray-800/40 hover:bg-gray-800/30 cursor-pointer transition-colors"
      onClick={() => onExpand(item.id)}
    >
      <td className="py-3 px-3 text-xs text-gray-500 font-mono">
        {new Date(item.timestamp_candle_close).toLocaleString()}
      </td>
      <td className="py-3 px-3">
        <span className="text-white text-sm font-medium">{item.symbol}</span>
        <span className="text-gray-600 text-xs ml-1">{item.timeframe}</span>
      </td>
      <td className="py-3 px-3">
        <ScoreBar score={item.final_score} />
      </td>
      <td className="py-3 px-3">
        <span className={`text-xs font-medium ${item.signal_result === 'SIGNAL' ? 'text-green-400' : 'text-gray-500'}`}>
          {item.signal_result === 'SIGNAL' ? '🟢 ALERT' : '⚫ NO_SIGNAL'}
        </span>
      </td>
      <td className="py-3 px-3">
        {blockReasonBadge(item.blocking_reason)}
      </td>
      <td className="py-3 px-3 text-xs text-gray-500">
        {item.regime}
        {item.mtf_scenario && (
          <span className={`ml-1 ${item.mtf_scenario === 'A' ? 'text-green-400' : item.mtf_scenario === 'B' ? 'text-yellow-400' : 'text-red-400'}`}>
            MTF-{item.mtf_scenario}
          </span>
        )}
      </td>
      <td className="py-3 px-3 text-right">
        <span className="text-gray-600 text-xs">▼</span>
      </td>
    </tr>
  )
}

function DetailDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const [detail, setDetail] = useState<SignalAuditDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAuditSignalDetail(id)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [id])

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end justify-center" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-t-2xl w-full max-w-3xl p-6 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-white font-bold">Signal Audit #{id}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-lg">✕</button>
        </div>

        {loading ? (
          <div className="text-center py-8 text-gray-500 animate-pulse">Loading…</div>
        ) : !detail ? (
          <div className="text-center py-8 text-gray-600">Failed to load detail</div>
        ) : (
          <div className="space-y-4">
            {/* Score breakdown */}
            {detail.score_breakdown && (
              <div>
                <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Score Breakdown</h4>
                <div className="grid grid-cols-5 gap-2">
                  {Object.entries(detail.score_breakdown).map(([k, v]) => (
                    <div key={k} className="bg-gray-800 rounded-lg p-2 text-center">
                      <div className="text-xs text-gray-500 mb-1">{k.toUpperCase()}</div>
                      <div className="font-mono font-bold text-white">{typeof v === 'number' ? v.toFixed(1) : v}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Price levels */}
            <div>
              <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Proposed Levels</h4>
              <div className="grid grid-cols-4 gap-2 text-sm">
                {[
                  ['Entry', detail.entry_price_proposed],
                  ['SL', detail.sl_proposed],
                  ['TP1', detail.tp1_proposed],
                  ['TP2', detail.tp2_proposed],
                ].map(([label, val]) => (
                  <div key={label as string} className="bg-gray-800 rounded-lg p-2">
                    <div className="text-xs text-gray-500">{label as string}</div>
                    <div className="font-mono text-white">
                      {val != null ? (val as number).toLocaleString() : '—'}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Post-hoc outcome */}
            {detail.would_have_hit_sl !== null && (
              <div>
                <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Post-hoc Outcome</h4>
                <OutcomeIndicators detail={detail} />
                <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                  {[
                    ['T+1 price', detail.price_at_T1],
                    ['T+4 price', detail.price_at_T4],
                    ['T+16 price', detail.price_at_T16],
                  ].map(([label, val]) => (
                    <div key={label as string} className="bg-gray-800/50 rounded p-2">
                      <span className="text-gray-500">{label as string}: </span>
                      <span className="text-gray-300 font-mono">
                        {val != null ? (val as number).toLocaleString() : '—'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Context */}
            <div className="grid grid-cols-3 gap-2 text-xs text-gray-400">
              {[
                ['ATR', detail.atr_value?.toFixed(2)],
                ['ADX', detail.adx_value?.toFixed(1)],
                ['Delta', detail.delta_value?.toFixed(0)],
                ['Threshold', detail.delta_threshold?.toFixed(0)],
                ['Funding', detail.funding_rate !== null ? (detail.funding_rate * 100).toFixed(4) + '%' : '—'],
                ['OB', detail.ob_available ? '✓' : '✗ (capped)'],
              ].map(([label, val]) => (
                <span key={label as string}>
                  <span className="text-gray-600">{label as string}: </span>
                  <span className="text-gray-300">{val ?? '—'}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function PerformanceSummary() {
  const [report, setReport] = useState<PerformanceReport | null>(null)

  useEffect(() => {
    fetchAuditPerformance().then(setReport).catch(() => null)
  }, [])

  if (!report) return null

  return (
    <div className="grid grid-cols-5 gap-3 mb-4">
      {[
        { label: 'Total Signals', value: report.total_signals?.toString() ?? '—' },
        { label: 'Win Rate', value: `${((report.win_rate ?? 0) * 100).toFixed(1)}%` },
        { label: 'Profit Factor', value: report.profit_factor?.toFixed(2) ?? '—' },
        { label: 'Net PnL', value: `$${report.total_net_pnl?.toFixed(2) ?? '—'}` },
        { label: 'Avg Hold', value: `${report.avg_hold_minutes?.toFixed(0) ?? '—'}m` },
      ].map(({ label, value }) => (
        <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
          <div className="text-xs text-gray-500 mb-1">{label}</div>
          <div className="font-bold text-white font-mono text-sm">{value}</div>
        </div>
      ))}
    </div>
  )
}

export function AuditTab() {
  const [data, setData] = useState<PaginatedSignalAudit | null>(null)
  const [page, setPage] = useState(1)
  const [resultFilter, setResultFilter] = useState<ResultFilter>('all')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchAuditSignals({
        page,
        limit: 50,
        result: resultFilter !== 'all' ? resultFilter : undefined,
      })
      setData(res)
    } finally {
      setLoading(false)
    }
  }, [page, resultFilter])

  useEffect(() => { load() }, [load])

  const totalPages = data ? Math.ceil(data.total / 50) : 1

  return (
    <div className="space-y-4">
      <PerformanceSummary />

      {/* Filter */}
      <div className="flex gap-2">
        {(['all', 'SIGNAL', 'NO_SIGNAL'] as const).map((f) => (
          <button
            key={f}
            onClick={() => { setResultFilter(f); setPage(1) }}
            className={`text-xs px-3 py-1 rounded-full transition-colors ${
              resultFilter === f ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {f === 'all' ? 'All' : f === 'SIGNAL' ? '🟢 Alert Only' : '⚫ No Signal'}
          </button>
        ))}
        {data && <span className="text-xs text-gray-600 self-center ml-2">{data.total} records</span>}
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500 animate-pulse">Loading audit…</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                {['Candle Time', 'Symbol', 'Score', 'Result', 'Block Reason', 'Regime', ''].map((h) => (
                  <th key={h} className="text-left py-2 px-3 text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.items.map((item) => (
                <SignalRow key={item.id} item={item} onExpand={setExpandedId} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      <div className="flex justify-center gap-3">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-sm rounded-lg text-gray-300 transition-colors"
        >
          ← Prev
        </button>
        <span className="text-gray-500 text-sm py-1.5">Page {page} / {totalPages}</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={page >= totalPages}
          className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-sm rounded-lg text-gray-300 transition-colors"
        >
          Next →
        </button>
      </div>

      {/* Detail drawer */}
      {expandedId !== null && (
        <DetailDrawer id={expandedId} onClose={() => setExpandedId(null)} />
      )}
    </div>
  )
}

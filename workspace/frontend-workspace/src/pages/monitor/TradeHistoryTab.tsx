/** Trade History — completed trades from /api/journal + audit outcome from /api/audit/trades. */

import { useCallback, useEffect, useState } from 'react'
import { fetchAuditTrades, fetchJournal } from '../../api/monitorApi'
import type { PaginatedTradeAudit, TradeAuditItem, TradeJournalEntry } from '../../types/monitor'

function resultBadge(result: string | null, outcome?: string | null) {
  const r = outcome ?? result
  switch (r?.toLowerCase()) {
    case 'win':
    case 'tp1_hit':
    case 'tp2_hit':
    case 'win':
      return { label: '✅ WIN', cls: 'bg-green-900/40 text-green-400' }
    case 'loss':
    case 'sl_hit':
      return { label: '❌ LOSS', cls: 'bg-red-900/40 text-red-400' }
    case 'be':
    case 'breakeven':
      return { label: '⚖ BE', cls: 'bg-gray-800 text-gray-400' }
    default:
      return { label: '— OPEN', cls: 'bg-blue-900/30 text-blue-400' }
  }
}

function verdictBadge(verdict: string | null) {
  switch (verdict) {
    case 'GOOD_SIGNAL': return 'text-green-400'
    case 'BAD_SIGNAL': return 'text-red-400'
    case 'ACCEPTABLE': return 'text-yellow-400'
    default: return 'text-gray-600'
  }
}

type HistoryFilter = 'all' | 'win' | 'loss' | 'be'

function FilterChip({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-3 py-1 rounded-full transition-colors ${
        active
          ? 'bg-blue-600 text-white'
          : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
      }`}
    >
      {label}
    </button>
  )
}

function PnlCell({ value }: { value: number | null }) {
  if (value === null) return <span className="text-gray-600">—</span>
  return (
    <span className={value >= 0 ? 'text-green-400' : 'text-red-400'}>
      {value >= 0 ? '+' : ''}${value.toFixed(2)}
    </span>
  )
}

export function TradeHistoryTab() {
  const [journalEntries, setJournalEntries] = useState<TradeJournalEntry[]>([])
  const [auditTrades, setAuditTrades] = useState<Map<string, TradeAuditItem>>(new Map())
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<HistoryFilter>('all')
  const [loading, setLoading] = useState(true)
  const [totalPages, setTotalPages] = useState(1)
  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [journal, auditRes] = await Promise.all([
        fetchJournal(page, PAGE_SIZE),
        fetchAuditTrades({ page, limit: PAGE_SIZE }),
      ])

      setJournalEntries(journal)

      // Build audit map keyed by trade_id for O(1) lookup
      const auditMap = new Map<string, TradeAuditItem>()
      for (const t of auditRes.items) {
        if (t.trade_id) auditMap.set(t.trade_id, t)
      }
      setAuditTrades(auditMap)
      setTotalPages(Math.ceil(auditRes.total / PAGE_SIZE) || 1)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { load() }, [load])

  const filtered = journalEntries.filter((e) => {
    if (filter === 'all') return true
    if (filter === 'win') return e.result === 'win'
    if (filter === 'loss') return e.result === 'loss'
    if (filter === 'be') return e.result === 'be'
    return true
  })

  // Summary bar
  const wins = journalEntries.filter((e) => e.result === 'win').length
  const losses = journalEntries.filter((e) => e.result === 'loss').length
  const totalPnl = journalEntries.reduce((sum, e) => sum + (e.net_pnl ?? 0), 0)
  const winRate = journalEntries.length > 0 ? ((wins / journalEntries.length) * 100).toFixed(0) : '—'

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Trades', value: journalEntries.length.toString(), color: 'text-white' },
          { label: 'Win Rate', value: `${winRate}%`, color: wins > losses ? 'text-green-400' : 'text-red-400' },
          { label: 'Net PnL', value: `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`, color: totalPnl >= 0 ? 'text-green-400' : 'text-red-400' },
          { label: 'W / L', value: `${wins} / ${losses}`, color: 'text-gray-300' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
            <div className="text-xs text-gray-500 mb-1">{label}</div>
            <div className={`font-bold font-mono ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Filter chips */}
      <div className="flex gap-2">
        {(['all', 'win', 'loss', 'be'] as const).map((f) => (
          <FilterChip key={f} active={filter === f} label={f.toUpperCase()} onClick={() => setFilter(f)} />
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-12 text-gray-500 animate-pulse">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-600">No trades match filter</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                {['Symbol', 'Dir', 'Entry Price', 'Exit Price', 'Net PnL', 'Result', 'Score', 'Verdict', 'Duration'].map((h) => (
                  <th key={h} className="text-left py-2 px-3 text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry) => {
                const audit = auditTrades.get(entry.trade_id)
                const badge = resultBadge(entry.result, audit?.outcome)
                const entryTs = entry.entry_timestamp ? new Date(entry.entry_timestamp) : null
                const exitTs = entry.exit_timestamp ? new Date(entry.exit_timestamp) : null
                const holdMin = entryTs && exitTs
                  ? Math.round((exitTs.getTime() - entryTs.getTime()) / 60000)
                  : null

                return (
                  <tr key={entry.trade_id} className="border-b border-gray-800/40 hover:bg-gray-800/20 transition-colors">
                    <td className="py-3 px-3">
                      <span className="font-medium text-white">{entry.asset}</span>
                      <div className="text-xs text-gray-600 font-mono">{entry.trade_id.slice(0, 8)}…</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`text-xs font-medium ${entry.direction === 'long' ? 'text-green-400' : 'text-red-400'}`}>
                        {entry.direction.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono text-sm text-gray-300">
                      {entry.actual_entry_price.toLocaleString()}
                      {entry.slippage_entry > 0 && (
                        <div className="text-xs text-orange-400/70">+{entry.slippage_entry.toFixed(2)} slip</div>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono text-sm">
                      {entry.actual_exit_price
                        ? <span className="text-gray-300">{entry.actual_exit_price.toLocaleString()}</span>
                        : <span className="text-gray-600 text-xs">Open</span>}
                    </td>
                    <td className="py-3 px-3 font-mono font-bold">
                      <PnlCell value={entry.net_pnl} />
                      {entry.fee_entry + entry.fee_exit > 0 && (
                        <div className="text-xs text-gray-600">
                          fees: ${(entry.fee_entry + entry.fee_exit).toFixed(3)}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span className="text-gray-300 font-mono text-sm">{entry.signal_score}</span>
                    </td>
                    <td className="py-3 px-3">
                      {audit?.signal_quality_verdict ? (
                        <span className={`text-xs font-medium ${verdictBadge(audit.signal_quality_verdict)}`}>
                          {audit.signal_quality_verdict.replace('_', ' ')}
                        </span>
                      ) : (
                        <span className="text-gray-700 text-xs">Pending</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-xs text-gray-500">
                      {holdMin !== null ? `${holdMin}m` : '—'}
                    </td>
                  </tr>
                )
              })}
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
          disabled={page >= totalPages || journalEntries.length < PAGE_SIZE}
          className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-sm rounded-lg text-gray-300 transition-colors"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

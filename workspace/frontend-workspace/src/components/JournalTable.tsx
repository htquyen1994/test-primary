/**
 * JournalTable
 * Displays all confirmed trades with PnL, slippage, and result.
 *
 * Satisfies: Requirement 18.7
 */
import type { TradeJournalEntry } from '../types'

interface Props {
  entries: TradeJournalEntry[]
}

export function JournalTable({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No trades yet. Confirm a signal to start trading.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 uppercase tracking-wide border-b border-gray-800">
            <th className="pb-2 pr-4">Time</th>
            <th className="pb-2 pr-4">Asset</th>
            <th className="pb-2 pr-4">Dir</th>
            <th className="pb-2 pr-4">Score</th>
            <th className="pb-2 pr-4">Entry</th>
            <th className="pb-2 pr-4">SL</th>
            <th className="pb-2 pr-4">TP1</th>
            <th className="pb-2 pr-4">Fill</th>
            <th className="pb-2 pr-4">Slip</th>
            <th className="pb-2 pr-4">Gross PnL</th>
            <th className="pb-2 pr-4">Net PnL</th>
            <th className="pb-2">Result</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {entries.map((t) => (
            <tr
              key={t.trade_id}
              className={`${
                t.result === 'win' ? 'bg-green-900/10' :
                t.result === 'loss' ? 'bg-red-900/10' :
                'bg-gray-900/10'
              }`}
            >
              <td className="py-2 pr-4 text-gray-400 text-xs">
                {new Date(t.entry_timestamp).toLocaleString()}
              </td>
              <td className="py-2 pr-4 font-medium text-white">{t.asset}</td>
              <td className={`py-2 pr-4 font-semibold ${t.direction === 'long' ? 'text-green-400' : 'text-red-400'}`}>
                {t.direction.toUpperCase()}
              </td>
              <td className="py-2 pr-4 text-gray-300">{t.signal_score}</td>
              <td className="py-2 pr-4 font-mono text-gray-300">${t.entry_price.toLocaleString()}</td>
              <td className="py-2 pr-4 font-mono text-red-400">${t.stop_loss.toLocaleString()}</td>
              <td className="py-2 pr-4 font-mono text-green-400">${t.take_profit_1.toLocaleString()}</td>
              <td className="py-2 pr-4 font-mono text-gray-300">
                ${(t.actual_entry_price ?? t.entry_price).toLocaleString()}
              </td>
              <td className="py-2 pr-4 font-mono text-xs text-gray-500">
                {t.slippage_entry >= 0 ? '+' : ''}{t.slippage_entry.toFixed(2)}
              </td>
              <td className={`py-2 pr-4 font-mono ${(t.gross_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {t.gross_pnl != null ? `$${t.gross_pnl.toFixed(2)}` : '—'}
              </td>
              <td className={`py-2 pr-4 font-mono font-semibold ${(t.net_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {t.net_pnl != null ? `$${t.net_pnl.toFixed(2)}` : '—'}
              </td>
              <td className="py-2">
                {t.result === 'win' && <span className="text-xs bg-green-900/50 text-green-400 px-2 py-0.5 rounded">WIN</span>}
                {t.result === 'loss' && <span className="text-xs bg-red-900/50 text-red-400 px-2 py-0.5 rounded">LOSS</span>}
                {t.result === 'be' && <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">BE</span>}
                {!t.result && <span className="text-xs text-gray-600">OPEN</span>}
                {t.is_testnet && <span className="ml-1 text-xs text-yellow-600">TEST</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

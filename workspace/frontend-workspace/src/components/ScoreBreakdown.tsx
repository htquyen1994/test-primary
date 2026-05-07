/**
 * ScoreBreakdown
 * Displays per-module score bars for a Signal Card.
 */
import type { ScoreBreakdown as ScoreBreakdownType } from '../types'

interface Props {
  breakdown: ScoreBreakdownType
  finalScore: number
}

const MODULES = [
  { key: 'order_flow' as const, label: 'Order Flow', max: 35, color: 'bg-blue-500' },
  { key: 'smc' as const, label: 'SMC', max: 30, color: 'bg-purple-500' },
  { key: 'vsa' as const, label: 'VSA + Vol', max: 30, color: 'bg-yellow-500' },
  { key: 'context' as const, label: 'Context', max: 15, color: 'bg-cyan-500' },
  { key: 'bonus' as const, label: 'Confluence', max: 15, color: 'bg-green-500' },
]

export function ScoreBreakdown({ breakdown, finalScore }: Props) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400 uppercase tracking-wide">Score Breakdown</span>
        <span className="text-lg font-bold text-white">{finalScore}</span>
      </div>
      {MODULES.map(({ key, label, max, color }) => {
        const value = breakdown[key] ?? 0
        const pct = Math.round((value / max) * 100)
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="text-xs text-gray-400 w-20 shrink-0">{label}</span>
            <div className="flex-1 bg-gray-800 rounded-full h-1.5">
              <div
                className={`${color} h-1.5 rounded-full transition-all`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 w-8 text-right">{value.toFixed(0)}</span>
          </div>
        )
      })}
    </div>
  )
}

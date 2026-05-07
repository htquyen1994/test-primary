/**
 * AnalyticsPage — Performance Metrics
 * Satisfies: Requirement 18.8
 */
import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { AnalyticsData } from '../types'

interface MetricCardProps {
  label: string
  value: string
  sub?: string
  color?: string
}

function MetricCard({ label, value, sub, color = 'text-white' }: MetricCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  )
}

export function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/analytics')
      .then((r) => r.json())
      .then((data) => {
        setAnalytics(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading analytics...</div>
  }

  if (!analytics || analytics.total_trades === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-xl font-bold text-white mb-4">Analytics</h1>
        <div className="text-center py-12 text-gray-500">
          No trade data yet. Complete some trades to see analytics.
        </div>
      </div>
    )
  }

  const winRateColor = analytics.win_rate >= 0.55 ? 'text-green-400' :
                       analytics.win_rate >= 0.45 ? 'text-yellow-400' : 'text-red-400'
  const pfColor = analytics.profit_factor >= 1.5 ? 'text-green-400' :
                  analytics.profit_factor >= 1.0 ? 'text-yellow-400' : 'text-red-400'
  const pnlColor = analytics.net_profit >= 0 ? 'text-green-400' : 'text-red-400'

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <h1 className="text-xl font-bold text-white">Analytics</h1>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="Win Rate (net)"
          value={`${(analytics.win_rate * 100).toFixed(1)}%`}
          sub={`${analytics.winning_trades ?? 0}W / ${analytics.losing_trades ?? 0}L`}
          color={winRateColor}
        />
        <MetricCard
          label="Profit Factor"
          value={analytics.profit_factor === Infinity ? '∞' : analytics.profit_factor.toFixed(2)}
          color={pfColor}
        />
        <MetricCard
          label="Net Profit"
          value={`$${analytics.net_profit.toFixed(2)}`}
          color={pnlColor}
        />
        <MetricCard
          label="Max Drawdown"
          value={`${(analytics.max_drawdown * 100).toFixed(1)}%`}
          color={analytics.max_drawdown < -0.15 ? 'text-red-400' : 'text-yellow-400'}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={analytics.sharpe_ratio.toFixed(2)}
          color={analytics.sharpe_ratio >= 1.0 ? 'text-green-400' : 'text-yellow-400'}
        />
        <MetricCard
          label="Total Trades"
          value={String(analytics.total_trades)}
          sub={analytics.total_trades < 30 ? '⚠ insufficient data' : undefined}
        />
      </div>
    </div>
  )
}

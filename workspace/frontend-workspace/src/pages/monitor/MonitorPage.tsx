/**
 * MonitorPage — Trade Monitor with 4 tabs:
 *   LIVE     — open positions with real-time unrealized PnL
 *   ORDERS   — pending/in-flight executions + exchange resting orders
 *   HISTORY  — completed trades with audit outcome
 *   AUDIT    — all scored signals with post-hoc analysis
 */

import { useEffect, useState } from 'react'
import { useMonitorStore } from '../../store/monitorStore'
import { LivePositionsTab } from './LivePositionsTab'
import { PendingOrdersTab } from './PendingOrdersTab'
import { TradeHistoryTab } from './TradeHistoryTab'
import { AuditTab } from './AuditTab'

type Tab = 'live' | 'orders' | 'history' | 'audit'

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'live',    label: 'Live Positions', icon: '📍' },
  { id: 'orders',  label: 'Pending Orders', icon: '⏳' },
  { id: 'history', label: 'Trade History',  icon: '📋' },
  { id: 'audit',   label: 'Signal Audit',   icon: '🔍' },
]

// Auto-refresh interval for live data (10s)
const REFRESH_INTERVAL_MS = 10_000

function AccountBar() {
  const { account, loadingAccount } = useMonitorStore()

  if (loadingAccount || !account) return null

  const pnlColor = account.total_realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'

  return (
    <div className="flex gap-6 text-sm bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 mb-4">
      {[
        { label: 'Balance',     value: `$${account.balance_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,      color: 'text-white' },
        { label: 'Equity',      value: `$${account.equity_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,       color: 'text-white' },
        { label: 'Used Margin', value: `$${account.used_margin.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,      color: 'text-orange-400' },
        { label: 'Realized PnL',value: `${account.total_realized_pnl >= 0 ? '+' : ''}$${account.total_realized_pnl.toFixed(2)}`, color: pnlColor },
        { label: 'Fees Paid',   value: `$${account.total_fees_paid.toFixed(2)}`,   color: 'text-gray-400' },
      ].map(({ label, value, color }) => (
        <div key={label} className="text-center">
          <div className="text-xs text-gray-500 mb-0.5">{label}</div>
          <div className={`font-mono font-bold ${color}`}>{value}</div>
        </div>
      ))}
    </div>
  )
}

function TabButton({ tab, active, onClick, badge }: {
  tab: typeof TABS[number]
  active: boolean
  onClick: () => void
  badge?: number
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors border-b-2 ${
        active
          ? 'border-blue-500 text-white bg-gray-800/50'
          : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/30'
      }`}
    >
      <span>{tab.icon}</span>
      <span>{tab.label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="bg-blue-600 text-white text-xs px-1.5 rounded-full">{badge}</span>
      )}
    </button>
  )
}

export function MonitorPage() {
  const [activeTab, setActiveTab] = useState<Tab>('live')
  const { refreshAll, positions, pendingExecutions, openOrders, lastRefreshed, error } = useMonitorStore()

  // Initial load + periodic refresh for live/orders tabs
  useEffect(() => {
    refreshAll()
    const interval = setInterval(refreshAll, REFRESH_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [refreshAll])

  const badges: Partial<Record<Tab, number>> = {
    live: positions.length,
    orders: pendingExecutions.length + openOrders.length,
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-white">Trade Monitor</h1>
          {lastRefreshed && (
            <p className="text-xs text-gray-600 mt-0.5">
              Last refreshed {lastRefreshed.toLocaleTimeString()} · auto-refresh every 10s
            </p>
          )}
        </div>
        <button
          onClick={refreshAll}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 bg-red-900/30 border border-red-800 rounded-lg px-4 py-2 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Account summary */}
      <AccountBar />

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-800 mb-4">
        {TABS.map((tab) => (
          <TabButton
            key={tab.id}
            tab={tab}
            active={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            badge={badges[tab.id]}
          />
        ))}
      </div>

      {/* Tab content */}
      <div className="min-h-[400px]">
        {activeTab === 'live'    && <LivePositionsTab />}
        {activeTab === 'orders'  && <PendingOrdersTab />}
        {activeTab === 'history' && <TradeHistoryTab />}
        {activeTab === 'audit'   && <AuditTab />}
      </div>
    </div>
  )
}

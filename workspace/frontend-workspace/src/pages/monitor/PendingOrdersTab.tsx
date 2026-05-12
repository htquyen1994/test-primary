/** Pending orders: in-flight Celery executions + exchange PENDING/OPEN orders. */

import { useState } from 'react'
import { useMonitorStore } from '../../store/monitorStore'
import type { ExchangeOrder, ExecutionStatus } from '../../types/monitor'

function executionStatusBadge(status: string) {
  switch (status) {
    case 'Executing':
      return 'bg-yellow-900/40 text-yellow-400 animate-pulse'
    case 'Submitted':
      return 'bg-blue-900/40 text-blue-400'
    case 'Filled':
      return 'bg-green-900/40 text-green-400'
    case 'Failed':
    case 'Rejected':
      return 'bg-red-900/40 text-red-400'
    default:
      return 'bg-gray-800 text-gray-400'
  }
}

function orderStatusBadge(status: string) {
  switch (status) {
    case 'PENDING':
      return 'bg-yellow-900/40 text-yellow-300'
    case 'OPEN':
      return 'bg-blue-900/40 text-blue-300'
    case 'FILLED':
      return 'bg-green-900/40 text-green-300'
    case 'CANCELLED':
      return 'bg-gray-800 text-gray-500'
    case 'REJECTED':
      return 'bg-red-900/40 text-red-400'
    default:
      return 'bg-gray-800 text-gray-400'
  }
}

function orderTypeLabel(type: string) {
  return { market: 'MKT', limit: 'LMT', stop_loss: 'SL', take_profit: 'TP' }[type] ?? type.toUpperCase()
}

function ExecutionRow({ exec }: { exec: ExecutionStatus }) {
  return (
    <tr className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors">
      <td className="py-3 px-3">
        <span className="font-medium text-white text-sm">{exec.asset || exec.symbol || '—'}</span>
        <div className="text-xs text-gray-500 font-mono">{exec.signal_id?.slice(0, 16)}…</div>
      </td>
      <td className="py-3 px-3">
        <span className="text-xs text-gray-400">ENTRY</span>
      </td>
      <td className="py-3 px-3 text-right">
        {exec.position_size_usd ? (
          <span className="text-gray-300 text-sm">${exec.position_size_usd.toFixed(2)}</span>
        ) : '—'}
      </td>
      <td className="py-3 px-3 text-right">
        {exec.fill_price ? (
          <span className="text-green-300 font-mono text-sm">{exec.fill_price.toLocaleString()}</span>
        ) : (
          <span className="text-gray-600 text-xs">Waiting…</span>
        )}
      </td>
      <td className="py-3 px-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${executionStatusBadge(exec.status)}`}>
          {exec.status}
        </span>
      </td>
      <td className="py-3 px-3 text-xs text-gray-600">
        {exec.dispatched_at ? new Date(exec.dispatched_at).toLocaleTimeString() : '—'}
      </td>
      <td className="py-3 px-3 text-center">
        {/* Celery tasks can't be cancelled mid-flight */}
        <span className="text-gray-700 text-xs">—</span>
      </td>
    </tr>
  )
}

function OrderRow({ order, onCancel }: { order: ExchangeOrder; onCancel: (id: string, sym: string) => void }) {
  const [cancelling, setCancelling] = useState(false)

  const handleCancel = async () => {
    setCancelling(true)
    try {
      await onCancel(order.order_id, order.symbol)
    } finally {
      setCancelling(false)
    }
  }

  const canCancel = order.status === 'PENDING' || order.status === 'OPEN'

  return (
    <tr className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors">
      <td className="py-3 px-3">
        <span className="font-medium text-white text-sm">{order.symbol}</span>
        <div className="text-xs text-gray-500 font-mono">{order.order_id.slice(0, 12)}…</div>
      </td>
      <td className="py-3 px-3">
        <span className="text-xs text-gray-400">{orderTypeLabel(order.order_type)}</span>
        <span className={`ml-1.5 text-xs ${order.side === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
          {order.side.toUpperCase()}
        </span>
      </td>
      <td className="py-3 px-3 text-right font-mono text-sm text-gray-300">
        {order.amount.toFixed(5)}
      </td>
      <td className="py-3 px-3 text-right font-mono text-sm text-white">
        {order.price.toLocaleString()}
        {order.fill_price && (
          <div className="text-xs text-green-400">Fill: {order.fill_price.toLocaleString()}</div>
        )}
      </td>
      <td className="py-3 px-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${orderStatusBadge(order.status)}`}>
          {order.status}
        </span>
      </td>
      <td className="py-3 px-3 text-xs text-gray-600">
        {new Date(order.created_at).toLocaleTimeString()}
      </td>
      <td className="py-3 px-3 text-center">
        {canCancel ? (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="text-xs px-2 py-1 rounded-md bg-red-900/30 hover:bg-red-900/60 text-red-400 transition-colors disabled:opacity-40"
          >
            {cancelling ? '…' : 'Cancel'}
          </button>
        ) : (
          <span className="text-gray-700 text-xs">—</span>
        )}
      </td>
    </tr>
  )
}

export function PendingOrdersTab() {
  const { pendingExecutions, openOrders, loadingOrders, cancelOrder } = useMonitorStore()

  const totalPending = pendingExecutions.length + openOrders.length

  if (loadingOrders && totalPending === 0) {
    return (
      <div className="text-center py-16 text-gray-500">
        <div className="animate-pulse text-2xl mb-2">⟳</div>
        Loading orders…
      </div>
    )
  }

  if (!loadingOrders && totalPending === 0) {
    return (
      <div className="text-center py-16 text-gray-600">
        <p className="text-3xl mb-2">📋</p>
        <p>No pending orders</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="text-left py-2 px-3 text-xs text-gray-500 font-medium">Symbol</th>
            <th className="text-left py-2 px-3 text-xs text-gray-500 font-medium">Type</th>
            <th className="text-right py-2 px-3 text-xs text-gray-500 font-medium">Amount / Size</th>
            <th className="text-right py-2 px-3 text-xs text-gray-500 font-medium">Price</th>
            <th className="py-2 px-3 text-xs text-gray-500 font-medium">Status</th>
            <th className="py-2 px-3 text-xs text-gray-500 font-medium">Time</th>
            <th className="text-center py-2 px-3 text-xs text-gray-500 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {/* In-flight Celery executions */}
          {pendingExecutions.map((exec) => (
            <ExecutionRow key={exec.signal_id} exec={exec} />
          ))}
          {/* Exchange open orders (SL/TP waiting) */}
          {openOrders.map((order) => (
            <OrderRow key={order.order_id} order={order} onCancel={cancelOrder} />
          ))}
        </tbody>
      </table>

      {/* Legend */}
      <div className="mt-4 flex gap-4 text-xs text-gray-600 px-3">
        <span><span className="text-yellow-400">⏳ EXECUTING</span> = Celery task dispatched, filling on exchange</span>
        <span><span className="text-blue-400">🔵 OPEN</span> = Resting SL/TP on exchange waiting for fill</span>
      </div>
    </div>
  )
}

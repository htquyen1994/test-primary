/** Live open positions with real-time unrealized PnL. */

import { useEffect, useRef } from 'react'
import { useMonitorStore } from '../../store/monitorStore'
import type { Position } from '../../types/monitor'

function pnlColor(pnl: number) {
  if (pnl > 0) return 'text-green-400'
  if (pnl < 0) return 'text-red-400'
  return 'text-gray-400'
}

function directionBadge(dir: string) {
  return dir === 'long'
    ? 'bg-green-900/50 text-green-400'
    : 'bg-red-900/50 text-red-400'
}

function ProgressBar({ position }: { position: Position }) {
  const { entry_price, take_profit_1, stop_loss, current_price, direction } = position
  if (!current_price || entry_price === stop_loss) return null

  const range = Math.abs(take_profit_1 - entry_price)
  const progress = direction === 'long'
    ? (current_price - entry_price) / range
    : (entry_price - current_price) / range
  const pct = Math.max(0, Math.min(100, progress * 100))
  const isProfit = direction === 'long' ? current_price > entry_price : current_price < entry_price

  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>SL {stop_loss.toLocaleString()}</span>
        <span className={pct > 60 ? 'text-green-400' : 'text-gray-400'}>
          {pct.toFixed(0)}% to TP1
        </span>
        <span>TP1 {take_profit_1.toLocaleString()}</span>
      </div>
      <div className="w-full bg-gray-800 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${
            isProfit ? 'bg-green-500' : 'bg-red-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function PositionCard({ position }: { position: Position }) {
  const { cancelOrder } = useMonitorStore()

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white text-sm">{position.symbol}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${directionBadge(position.direction)}`}>
            {position.direction.toUpperCase()}
          </span>
          <span className="text-xs text-gray-500">{position.leverage}×</span>
        </div>
        <div className={`text-right ${pnlColor(position.unrealized_pnl)}`}>
          <div className="font-mono font-bold text-sm">
            {position.unrealized_pnl >= 0 ? '+' : ''}
            ${position.unrealized_pnl.toFixed(2)}
          </div>
          <div className="text-xs">
            {position.unrealized_pnl_pct >= 0 ? '+' : ''}
            {position.unrealized_pnl_pct.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Price levels */}
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div className="bg-gray-800/60 rounded-lg p-2">
          <div className="text-gray-500 mb-0.5">Entry</div>
          <div className="text-white font-mono">{position.entry_price.toLocaleString()}</div>
        </div>
        <div className="bg-gray-800/60 rounded-lg p-2">
          <div className="text-gray-500 mb-0.5">Current</div>
          <div className={`font-mono ${pnlColor(position.unrealized_pnl)}`}>
            {position.current_price.toLocaleString()}
          </div>
        </div>
        <div className="bg-red-900/20 border border-red-900/30 rounded-lg p-2">
          <div className="text-red-400/70 mb-0.5">SL</div>
          <div className="text-red-300 font-mono">{position.stop_loss.toLocaleString()}</div>
        </div>
        <div className="bg-green-900/20 border border-green-900/30 rounded-lg p-2">
          <div className="text-green-400/70 mb-0.5">TP1</div>
          <div className="text-green-300 font-mono">{position.take_profit_1.toLocaleString()}</div>
        </div>
      </div>

      {/* Progress bar */}
      <ProgressBar position={position} />

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <div className="flex gap-3">
          <span>Size: <span className="text-gray-300">${position.amount.toFixed(4)}</span></span>
          {position.signal_id && (
            <span>Signal: <span className="text-gray-400 font-mono">{position.signal_id.slice(0, 12)}…</span></span>
          )}
          <span>Opened: <span className="text-gray-300">{new Date(position.opened_at).toLocaleTimeString()}</span></span>
        </div>
        {/* Close is manual on real exchange; for mock we show a hint */}
        <span className="text-gray-700 text-xs">SL/TP managed by exchange</span>
      </div>
    </div>
  )
}

// WebSocket hook for real-time position price updates
function usePositionsWebSocket() {
  const updatePositionFromWS = useMonitorStore((s) => s.updatePositionFromWS)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host.replace(':5173', ':8001')}/ws/positions`)
    wsRef.current = ws

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'positions' && Array.isArray(msg.data)) {
          updatePositionFromWS(msg.data)
        }
      } catch { /* ignore malformed */ }
    }

    ws.onclose = () => {
      // Reconnect after 3s on unexpected close
      setTimeout(() => usePositionsWebSocket(), 3000)
    }

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}')
    }, 25000)

    return () => {
      clearInterval(ping)
      ws.close()
    }
  }, [updatePositionFromWS])
}

export function LivePositionsTab() {
  const { positions, loadingPositions, refreshPositions } = useMonitorStore()
  usePositionsWebSocket()

  if (loadingPositions && positions.length === 0) {
    return (
      <div className="text-center py-16 text-gray-500">
        <div className="animate-pulse text-2xl mb-2">⟳</div>
        Loading positions…
      </div>
    )
  }

  if (!loadingPositions && positions.length === 0) {
    return (
      <div className="text-center py-16 text-gray-600">
        <p className="text-3xl mb-2">📭</p>
        <p>No open positions</p>
        <p className="text-xs mt-1">Confirm a signal to open a position</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {positions.map((pos) => (
        <PositionCard key={`${pos.symbol}-${pos.opened_at}`} position={pos} />
      ))}
    </div>
  )
}

/**
 * SignalCard
 * Displays all relevant information for a single Signal.
 * Includes Countdown Timer, Score Breakdown, Confirm/Skip buttons.
 *
 * Satisfies: Requirements 18.1, 18.2, 18.3, 18.4, 18.5
 */
import { useState } from 'react'
import { useAlertsStore } from '../store/alertsStore'
import { CountdownTimer } from './CountdownTimer'
import { ScoreBreakdown } from './ScoreBreakdown'
import type { SignalCard as SignalCardType } from '../types'

interface Props {
  signal: SignalCardType
  currentCandle?: number
}

const REGIME_COLORS: Record<string, string> = {
  TRENDING: 'text-green-400 bg-green-900/30',
  RANGING: 'text-yellow-400 bg-yellow-900/30',
  PARABOLIC: 'text-red-400 bg-red-900/30',
  CHOPPY: 'text-gray-400 bg-gray-800',
}

export function SignalCard({ signal, currentCandle = 0 }: Props) {
  const { removeSignal, updateSignal } = useAlertsStore()
  const [skipReason, setSkipReason] = useState('')
  const [showSkipModal, setShowSkipModal] = useState(false)
  const [status, setStatus] = useState<'active' | 'submitted' | 'skipped' | 'expired'>('active')

  const isLong = signal.direction === 'long'
  const directionColor = isLong ? 'text-green-400' : 'text-red-400'
  const directionBg = isLong ? 'bg-green-900/20 border-green-800' : 'bg-red-900/20 border-red-800'

  async function handleConfirm() {
    try {
      const res = await fetch(`/api/signals/${signal.signal_id}/confirm`, { method: 'POST' })
      if (res.ok) {
        setStatus('submitted')
        updateSignal(signal.signal_id, { status: 'Submitted', user_action: 'CONFIRM' })
        setTimeout(() => removeSignal(signal.signal_id), 2000)
      }
    } catch (err) {
      console.error('Confirm failed:', err)
    }
  }

  async function handleSkip() {
    try {
      const res = await fetch(`/api/signals/${signal.signal_id}/skip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: skipReason || null }),
      })
      if (res.ok) {
        setStatus('skipped')
        setShowSkipModal(false)
        removeSignal(signal.signal_id)
      }
    } catch (err) {
      console.error('Skip failed:', err)
    }
  }

  async function handleExpire() {
    setStatus('expired')
    await fetch(`/api/signals/${signal.signal_id}/expire`, { method: 'PATCH' })
    setTimeout(() => removeSignal(signal.signal_id), 1500)
  }

  if (status === 'submitted') {
    return (
      <div className="rounded-xl border border-green-700 bg-green-900/20 p-4 text-center">
        <p className="text-green-400 font-semibold">✓ Order Submitted</p>
        <p className="text-xs text-gray-400 mt-1">{signal.asset} {signal.direction.toUpperCase()}</p>
      </div>
    )
  }

  if (status === 'expired') {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4 text-center opacity-50">
        <p className="text-gray-400 text-sm">Signal expired — {signal.asset}</p>
      </div>
    )
  }

  return (
    <div className={`rounded-xl border p-4 space-y-3 ${directionBg}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-white">{signal.asset}</span>
            <span className={`text-sm font-semibold uppercase ${directionColor}`}>
              {signal.direction}
            </span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${REGIME_COLORS[signal.regime] ?? 'text-gray-400'}`}>
              {signal.regime}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">{signal.strategy_name} · {signal.timeframe}</p>
        </div>
        <CountdownTimer
          expiresAtCandle={signal.expires_at_candle}
          currentCandle={currentCandle}
          onExpire={handleExpire}
        />
      </div>

      {/* Price levels */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="bg-gray-900/50 rounded-lg p-2">
          <p className="text-xs text-gray-500">Entry</p>
          <p className="font-mono font-semibold text-white">${signal.entry_price.toLocaleString()}</p>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-2">
          <p className="text-xs text-gray-500">Stop Loss</p>
          <p className="font-mono font-semibold text-red-400">${signal.stop_loss.toLocaleString()}</p>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-2">
          <p className="text-xs text-gray-500">TP1</p>
          <p className="font-mono font-semibold text-green-400">${signal.take_profit_1.toLocaleString()}</p>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-2">
          <p className="text-xs text-gray-500">TP2</p>
          <p className="font-mono font-semibold text-green-300">${signal.take_profit_2.toLocaleString()}</p>
        </div>
      </div>

      {/* R:R */}
      <div className="flex gap-3 text-xs">
        <span className="text-gray-400">Gross R:R <span className="text-white font-semibold">{signal.gross_rr.toFixed(2)}</span></span>
        <span className="text-gray-400">Net R:R <span className="text-white font-semibold">{signal.net_rr.toFixed(2)}</span></span>
      </div>

      {/* Score breakdown */}
      <ScoreBreakdown breakdown={signal.score_breakdown} finalScore={signal.final_score} />

      {/* Action buttons */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={handleConfirm}
          disabled={status !== 'active'}
          className="flex-1 py-2 rounded-lg bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
        >
          CONFIRM
        </button>
        <button
          onClick={() => setShowSkipModal(true)}
          disabled={status !== 'active'}
          className="flex-1 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-gray-200 font-semibold text-sm transition-colors"
        >
          SKIP
        </button>
      </div>

      {/* Skip modal */}
      {showSkipModal && (
        <div className="mt-2 space-y-2">
          <input
            type="text"
            placeholder="Skip reason (optional)"
            value={skipReason}
            onChange={(e) => setSkipReason(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSkip}
              className="flex-1 py-1.5 rounded-lg bg-gray-600 hover:bg-gray-500 text-white text-sm transition-colors"
            >
              Confirm Skip
            </button>
            <button
              onClick={() => setShowSkipModal(false)}
              className="flex-1 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * CountdownTimer
 * Shows remaining candles before signal expires.
 * Calls onExpire when countdown reaches zero.
 *
 * Satisfies: Requirement 18.1, 18.5
 */
import { useEffect, useState } from 'react'

interface Props {
  expiresAtCandle: number
  currentCandle: number
  timeframeMinutes?: number
  onExpire?: () => void
}

export function CountdownTimer({
  expiresAtCandle,
  currentCandle,
  timeframeMinutes = 15,
  onExpire,
}: Props) {
  const [remaining, setRemaining] = useState(expiresAtCandle - currentCandle)

  useEffect(() => {
    const r = expiresAtCandle - currentCandle
    setRemaining(r)
    if (r <= 0) {
      onExpire?.()
    }
  }, [expiresAtCandle, currentCandle, onExpire])

  const minutes = remaining * timeframeMinutes
  const isUrgent = remaining <= 3

  if (remaining <= 0) {
    return (
      <span className="text-xs font-medium text-red-400 bg-red-900/30 px-2 py-0.5 rounded">
        EXPIRED
      </span>
    )
  }

  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded ${
        isUrgent
          ? 'text-orange-300 bg-orange-900/30 animate-pulse'
          : 'text-gray-400 bg-gray-800'
      }`}
    >
      ⏱ {remaining} candles ({minutes}m)
    </span>
  )
}

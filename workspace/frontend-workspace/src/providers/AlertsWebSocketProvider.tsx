/**
 * AlertsWebSocketProvider
 * Connects to /ws/alerts, parses Signal Cards, stores in Zustand alertsStore.
 * Reconnects with exponential backoff on disconnect.
 *
 * Satisfies: Requirement 18.10
 */
import { useEffect, useRef } from 'react'
import { useAlertsStore } from '../store/alertsStore'
import type { SignalCard } from '../types'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/alerts`
const MAX_BACKOFF_MS = 30_000

export function AlertsWebSocketProvider({ children }: { children: React.ReactNode }) {
  const addSignal = useAlertsStore((s) => s.addSignal)
  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef(1000)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true

    function connect() {
      if (!mountedRef.current) return
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        backoffRef.current = 1000
        console.log('[AlertsWS] connected')
      }

      ws.onmessage = (event) => {
        try {
          const card: SignalCard = JSON.parse(event.data)
          if (card.signal_id) {
            addSignal(card)
          }
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        console.log(`[AlertsWS] disconnected — reconnecting in ${backoffRef.current}ms`)
        setTimeout(connect, backoffRef.current)
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS)
      }

      ws.onerror = (err) => {
        console.error('[AlertsWS] error', err)
        ws.close()
      }
    }

    connect()

    return () => {
      mountedRef.current = false
      wsRef.current?.close()
    }
  }, [addSignal])

  return <>{children}</>
}

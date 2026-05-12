/**
 * PortfolioWebSocketProvider
 * Connects to /ws/portfolio, updates Portfolio_Heat in Zustand portfolioStore.
 *
 * Satisfies: Requirements 14.8, 18.9, 18.10
 */
import { useEffect, useRef } from 'react'
import { usePortfolioStore } from '../store/portfolioStore'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/portfolio`
const MAX_BACKOFF_MS = 30_000

export function PortfolioWebSocketProvider({ children }: { children: React.ReactNode }) {
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio)
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
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setPortfolio(data)
        } catch {
          // ignore
        }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setTimeout(connect, backoffRef.current)
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS)
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      mountedRef.current = false
      wsRef.current?.close()
    }
  }, [setPortfolio])

  return <>{children}</>
}

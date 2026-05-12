/**
 * Monitor API client — all calls go to /api/* on the same origin (:8000).
 * monitor_routes.py in backend-workspace proxies exchange/audit requests
 * to mock-exchange-workspace (:8001) transparently.
 */

import type {
  AccountState,
  ExchangeOrder,
  PaginatedSignalAudit,
  PaginatedTradeAudit,
  PendingOrdersResponse,
  PerformanceReport,
  Position,
  SignalAuditDetail,
  TradeAuditDetail,
  TradeJournalEntry,
} from '../types/monitor'

async function get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
    })
  }
  const r = await fetch(url.toString())
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText)
    throw new Error(`${r.status} ${text}`)
  }
  return r.json()
}

async function del<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  const r = await fetch(url.toString(), { method: 'DELETE' })
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText)
    throw new Error(`${r.status} ${text}`)
  }
  return r.json()
}

// ---------------------------------------------------------------------------
// Account
// ---------------------------------------------------------------------------

export const fetchAccount = () =>
  get<AccountState>('/api/exchange/account')

// ---------------------------------------------------------------------------
// Positions
// ---------------------------------------------------------------------------

export const fetchPositions = () =>
  get<Position[]>('/api/exchange/positions')

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export const fetchOpenOrders = (symbol?: string) =>
  get<ExchangeOrder[]>('/api/exchange/orders', symbol ? { symbol } : undefined)

export const cancelOrder = (orderId: string, symbol: string) =>
  del<{ cancelled: boolean; order_id: string }>(
    `/api/exchange/orders/${orderId}`,
    { symbol },
  )

export const fetchPendingOrders = () =>
  get<PendingOrdersResponse>('/api/orders/pending')

// ---------------------------------------------------------------------------
// Trade Journal (backend-workspace native)
// ---------------------------------------------------------------------------

export const fetchJournal = (page = 1, pageSize = 20, asset?: string) =>
  get<TradeJournalEntry[]>('/api/journal', {
    page,
    page_size: pageSize,
    ...(asset ? { asset } : {}),
  })

// ---------------------------------------------------------------------------
// Audit — Signals
// ---------------------------------------------------------------------------

export const fetchAuditSignals = (params?: {
  page?: number
  limit?: number
  symbol?: string
  result?: string
  regime?: string
}) =>
  get<PaginatedSignalAudit>('/api/audit/signals', {
    page: params?.page ?? 1,
    limit: params?.limit ?? 50,
    ...(params?.symbol ? { symbol: params.symbol } : {}),
    ...(params?.result ? { result: params.result } : {}),
    ...(params?.regime ? { regime: params.regime } : {}),
  })

export const fetchAuditSignalDetail = (id: number) =>
  get<SignalAuditDetail>(`/api/audit/signals/${id}`)

// ---------------------------------------------------------------------------
// Audit — Trades
// ---------------------------------------------------------------------------

export const fetchAuditTrades = (params?: {
  page?: number
  limit?: number
  outcome?: string
  verdict?: string
}) =>
  get<PaginatedTradeAudit>('/api/audit/trades', {
    page: params?.page ?? 1,
    limit: params?.limit ?? 50,
    ...(params?.outcome ? { outcome: params.outcome } : {}),
    ...(params?.verdict ? { verdict: params.verdict } : {}),
  })

export const fetchAuditTradeDetail = (id: number) =>
  get<TradeAuditDetail>(`/api/audit/trades/${id}`)

// ---------------------------------------------------------------------------
// Audit — Analytics
// ---------------------------------------------------------------------------

export const fetchAuditPerformance = () =>
  get<PerformanceReport>('/api/audit/analytics/performance')

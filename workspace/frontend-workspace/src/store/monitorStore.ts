/**
 * Monitor Store — Zustand state for Trade Monitor page.
 * Holds positions, orders, account state. Updated by polling + WS.
 */

import { create } from 'zustand'
import type { AccountState, ExchangeOrder, ExecutionStatus, Position } from '../types/monitor'
import {
  fetchAccount,
  fetchOpenOrders,
  fetchPendingOrders,
  fetchPositions,
} from '../api/monitorApi'

interface MonitorState {
  // Exchange data
  account: AccountState | null
  positions: Position[]
  openOrders: ExchangeOrder[]
  // In-flight Celery executions
  pendingExecutions: ExecutionStatus[]
  // Loading flags
  loadingPositions: boolean
  loadingOrders: boolean
  loadingAccount: boolean
  // Last refresh timestamp
  lastRefreshed: Date | null
  error: string | null

  // Actions
  refreshAll: () => Promise<void>
  refreshPositions: () => Promise<void>
  cancelOrder: (orderId: string, symbol: string) => Promise<void>
  updatePositionFromWS: (positions: Position[]) => void
}

export const useMonitorStore = create<MonitorState>((set, get) => ({
  account: null,
  positions: [],
  openOrders: [],
  pendingExecutions: [],
  loadingPositions: false,
  loadingOrders: false,
  loadingAccount: false,
  lastRefreshed: null,
  error: null,

  refreshAll: async () => {
    set({ error: null })
    await Promise.allSettled([
      get().refreshPositions(),
      (async () => {
        set({ loadingOrders: true })
        try {
          const [ordersRes, pendingRes] = await Promise.all([
            fetchOpenOrders(),
            fetchPendingOrders(),
          ])
          set({
            openOrders: ordersRes,
            pendingExecutions: pendingRes.executions,
            loadingOrders: false,
          })
        } catch {
          set({ loadingOrders: false })
        }
      })(),
      (async () => {
        set({ loadingAccount: true })
        try {
          const account = await fetchAccount()
          set({ account, loadingAccount: false })
        } catch {
          set({ loadingAccount: false })
        }
      })(),
    ])
    set({ lastRefreshed: new Date() })
  },

  refreshPositions: async () => {
    set({ loadingPositions: true })
    try {
      const positions = await fetchPositions()
      set({ positions, loadingPositions: false })
    } catch (e: unknown) {
      set({
        loadingPositions: false,
        error: e instanceof Error ? e.message : 'Failed to load positions',
      })
    }
  },

  cancelOrder: async (orderId: string, symbol: string) => {
    const { cancelOrder: apiCancel } = await import('../api/monitorApi')
    await apiCancel(orderId, symbol)
    // Remove from local state immediately (optimistic)
    set((s) => ({
      openOrders: s.openOrders.filter((o) => o.order_id !== orderId),
    }))
  },

  updatePositionFromWS: (positions: Position[]) => {
    set({ positions, lastRefreshed: new Date() })
  },
}))

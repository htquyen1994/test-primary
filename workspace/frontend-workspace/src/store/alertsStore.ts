import { create } from 'zustand'
import type { SignalCard } from '../types'

interface AlertsState {
  signals: Record<string, SignalCard>
  addSignal: (signal: SignalCard) => void
  removeSignal: (id: string) => void
  updateSignal: (id: string, updates: Partial<SignalCard>) => void
  clearAll: () => void
}

export const useAlertsStore = create<AlertsState>((set) => ({
  signals: {},

  addSignal: (signal) =>
    set((state) => ({
      signals: { ...state.signals, [signal.signal_id]: signal },
    })),

  removeSignal: (id) =>
    set((state) => {
      const { [id]: _, ...rest } = state.signals
      return { signals: rest }
    }),

  updateSignal: (id, updates) =>
    set((state) => ({
      signals: {
        ...state.signals,
        [id]: { ...state.signals[id], ...updates },
      },
    })),

  clearAll: () => set({ signals: {} }),
}))

import { create } from 'zustand'
import type { PortfolioData } from '../types'

interface PortfolioState extends PortfolioData {
  setPortfolio: (data: PortfolioData) => void
}

export const usePortfolioStore = create<PortfolioState>((set) => ({
  portfolio_heat: 0,
  open_positions: {},
  setPortfolio: (data) => set(data),
}))

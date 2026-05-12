// Core types for the trading dashboard

export interface ScoreBreakdown {
  order_flow: number
  smc: number
  vsa: number
  context: number
  bonus: number
}

export interface SignalCard {
  signal_id: string
  strategy_name: string
  asset: string
  timeframe: string
  direction: 'long' | 'short'
  final_score: number
  classification: 'ALERT' | 'WATCH' | 'IGNORE'
  entry_price: number
  stop_loss: number
  take_profit_1: number
  take_profit_2: number
  gross_rr: number
  net_rr: number
  score_breakdown: ScoreBreakdown
  regime: string
  expires_at_candle: number
  created_at: string
  user_action?: string
  status?: string
}

export interface TradeJournalEntry {
  trade_id: string
  strategy_name: string
  asset: string
  direction: string
  entry_timestamp: string
  exit_timestamp?: string
  entry_price: number
  actual_entry_price: number
  actual_exit_price?: number
  stop_loss: number
  take_profit_1: number
  position_size_usd: number
  slippage_entry: number
  fee_entry: number
  fee_exit: number
  gross_pnl?: number
  net_pnl?: number
  result?: 'win' | 'loss' | 'be'
  signal_score: number
  is_testnet: boolean
}

export interface AnalyticsData {
  total_trades: number
  win_rate: number
  profit_factor: number
  max_drawdown: number
  sharpe_ratio: number
  net_profit: number
}

export interface PortfolioData {
  portfolio_heat: number
  open_positions: Record<string, number>
}

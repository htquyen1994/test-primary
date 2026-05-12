/** Types for Trade Monitor page — positions, orders, history, audit. */

// ---------------------------------------------------------------------------
// Exchange — Positions
// ---------------------------------------------------------------------------

export interface Position {
  symbol: string
  direction: 'long' | 'short'
  entry_price: number
  amount: number
  leverage: number
  stop_loss: number
  take_profit_1: number
  take_profit_2: number | null
  current_price: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  opened_at: string
  signal_id: string | null
}

// ---------------------------------------------------------------------------
// Exchange — Orders
// ---------------------------------------------------------------------------

export type OrderStatus =
  | 'PENDING'
  | 'OPEN'
  | 'FILLED'
  | 'PARTIAL'
  | 'CANCELLED'
  | 'REJECTED'
  | 'EXPIRED'

export type OrderType = 'market' | 'limit' | 'stop_loss' | 'take_profit'

export interface ExchangeOrder {
  order_id: string
  symbol: string
  side: 'buy' | 'sell'
  order_type: OrderType
  amount: number
  price: number
  status: OrderStatus
  filled_amount: number
  fill_price: number | null
  fee: number
  created_at: string
  filled_at: string | null
  client_order_id: string | null
}

// ---------------------------------------------------------------------------
// Pending — in-flight Celery executions
// ---------------------------------------------------------------------------

export interface ExecutionStatus {
  signal_id: string
  asset?: string
  symbol?: string
  direction?: string
  status: 'Executing' | 'Submitted' | 'Filled' | 'Failed' | 'Rejected'
  position_size_usd?: number
  fill_price?: number
  error?: string
  dispatched_at?: string
}

export interface PendingOrdersResponse {
  executions: ExecutionStatus[]
  exchange_orders: ExchangeOrder[]
}

// ---------------------------------------------------------------------------
// Exchange — Account
// ---------------------------------------------------------------------------

export interface AccountState {
  balance_usd: number
  equity_usd: number
  used_margin: number
  total_realized_pnl: number
  total_fees_paid: number
  updated_at: string
}

// ---------------------------------------------------------------------------
// Trade Journal (from backend-workspace /api/journal)
// ---------------------------------------------------------------------------

export interface TradeJournalEntry {
  trade_id: string
  strategy_name: string
  asset: string
  direction: 'long' | 'short'
  entry_timestamp: string
  exit_timestamp: string | null
  entry_price: number
  actual_entry_price: number
  actual_exit_price: number | null
  stop_loss: number
  take_profit_1: number
  position_size_usd: number
  slippage_entry: number
  fee_entry: number
  fee_exit: number
  gross_pnl: number | null
  net_pnl: number | null
  result: 'win' | 'loss' | 'be' | null
  signal_score: number
  is_testnet: boolean
}

// ---------------------------------------------------------------------------
// Audit — Signals (from mock-exchange-workspace /audit/signals)
// ---------------------------------------------------------------------------

export interface SignalAuditItem {
  id: number
  signal_id: string | null
  symbol: string
  timeframe: string
  timestamp_candle_close: string
  signal_result: 'SIGNAL' | 'NO_SIGNAL'
  final_score: number
  regime: string
  mtf_scenario: string | null
  blocking_reason: string | null
  audit_status: string
  created_at: string
}

export interface SignalAuditDetail extends SignalAuditItem {
  score_breakdown: Record<string, number> | null
  regime_multiplier: number | null
  mtf_4h_bias: string | null
  daily_bias: string | null
  btc_guard_active: boolean
  circuit_breaker_locked: boolean
  blocking_detail: string | null
  entry_price_proposed: number | null
  sl_proposed: number | null
  tp1_proposed: number | null
  tp2_proposed: number | null
  atr_value: number | null
  adx_value: number | null
  delta_value: number | null
  delta_threshold: number | null
  funding_rate: number | null
  ob_available: boolean
  // Post-hoc price outcome
  price_at_T1: number | null
  price_at_T4: number | null
  price_at_T16: number | null
  max_favorable_excursion: number | null
  max_adverse_excursion: number | null
  would_have_hit_sl: boolean | null
  would_have_hit_tp1: boolean | null
  would_have_hit_tp2: boolean | null
}

export interface PaginatedSignalAudit {
  total: number
  page: number
  limit: number
  items: SignalAuditItem[]
}

// ---------------------------------------------------------------------------
// Audit — Trades (from mock-exchange-workspace /audit/trades)
// ---------------------------------------------------------------------------

export type TradeOutcome = 'WIN' | 'LOSS' | 'BREAKEVEN'
export type SignalVerdict = 'GOOD_SIGNAL' | 'BAD_SIGNAL' | 'ACCEPTABLE'

export interface TradeAuditItem {
  id: number
  trade_id: string
  signal_audit_id: number | null
  outcome: TradeOutcome | null
  exit_price: number | null
  exit_timestamp: string | null
  hold_duration_minutes: number | null
  net_pnl: number | null
  pnl_pct: number | null
  signal_quality_verdict: SignalVerdict | null
  audit_status: string
}

export interface TradeAuditDetail extends TradeAuditItem {
  entry_price_proposed: number | null
  entry_price_actual: number | null
  sl_proposed: number | null
  sl_actual: number | null
  tp1_proposed: number | null
  tp1_actual: number | null
  gross_pnl: number | null
  sl_hit_reason: string | null
  audit_notes: string | null
  analyzed_at: string | null
}

export interface PaginatedTradeAudit {
  total: number
  page: number
  limit: number
  items: TradeAuditItem[]
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface PerformanceReport {
  total_signals: number
  total_trades: number
  win_rate: number
  profit_factor: number
  max_drawdown: number
  avg_hold_minutes: number
  best_trade_pnl: number
  worst_trade_pnl: number
  total_net_pnl: number
  total_fees_paid: number
}

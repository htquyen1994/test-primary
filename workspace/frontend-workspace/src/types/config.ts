// Config management types

export interface TradingParams {
  id?: string
  version_tag?: string
  version_note?: string
  is_active?: boolean
  created_at?: string

  // Signal Scoring
  score_alert_threshold: number
  score_watch_threshold: number
  order_flow_max_pts: number
  smc_max_pts: number
  vsa_max_pts: number
  context_max_pts: number
  confluence_bonus_max_pts: number

  // Regime Detection
  adx_trending_threshold: number
  adx_choppy_threshold: number
  atr_parabolic_multiplier: number
  parabolic_score_multiplier: number
  ranging_score_multiplier: number
  trending_score_multiplier: number

  // Timeframes
  trigger_timeframe: string
  context_timeframe: string
  time_invalidation_candles: number

  // Strategy thresholds
  ob_atr_multiplier: number
  pinbar_tail_ratio: number
  tp1_rr_ratio: number
  tp2_rr_ratio: number

  // Risk
  correlation_threshold: number
  max_correlated_risk_pct: number
  portfolio_heat_limit_pct: number
  max_concurrent_positions: number
  max_daily_loss_pct: number
}

export interface AssetConfig {
  symbol: string
  enabled: boolean
  leverage?: number | null
}

export interface ExchangeSettings {
  id?: string
  profile_name: string
  exchange_id: string
  market_type: 'futures' | 'spot'
  testnet: boolean
  api_key: string
  api_secret: string
  passphrase: string
  account_balance_usd: number
  account_currency: string
  sizing_mode: 'fixed_usd' | 'risk_pct' | 'kelly'
  fixed_usd_per_trade: number
  risk_pct_per_trade: number
  default_leverage: number
  fee_rate: number
  slippage_pct: number
  assets: AssetConfig[]
}

export interface SupportedExchange {
  id: string
  name: string
  futures: boolean
  spot: boolean
  testnet: boolean
  needs_passphrase?: boolean
}

export interface ParamsVersionHistory {
  id: string
  version_tag: string
  version_note?: string
  is_active: boolean
  created_at: string
  activated_at?: string
}

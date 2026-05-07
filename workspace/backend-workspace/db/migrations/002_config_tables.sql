-- Migration 002: Config Management Tables

IF OBJECT_ID('dbo.trading_params', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.trading_params (
        id                              NVARCHAR(36)  NOT NULL CONSTRAINT pk_trading_params PRIMARY KEY DEFAULT NEWID(),
        version_tag                     NVARCHAR(50)  NOT NULL,
        version_note                    NVARCHAR(500) NULL,
        is_active                       BIT           NOT NULL DEFAULT 0,
        created_at                      DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        activated_at                    DATETIME2     NULL,
        score_alert_threshold           INT           NOT NULL DEFAULT 75,
        score_watch_threshold           INT           NOT NULL DEFAULT 55,
        order_flow_max_pts              INT           NOT NULL DEFAULT 35,
        smc_max_pts                     INT           NOT NULL DEFAULT 30,
        vsa_max_pts                     INT           NOT NULL DEFAULT 30,
        context_max_pts                 INT           NOT NULL DEFAULT 15,
        confluence_bonus_max_pts        INT           NOT NULL DEFAULT 15,
        adx_trending_threshold          FLOAT         NOT NULL DEFAULT 25.0,
        adx_choppy_threshold            FLOAT         NOT NULL DEFAULT 20.0,
        atr_parabolic_multiplier        FLOAT         NOT NULL DEFAULT 3.0,
        atr_parabolic_rolling_window    INT           NOT NULL DEFAULT 20,
        parabolic_score_multiplier      FLOAT         NOT NULL DEFAULT 0.6,
        ranging_score_multiplier        FLOAT         NOT NULL DEFAULT 0.85,
        trending_score_multiplier       FLOAT         NOT NULL DEFAULT 1.0,
        trigger_timeframe               NVARCHAR(5)   NOT NULL DEFAULT '15m',
        context_timeframe               NVARCHAR(5)   NOT NULL DEFAULT '1h',
        entry_timeframe                 NVARCHAR(5)   NOT NULL DEFAULT '5m',
        time_invalidation_candles       INT           NOT NULL DEFAULT 15,
        ob_atr_multiplier               FLOAT         NOT NULL DEFAULT 1.5,
        fvg_touch_tolerance_pct         FLOAT         NOT NULL DEFAULT 0.001,
        ob_retest_tolerance_pct         FLOAT         NOT NULL DEFAULT 0.002,
        pinbar_tail_ratio               FLOAT         NOT NULL DEFAULT 2.0,
        pinbar_body_position_long       FLOAT         NOT NULL DEFAULT 0.70,
        pinbar_body_position_short      FLOAT         NOT NULL DEFAULT 0.30,
        no_supply_vol_ratio             FLOAT         NOT NULL DEFAULT 0.40,
        effort_result_vol_ratio         FLOAT         NOT NULL DEFAULT 0.50,
        poc_tolerance_pct               FLOAT         NOT NULL DEFAULT 0.003,
        swing_lookback                  INT           NOT NULL DEFAULT 20,
        fibonacci_lookback              INT           NOT NULL DEFAULT 50,
        correlation_threshold           FLOAT         NOT NULL DEFAULT 0.8,
        max_correlated_risk_pct         FLOAT         NOT NULL DEFAULT 3.0,
        portfolio_heat_limit_pct        FLOAT         NOT NULL DEFAULT 6.0,
        atr_sl_multiplier               FLOAT         NOT NULL DEFAULT 1.5,
        tp1_rr_ratio                    FLOAT         NOT NULL DEFAULT 1.5,
        tp2_rr_ratio                    FLOAT         NOT NULL DEFAULT 2.5,
        max_concurrent_positions        INT           NOT NULL DEFAULT 3,
        max_daily_loss_pct              FLOAT         NOT NULL DEFAULT 5.0,
        min_trades_threshold            INT           NOT NULL DEFAULT 30,
        overfit_degradation_threshold   FLOAT         NOT NULL DEFAULT 0.20
    )
END

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_trading_params_active' AND object_id = OBJECT_ID('dbo.trading_params'))
    CREATE INDEX idx_trading_params_active ON dbo.trading_params (is_active, created_at)

IF NOT EXISTS (SELECT 1 FROM dbo.trading_params)
    INSERT INTO dbo.trading_params (version_tag, version_note, is_active, activated_at)
    VALUES ('v1.0', 'Initial default parameters', 1, GETUTCDATE())

IF OBJECT_ID('dbo.exchange_settings', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.exchange_settings (
        id                      NVARCHAR(36)  NOT NULL CONSTRAINT pk_exchange_settings PRIMARY KEY DEFAULT NEWID(),
        profile_name            NVARCHAR(100) NOT NULL DEFAULT 'default',
        is_active               BIT           NOT NULL DEFAULT 0,
        created_at              DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        updated_at              DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        exchange_id             NVARCHAR(50)  NOT NULL DEFAULT 'binance',
        market_type             NVARCHAR(10)  NOT NULL DEFAULT 'futures',
        testnet                 BIT           NOT NULL DEFAULT 1,
        api_key_encrypted       NVARCHAR(MAX) NULL,
        api_secret_encrypted    NVARCHAR(MAX) NULL,
        passphrase_encrypted    NVARCHAR(MAX) NULL,
        account_balance_usd     FLOAT         NOT NULL DEFAULT 10000.0,
        account_currency        NVARCHAR(10)  NOT NULL DEFAULT 'USDT',
        sizing_mode             NVARCHAR(20)  NOT NULL DEFAULT 'risk_pct',
        fixed_usd_per_trade     FLOAT         NOT NULL DEFAULT 100.0,
        risk_pct_per_trade      FLOAT         NOT NULL DEFAULT 0.02,
        default_leverage        INT           NOT NULL DEFAULT 5,
        fee_rate                FLOAT         NOT NULL DEFAULT 0.001,
        slippage_pct            FLOAT         NOT NULL DEFAULT 0.0002
    )
END

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_exchange_settings_active' AND object_id = OBJECT_ID('dbo.exchange_settings'))
    CREATE INDEX idx_exchange_settings_active ON dbo.exchange_settings (is_active)

IF NOT EXISTS (SELECT 1 FROM dbo.exchange_settings)
    INSERT INTO dbo.exchange_settings (profile_name, is_active)
    VALUES ('default', 1)

IF OBJECT_ID('dbo.exchange_assets', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.exchange_assets (
        id                      NVARCHAR(36)  NOT NULL CONSTRAINT pk_exchange_assets PRIMARY KEY DEFAULT NEWID(),
        exchange_settings_id    NVARCHAR(36)  NOT NULL,
        symbol                  NVARCHAR(30)  NOT NULL,
        enabled                 BIT           NOT NULL DEFAULT 1,
        leverage_override       INT           NULL,
        created_at              DATETIME2     NOT NULL DEFAULT GETUTCDATE()
    )
END

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_exchange_assets_settings' AND object_id = OBJECT_ID('dbo.exchange_assets'))
    CREATE INDEX idx_exchange_assets_settings ON dbo.exchange_assets (exchange_settings_id, enabled)

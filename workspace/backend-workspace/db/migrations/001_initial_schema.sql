-- =============================================================================
-- Migration 001: Initial Schema — Microsoft SQL Server 2019+
-- Run via: python db/init_db.py
-- =============================================================================

-- signal_log
-- Records every generated Signal regardless of classification or user action.
-- Satisfies: Requirements 17.1, 17.2, 17.7
IF OBJECT_ID('dbo.signal_log', 'U') IS NULL
    CREATE TABLE dbo.signal_log (
        log_id                  NVARCHAR(36)    NOT NULL CONSTRAINT pk_signal_log PRIMARY KEY DEFAULT NEWID(),
        timestamp               DATETIME2       NOT NULL,
        asset                   NVARCHAR(20)    NOT NULL,
        timeframe               NVARCHAR(5)     NOT NULL,
        strategy_name           NVARCHAR(100)   NOT NULL,
        direction               NVARCHAR(5)     NOT NULL CONSTRAINT chk_sl_direction CHECK (direction IN ('long', 'short')),
        candle_index            BIGINT          NOT NULL,
        entry_price             FLOAT           NULL,
        stop_loss               FLOAT           NULL,
        take_profit_1           FLOAT           NULL,
        take_profit_2           FLOAT           NULL,
        raw_score               FLOAT           NOT NULL,
        final_score             INT             NOT NULL CONSTRAINT chk_sl_final_score CHECK (final_score BETWEEN 0 AND 100),
        score_order_flow        FLOAT           NOT NULL DEFAULT 0,
        score_smc               FLOAT           NOT NULL DEFAULT 0,
        score_vsa               FLOAT           NOT NULL DEFAULT 0,
        score_context           FLOAT           NOT NULL DEFAULT 0,
        score_bonus             FLOAT           NOT NULL DEFAULT 0,
        regime                  NVARCHAR(20)    NOT NULL CONSTRAINT chk_sl_regime CHECK (regime IN ('TRENDING', 'RANGING', 'PARABOLIC', 'CHOPPY')),
        regime_multiplier       FLOAT           NOT NULL,
        funding_rate            FLOAT           NOT NULL DEFAULT 0,
        portfolio_heat          FLOAT           NOT NULL DEFAULT 0,
        correlated_group_risk   FLOAT           NOT NULL DEFAULT 0,
        classification          NVARCHAR(10)    NOT NULL CONSTRAINT chk_sl_classification CHECK (classification IN ('ALERT', 'WATCH', 'IGNORE')),
        user_action             NVARCHAR(10)    NULL CONSTRAINT chk_sl_user_action CHECK (user_action IN ('CONFIRM', 'SKIP', 'EXPIRED', 'IGNORE')),
        skip_reason             NVARCHAR(MAX)   NULL,
        expiry_price            FLOAT           NULL,
        expires_at_candle       BIGINT          NOT NULL,
        created_at              DATETIME2       NOT NULL DEFAULT GETUTCDATE()
    )

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_signal_log_asset_ts' AND object_id = OBJECT_ID('dbo.signal_log'))
    CREATE INDEX idx_signal_log_asset_ts ON dbo.signal_log (asset, timestamp)

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_signal_log_classification' AND object_id = OBJECT_ID('dbo.signal_log'))
    CREATE INDEX idx_signal_log_classification ON dbo.signal_log (classification)

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_signal_log_strategy' AND object_id = OBJECT_ID('dbo.signal_log'))
    CREATE INDEX idx_signal_log_strategy ON dbo.signal_log (strategy_name)

-- trade_journal
-- Persistent log of all confirmed trades with actual fill prices and PnL.
-- Satisfies: Requirements 17, 18.7, 19.5, 19.6, 19.10
IF OBJECT_ID('dbo.trade_journal', 'U') IS NULL
    CREATE TABLE dbo.trade_journal (
        trade_id            NVARCHAR(36)    NOT NULL CONSTRAINT pk_trade_journal PRIMARY KEY DEFAULT NEWID(),
        signal_log_id       NVARCHAR(36)    NULL,
        strategy_name       NVARCHAR(100)   NOT NULL,
        asset               NVARCHAR(20)    NOT NULL,
        timeframe           NVARCHAR(5)     NOT NULL,
        direction           NVARCHAR(5)     NOT NULL CONSTRAINT chk_tj_direction CHECK (direction IN ('long', 'short')),
        entry_timestamp     DATETIME2       NOT NULL,
        exit_timestamp      DATETIME2       NULL,
        entry_price         FLOAT           NOT NULL,
        exit_price          FLOAT           NULL,
        actual_entry_price  FLOAT           NOT NULL,
        actual_exit_price   FLOAT           NULL,
        stop_loss           FLOAT           NOT NULL,
        take_profit_1       FLOAT           NOT NULL,
        take_profit_2       FLOAT           NULL,
        position_size_usd   FLOAT           NOT NULL,
        leverage            INT             NOT NULL DEFAULT 1,
        slippage_entry      FLOAT           NOT NULL DEFAULT 0,
        slippage_exit       FLOAT           NOT NULL DEFAULT 0,
        fee_entry           FLOAT           NOT NULL DEFAULT 0,
        fee_exit            FLOAT           NOT NULL DEFAULT 0,
        funding_paid        FLOAT           NOT NULL DEFAULT 0,
        gross_pnl           FLOAT           NULL,
        net_pnl             FLOAT           NULL,
        result              NVARCHAR(4)     NULL CONSTRAINT chk_tj_result CHECK (result IN ('win', 'loss', 'be')),
        signal_score        INT             NOT NULL CONSTRAINT chk_tj_signal_score CHECK (signal_score BETWEEN 0 AND 100),
        exchange_order_id   NVARCHAR(100)   NULL,
        is_testnet          BIT             NOT NULL DEFAULT 1,
        created_at          DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
        updated_at          DATETIME2       NOT NULL DEFAULT GETUTCDATE()
    )

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_trade_journal_asset' AND object_id = OBJECT_ID('dbo.trade_journal'))
    CREATE INDEX idx_trade_journal_asset ON dbo.trade_journal (asset)

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_trade_journal_strategy' AND object_id = OBJECT_ID('dbo.trade_journal'))
    CREATE INDEX idx_trade_journal_strategy ON dbo.trade_journal (strategy_name)

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_trade_journal_entry_ts' AND object_id = OBJECT_ID('dbo.trade_journal'))
    CREATE INDEX idx_trade_journal_entry_ts ON dbo.trade_journal (entry_timestamp)

-- backtest_results
-- One row per backtest run; includes walk-forward metadata.
-- Satisfies: Requirements 9, 10, 11
IF OBJECT_ID('dbo.backtest_results', 'U') IS NULL
    CREATE TABLE dbo.backtest_results (
        run_id              NVARCHAR(36)    NOT NULL CONSTRAINT pk_backtest_results PRIMARY KEY DEFAULT NEWID(),
        strategy_name       NVARCHAR(100)   NOT NULL,
        asset               NVARCHAR(20)    NOT NULL,
        timeframe           NVARCHAR(5)     NOT NULL,
        start_date          DATE            NOT NULL,
        end_date            DATE            NOT NULL,
        win_rate            FLOAT           NULL,
        profit_factor       FLOAT           NULL,
        max_drawdown        FLOAT           NULL,
        sharpe_ratio        FLOAT           NULL,
        recovery_factor     FLOAT           NULL,
        total_trades        INT             NULL,
        winning_trades      INT             NULL,
        losing_trades       INT             NULL,
        is_walk_forward     BIT             NOT NULL DEFAULT 0,
        wf_window_index     INT             NULL,
        is_in_sample        BIT             NULL,
        is_statistically_insufficient BIT  NOT NULL DEFAULT 0,
        config_snapshot     NVARCHAR(MAX)   NOT NULL,
        completed_at        DATETIME2       NOT NULL DEFAULT GETUTCDATE()
    )

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_backtest_results_strategy' AND object_id = OBJECT_ID('dbo.backtest_results'))
    CREATE INDEX idx_backtest_results_strategy ON dbo.backtest_results (strategy_name, asset, timeframe)

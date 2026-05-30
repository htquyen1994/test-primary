-- Migration 006: Score weight multipliers & tuning metadata in trading_params
-- Each weight is a multiplier (default 1.0).  Re-normalization ensures scale stays 0-100.
-- tuning_* columns provide audit trail for automated tuning runs.

IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'weight_of')
    ALTER TABLE dbo.trading_params ADD weight_of FLOAT NOT NULL DEFAULT 1.0
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'weight_smc')
    ALTER TABLE dbo.trading_params ADD weight_smc FLOAT NOT NULL DEFAULT 1.0
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'weight_vsa')
    ALTER TABLE dbo.trading_params ADD weight_vsa FLOAT NOT NULL DEFAULT 1.0
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'weight_ctx')
    ALTER TABLE dbo.trading_params ADD weight_ctx FLOAT NOT NULL DEFAULT 1.0
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'weight_bonus')
    ALTER TABLE dbo.trading_params ADD weight_bonus FLOAT NOT NULL DEFAULT 1.0
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'tuning_win_rate')
    ALTER TABLE dbo.trading_params ADD tuning_win_rate FLOAT NULL
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'tuning_sample_size')
    ALTER TABLE dbo.trading_params ADD tuning_sample_size INT NULL
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'tuning_date')
    ALTER TABLE dbo.trading_params ADD tuning_date DATETIME2 NULL
GO
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'tuning_auc_roc')
    ALTER TABLE dbo.trading_params ADD tuning_auc_roc FLOAT NULL
GO

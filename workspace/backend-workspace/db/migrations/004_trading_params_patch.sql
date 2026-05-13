-- =============================================================================
-- Migration 004: trading_params patch — Microsoft SQL Server 2019+
-- Fixes:
--   1. Add missing column min_net_rr (in ORM but absent from migration 002)
--   2. Correct existing active row: tp1_rr_ratio 1.5→2.0, tp2_rr_ratio 2.5→3.0
-- Run via: python db/init_db.py
-- =============================================================================

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.trading_params') AND name = 'min_net_rr'
)
    ALTER TABLE dbo.trading_params ADD min_net_rr FLOAT NOT NULL DEFAULT 1.5

UPDATE dbo.trading_params
    SET tp1_rr_ratio = 2.0, tp2_rr_ratio = 3.0, min_net_rr = 1.5
    WHERE is_active = 1

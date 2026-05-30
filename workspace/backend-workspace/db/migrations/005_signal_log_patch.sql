-- Migration 005: Patch signal_log table
-- Adds block_reason column for filter pipeline analysis
-- Run: python db/init_db.py (idempotent)

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.signal_log')
      AND name = 'block_reason'
)
    ALTER TABLE dbo.signal_log ADD block_reason VARCHAR(120) NULL

GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.signal_log')
      AND name = 'mtf_scenario'
)
    ALTER TABLE dbo.signal_log ADD mtf_scenario VARCHAR(2) NULL

GO

IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.signal_log')
      AND name = 'size_multiplier'
)
    ALTER TABLE dbo.signal_log ADD size_multiplier FLOAT NULL

GO

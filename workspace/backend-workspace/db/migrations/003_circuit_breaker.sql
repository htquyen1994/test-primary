-- =============================================================================
-- Migration 003: Circuit Breaker State Table — Microsoft SQL Server 2019+
-- Task 32.1 — Enhanced Circuit Breaker with 4 triggers + smart unlock
-- Run via: python db/init_db.py
-- =============================================================================

IF OBJECT_ID('dbo.circuit_breaker_state', 'U') IS NULL
    CREATE TABLE dbo.circuit_breaker_state (
        id                      INT             IDENTITY(1,1)   NOT NULL CONSTRAINT pk_circuit_breaker_state PRIMARY KEY,
        triggered_at            DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
        unlock_at               DATETIME2       NOT NULL,
        trigger_type            NVARCHAR(50)    NOT NULL,
            -- 'CONSECUTIVE_LOSSES' | 'LOSS_MAGNITUDE' | 'DAILY_LOSS_CAP' | 'DRAWDOWN_FROM_PEAK'
        trigger_detail          NVARCHAR(500)   NULL,
            -- Human-readable: "3 consecutive losses: -2.1%, -3.5%, -4.2%"
        regime_at_trigger       NVARCHAR(20)    NOT NULL DEFAULT 'UNKNOWN',
            -- Regime when triggered: TRENDING | CHOPPY | RANGING | PARABOLIC
        is_locked               BIT             NOT NULL DEFAULT 1,
        unlock_requires_review  BIT             NOT NULL DEFAULT 0,
            -- 1 for Trigger 4 (drawdown from peak) — requires manual review note
        review_note             NVARCHAR(1000)  NULL,
            -- User-provided review note when manually unlocking (Trigger 4)
        unlocked_at             DATETIME2       NULL,
        unlocked_by             NVARCHAR(100)   NULL,
            -- 'auto_regime_change' | 'manual_user' | 'timer_expired'
        created_at              DATETIME2       NOT NULL DEFAULT GETUTCDATE()
    )

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_cb_is_locked' AND object_id = OBJECT_ID('dbo.circuit_breaker_state'))
    CREATE INDEX idx_cb_is_locked ON dbo.circuit_breaker_state (is_locked, unlock_at)

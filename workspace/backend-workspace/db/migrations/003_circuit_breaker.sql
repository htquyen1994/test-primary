-- Migration 003: Circuit Breaker State Table
-- Task 32.1 — Enhanced Circuit Breaker with 4 triggers

CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    triggered_at          DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    unlock_at             DATETIME2 NOT NULL,
    trigger_type          NVARCHAR(50) NOT NULL,
        -- 'CONSECUTIVE_LOSSES' | 'LOSS_MAGNITUDE' | 'DAILY_LOSS_CAP' | 'DRAWDOWN_FROM_PEAK'
    trigger_detail        NVARCHAR(500) NULL,
        -- Human-readable description: "3 consecutive losses in 24h"
    regime_at_trigger     NVARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
        -- Regime when triggered: TRENDING | CHOPPY | RANGING | PARABOLIC
    is_locked             BIT NOT NULL DEFAULT 1,
    unlock_requires_review BIT NOT NULL DEFAULT 0,
        -- True for Trigger 4 (drawdown from peak) — requires manual review note
    review_note           NVARCHAR(1000) NULL,
        -- User-provided review note when manually unlocking
    unlocked_at           DATETIME2 NULL,
    unlocked_by           NVARCHAR(100) NULL,
        -- 'auto_regime_change' | 'manual_user' | 'timer_expired'
    created_at            DATETIME2 NOT NULL DEFAULT GETUTCDATE()
);

-- Index for fast lock status queries
CREATE INDEX IF NOT EXISTS idx_cb_is_locked ON circuit_breaker_state (is_locked, unlock_at);

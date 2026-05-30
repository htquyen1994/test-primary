# Threshold Optimization Report — 2026-05-30
> Generated: 2026-05-30 16:17 UTC  
> Sample: **200 labeled signals** (WIN=104, LOSS=96)  
> Overall win rate: **52.0%**

## Executive Summary

6 change(s) recommended based on N=200 signals (win_rate=52.0%, current_EV=+2.735, optimal_EV=+1.943, AUC 0.577→0.615).

**6 recommendation(s):**

- [HIGH] **score_alert_threshold**: 75.0 ↓ 72.0 (effect=-0.792)
- [LOW] **weight_of**: 1.0 ↑ 2.5 (effect=+0.038)
- [LOW] **weight_smc**: 1.0 ↑ 2.88 (effect=+0.038)
- [LOW] **weight_vsa**: 1.0 ↓ 0.88 (effect=+0.038)
- [LOW] **weight_ctx**: 1.0 ↓ 0.38 (effect=+0.038)
- [LOW] **weight_bonus**: 1.0 ↓ 0.25 (effect=+0.038)

---
## 1. Threshold Analysis

**Current threshold (T=75):**
- Alerts generated: 2 | Precision: 100.0% | Recall: 1.9% | EV: +2.735

**Optimal threshold (T=72):**
- Alerts generated: 6 | Precision: 83.3% | Recall: 4.8% | EV: +1.943 [CI +0.866 – +2.680]

### Win Rate by Score Bucket

| Score Range | N | Win Rate | Avg R:R | EV/trade |
|------------|--:|--------:|-------:|--------:|
| 55-59 | 16 | 62.5% | 2.18 | +0.987 |
| 60-64 | 12 | 50.0% | 2.22 | +0.608 |
| 65-69 | 8 | 87.5% | 1.80 | +1.454 |
| 70-74 | 9 | 55.6% | 2.32 | +0.847 |
| 75-79 | 1 | 100.0% | 2.59 | +2.592 | ◀ current
| 80-84 | 1 | 100.0% | 2.88 | +2.879 |

### EV Curve (valid thresholds only)

| T | N | Precision | Recall | F1 | EV | EV CI |
|--:|--:|---------:|------:|---:|---:|------|
| 50 | 74 | 56.8% | 40.4% | 0.472 | +0.803 | [+0.491, +1.114] |
| 55 | 47 | 63.8% | 28.8% | 0.397 | +1.017 | [+0.649, +1.374] |
| 60 | 31 | 64.5% | 19.2% | 0.296 | +1.033 | [+0.570, +1.472] |
| 65 | 19 | 73.7% | 13.5% | 0.228 | +1.301 | [+0.715, +1.841] |
| 70 | 11 | 63.6% | 6.7% | 0.122 | +1.190 | [+0.302, +1.966] |
| 72 | 6 | 83.3% | 4.8% | 0.091 | +1.943 | [+0.866, +2.680] | ◀ optimal

---
## 2. Module Predictiveness

### Module Importance Ranking

| Rank | Module | AUC-ROC | Correlation | Cohen's d | p-value | Mean(WIN) | Mean(LOSS) | Predictive? |
|-----:|-------|-------:|----------:|--------:|-------:|--------:|----------:|------------|
| 1 | **OF** | 0.598 | +0.163 | +0.329 | 0.992 | 19.1 | 15.8 | ✗ No |
| 2 | **SMC** | 0.583 | +0.139 | +0.280 | 0.978 | 15.9 | 13.6 | ✗ No |
| 3 | **BONUS** | 0.456 | -0.077 | -0.153 | 0.139 | 7.3 | 8.0 | ✗ No |
| 4 | **VSA** | 0.526 | +0.046 | +0.091 | 0.739 | 15.2 | 14.4 | ✗ No |
| 5 | **CTX** | 0.496 | -0.011 | -0.023 | 0.460 | 7.3 | 7.4 | ✗ No |

### Weight Optimization Result

- Baseline AUC (all weights = 1.0): **0.5773**
- Optimized AUC: **0.6150** (Δ +0.0377)
- Converged: True (iterations: 2)
- Sample used: N=200

**Proposed weight multipliers:**

| Module | Current | Proposed | Direction |
|--------|--------:|---------:|----------|
| OF | 1.00 | 2.50 | ↑ increase |
| SMC | 1.00 | 2.88 | ↑ increase |
| VSA | 1.00 | 0.88 | ↓ decrease |
| CTX | 1.00 | 0.38 | ↓ decrease |
| BONUS | 1.00 | 0.25 | ↓ decrease |

---
## 3. Regime Analysis

| Regime | N | Win Rate | Avg Score | Avg MAE% | Avg MFE% | Recommendation |
|--------|--:|--------:|--------:|---------:|---------:|---------------|
| CHOPPY | 76 | 56.6% | 43 | 0.31% | 0.96% | **KEEP** |
| PARABOLIC | 20 | 50.0% | 29 | 0.29% | 0.93% | **KEEP** |
| TRENDING | 104 | 49.0% | 49 | 0.30% | 0.94% | **KEEP** |

---
## 4. Recommendations

### Rec 1: `score_alert_threshold` (threshold)
🟢 **Confidence: HIGH** | Effect size: -0.7921 | Sample: N=200

- Current value: `75.0`
- Proposed value: `72.0`
- Reason: Optimal threshold for max EV is 72. At T=72: win_rate=83.3%, EV=+1.943 vs current EV=+2.735 (Δ=-0.792 per trade, N=6 signals above).

### Rec 2: `weight_of` (weight)
🔴 **Confidence: LOW** | Effect size: +0.0377 | Sample: N=200

- Current value: `1.0`
- Proposed value: `2.5`
- Reason: Increase weight for OF module (1.00 → 2.50). Module has marginal predictive value (AUC=0.598, r=+0.163, p=0.992). Overall AUC improvement: +0.038.

### Rec 3: `weight_smc` (weight)
🔴 **Confidence: LOW** | Effect size: +0.0377 | Sample: N=200

- Current value: `1.0`
- Proposed value: `2.88`
- Reason: Increase weight for SMC module (1.00 → 2.88). Module has marginal predictive value (AUC=0.583, r=+0.139, p=0.978). Overall AUC improvement: +0.038.

### Rec 4: `weight_vsa` (weight)
🔴 **Confidence: LOW** | Effect size: +0.0377 | Sample: N=200

- Current value: `1.0`
- Proposed value: `0.88`
- Reason: Decrease weight for VSA module (1.00 → 0.88). Module has marginal predictive value (AUC=0.526, r=+0.046, p=0.739). Overall AUC improvement: +0.038.

### Rec 5: `weight_ctx` (weight)
🔴 **Confidence: LOW** | Effect size: +0.0377 | Sample: N=200

- Current value: `1.0`
- Proposed value: `0.38`
- Reason: Decrease weight for CTX module (1.00 → 0.38). Module has marginal predictive value (AUC=0.496, r=-0.011, p=0.460). Overall AUC improvement: +0.038.

### Rec 6: `weight_bonus` (weight)
🔴 **Confidence: LOW** | Effect size: +0.0377 | Sample: N=200

- Current value: `1.0`
- Proposed value: `0.25`
- Reason: Decrease weight for BONUS module (1.00 → 0.25). Module has marginal predictive value (AUC=0.456, r=-0.077, p=0.139). Overall AUC improvement: +0.038.


---
## 6. How to Apply

```bash
# Dry-run (default — shows what would change, no DB write)
python threshold_optimizer.py --step=all

# Apply recommendations to DB
python threshold_optimizer.py --step=all --apply

# Apply only threshold change
python threshold_optimizer.py --step=apply --apply
```

> After applying, **restart the pipeline** (`python main.py`) to pick up
> the new weights and thresholds from DB.

---
*Report generated by threshold_optimizer.py — 2026-05-30 16:17 UTC*
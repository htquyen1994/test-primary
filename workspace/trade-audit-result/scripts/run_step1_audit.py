"""
Master Audit — Step 1: Daily Signal Log Audit
Reads from SQL Server signal_log and prints summary.
Run: python run_step1_audit.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent  # workspace/
sys.path.insert(0, str(ROOT / "backend-workspace"))
sys.path.insert(0, str(ROOT / "trading-core"))

# Load .env
env_path = ROOT / "backend-workspace" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

# ── DB connect ────────────────────────────────────────────────────────────────
try:
    import pyodbc
    from urllib.parse import urlparse, unquote

    # Parse from DATABASE_URL (mssql+pyodbc://user:pass@host:port/db?...)
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        # strip driver prefix
        url_part = db_url.replace("mssql+pyodbc://", "")
        # split off query string
        url_part = url_part.split("?")[0]
        userinfo, hostdb = url_part.split("@", 1)
        username, password = userinfo.split(":", 1)
        password = unquote(password)
        hostport, database = hostdb.split("/", 1)
        server = hostport.replace(":", ",")  # e.g. localhost:1433 → localhost,1433
    else:
        server   = "localhost,1433"
        database = "trading"
        username = "admin"
        password = ""

    # Try ODBC Driver 18 first, fallback to 17
    for drv in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]:
        try:
            conn_str = (
                f"DRIVER={{{drv}}};"
                f"SERVER={server};DATABASE={database};"
                f"UID={username};PWD={password};TrustServerCertificate=yes"
            )
            conn = pyodbc.connect(conn_str, timeout=10)
            print(f"[OK] Connected to SQL Server ({drv}): {server}/{database}")
            break
        except Exception:
            continue
    else:
        raise RuntimeError("Could not connect with ODBC Driver 17 or 18")
    cursor = conn.cursor()
except Exception as e:
    print(f"[ERROR] DB connect failed: {e}")
    sys.exit(1)

# ── Helpers ───────────────────────────────────────────────────────────────────
today     = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
yesterday = today - timedelta(days=1)
week_ago  = today - timedelta(days=7)

def q(sql, *params):
    cursor.execute(sql, *params)
    return cursor.fetchall()

def q1(sql, *params):
    cursor.execute(sql, *params)
    row = cursor.fetchone()
    return row[0] if row and row[0] is not None else 0

# ── 1. Check table exists ─────────────────────────────────────────────────────
print("\n" + "="*60)
print("  STEP 1 — Daily Signal Log Audit")
print("="*60)

try:
    cursor.execute("SELECT COUNT(*) FROM dbo.signal_log")
    total_all = cursor.fetchone()[0]
    print(f"\n[1A] signal_log total rows: {total_all:,}")
except Exception as e:
    print(f"[ERROR] signal_log table not found: {e}")
    sys.exit(1)

# ── 1A. Today's signals ───────────────────────────────────────────────────────
rows_today = q("""
    SELECT classification, COUNT(*) as cnt
    FROM dbo.signal_log
    WHERE timestamp >= ?
    GROUP BY classification
    ORDER BY cnt DESC
""", today)

print(f"\n[1A] Today's signals (since {today.strftime('%Y-%m-%d %H:%M UTC')}):")
total_today = 0
for row in rows_today:
    print(f"     {row[0] or 'NULL':<12} : {row[1]:>6}")
    total_today += row[1]
if not rows_today:
    print("     (none)")
print(f"     TOTAL today     : {total_today:>6}")

# ── Breakdown by asset today ──────────────────────────────────────────────────
asset_rows = q("""
    SELECT asset, classification, COUNT(*) as cnt
    FROM dbo.signal_log
    WHERE timestamp >= ?
    GROUP BY asset, classification
    ORDER BY asset, classification
""", today)

print(f"\n[1A] Today's breakdown by asset:")
if asset_rows:
    for row in asset_rows:
        print(f"     {row[0]:<12} {row[1] or 'NULL':<12} : {row[2]:>4}")
else:
    print("     (none)")

# ── 1B. Score distribution today ─────────────────────────────────────────────
score_rows = q("""
    SELECT
        MIN(final_score) as min_s,
        MAX(final_score) as max_s,
        AVG(CAST(final_score AS FLOAT)) as avg_s,
        COUNT(*) as cnt
    FROM dbo.signal_log
    WHERE timestamp >= ?
""", today)

if score_rows and score_rows[0][3] > 0:
    r = score_rows[0]
    print(f"\n[1B] Score distribution today: min={r[0]} max={r[1]} avg={r[2]:.1f} count={r[3]}")
else:
    print(f"\n[1B] Score distribution today: no data")

# ── Alert/Watch today ──────────────────────────────────────────────────────────
alert_ct = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ? AND classification = 'ALERT'", today)
watch_ct  = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ? AND classification = 'WATCH'", today)
ignore_ct = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ? AND classification = 'IGNORE'", today)
print(f"\n[1B] Classification today: ALERT={alert_ct}  WATCH={watch_ct}  IGNORE={ignore_ct}")

# ── 1C. Filter block analysis ──────────────────────────────────────────────────
try:
    block_rows = q("""
        SELECT block_reason, COUNT(*) as cnt
        FROM dbo.signal_log
        WHERE timestamp >= ? AND block_reason IS NOT NULL AND block_reason != ''
        GROUP BY block_reason
        ORDER BY cnt DESC
    """, today)
    print(f"\n[1C] Filter blocks today:")
    if block_rows:
        for row in block_rows:
            print(f"     {row[0]:<40} : {row[1]:>4}")
    else:
        print("     (none — column may not exist or no blocks)")
except Exception as e:
    print(f"\n[1C] Filter blocks: column not available ({e})")

# ── 1D. Score component breakdown ─────────────────────────────────────────────
try:
    comp_rows = q("""
        SELECT
            AVG(CAST(score_order_flow AS FLOAT)) as of_avg,
            AVG(CAST(score_smc AS FLOAT)) as smc_avg,
            AVG(CAST(score_vsa AS FLOAT)) as vsa_avg,
            AVG(CAST(score_context AS FLOAT)) as ctx_avg,
            AVG(CAST(score_bonus AS FLOAT)) as bonus_avg,
            COUNT(*) as cnt
        FROM dbo.signal_log
        WHERE timestamp >= ?
    """, today)
    if comp_rows and comp_rows[0][5] > 0:
        r = comp_rows[0]
        print(f"\n[1D] Avg score components today (n={r[5]}):")
        print(f"     OrderFlow={r[0]:.1f}  SMC={r[1]:.1f}  VSA={r[2]:.1f}  Context={r[3]:.1f}  Bonus={r[4]:.1f}")
    else:
        print(f"\n[1D] Score components: no data today")
except Exception as e:
    print(f"\n[1D] Score components: column not available ({e})")

# ── 1D. Yesterday comparison ──────────────────────────────────────────────────
yday_ct    = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ? AND timestamp < ?", yesterday, today)
yday_alert = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ? AND timestamp < ? AND classification = 'ALERT'", yesterday, today)
yday_watch = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ? AND timestamp < ? AND classification = 'WATCH'", yesterday, today)
print(f"\n[1D] Yesterday: total={yday_ct}  ALERT={yday_alert}  WATCH={yday_watch}")

week_ct    = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ?", week_ago)
week_alert = q1("SELECT COUNT(*) FROM dbo.signal_log WHERE timestamp >= ? AND classification = 'ALERT'", week_ago)
print(f"[1D] Last 7 days: total={week_ct}  ALERT={week_alert}")

# ── 1E. Latest signals ────────────────────────────────────────────────────────
recent = q("""
    SELECT TOP 10
        timestamp, asset, timeframe, direction, final_score, classification, regime
    FROM dbo.signal_log
    ORDER BY timestamp DESC
""")
print(f"\n[1E] Latest 10 signals:")
print(f"     {'Time (UTC)':<20} {'Asset':<12} {'TF':<5} {'Dir':<6} {'Score':>6} {'Class':<8} {'Regime'}")
print(f"     {'-'*20} {'-'*12} {'-'*5} {'-'*6} {'-'*6} {'-'*8} {'-'*12}")
if recent:
    for row in recent:
        ts_str = row[0].strftime('%Y-%m-%d %H:%M') if row[0] else 'NULL'
        print(f"     {ts_str:<20} {str(row[1]):<12} {str(row[2]):<5} {str(row[3]):<6} {str(row[4]):>6} {str(row[5]):<8} {str(row[6])}")
else:
    print("     (no signals yet)")

# ── 1F. Regime distribution today ─────────────────────────────────────────────
try:
    reg_rows = q("""
        SELECT regime, COUNT(*) as cnt
        FROM dbo.signal_log
        WHERE timestamp >= ?
        GROUP BY regime
        ORDER BY cnt DESC
    """, today)
    print(f"\n[1F] Regime distribution today:")
    if reg_rows:
        for row in reg_rows:
            print(f"     {str(row[0]):<15} : {row[1]:>4}")
    else:
        print("     (none)")
except Exception as e:
    print(f"\n[1F] Regime data: {e}")

# ── 1G. Validation sample ─────────────────────────────────────────────────────
try:
    val_ct = q1("""
        SELECT COUNT(*) FROM dbo.signal_log
        WHERE timestamp >= ?
          AND classification IN ('ALERT', 'WATCH')
          AND entry_price IS NOT NULL
          AND stop_loss IS NOT NULL
          AND take_profit_1 IS NOT NULL
    """, week_ago)
    print(f"\n[1G] Validation sample (7 days, ALERT/WATCH with full SL/TP): {val_ct}")
    if val_ct < 20:
        print(f"     ⚠ INSUFFICIENT SAMPLE — need ≥20 for statistical significance")
    else:
        print(f"     ✓ Sufficient — proceed with validate_signals.py")
except Exception as e:
    print(f"\n[1G] Validation sample: {e}")

# ── Done ──────────────────────────────────────────────────────────────────────
conn.close()
print(f"\n{'='*60}")
print(f"  Step 1 complete — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"{'='*60}\n")

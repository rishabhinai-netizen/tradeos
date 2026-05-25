import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime, timedelta
import json

_SUPABASE_URL = "https://pqhipbnjkbhlguvrjcah.supabase.co"
_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBxaGlwYm5qa2JobGd1dnJqY2FoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY3NzM5OSwiZXhwIjoyMDg3MjUzMzk5fQ.UTLaTxb0YNVrRXE28uSaGOv4OKd_zBwcgXa7KVzWgso"

@st.cache_resource
def get_client():
    try:
        url = st.secrets.get("SUPABASE_URL", _SUPABASE_URL)
        key = st.secrets.get("SUPABASE_SERVICE_KEY", _SUPABASE_KEY)
    except Exception:
        url, key = _SUPABASE_URL, _SUPABASE_KEY
    return create_client(url, key)

def sb(): return get_client()

# ── Sessions ──────────────────────────────────────────────────────────────────
def get_or_create_session(session_date):
    try:
        r = sb().table("tl_sessions").select("*").eq("session_date", str(session_date)).execute()
        if r.data: return r.data[0]
        r = sb().table("tl_sessions").insert({"session_date": str(session_date)}).execute()
        return r.data[0]
    except Exception:
        return {"session_id": None, "session_date": str(session_date)}

def update_session(session_id, data):
    try:
        data["updated_at"] = datetime.utcnow().isoformat()
        # Map app fields to actual schema columns
        mapped = {}
        field_map = {
            "market_bias": "market_bias", "max_loss_limit": "max_loss_limit",
            "mental_state": "mental_state", "session_quality": "session_quality",
            "loss_limit_respected": "loss_limit_respected", "loss_limit_breach_amt": "loss_limit_breach_amt",
            "personal_context": "personal_context", "session_complete": "session_complete",
            "total_trades": "total_trades", "total_pnl_net": "total_pnl_net",
            "total_charges": "total_charges", "updated_at": "updated_at",
            "eod_notes": "eod_notes", "total_pnl_gross": "total_pnl_gross",
        }
        for k, v in data.items():
            col = field_map.get(k, k)
            mapped[col] = v
        return sb().table("tl_sessions").update(mapped).eq("session_id", session_id).execute()
    except Exception:
        return None

def get_sessions(limit=90):
    try:
        r = sb().table("tl_sessions").select("*").order("session_date", desc=True).limit(limit).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def get_session_by_date(d):
    try:
        r = sb().table("tl_sessions").select("*").eq("session_date", str(d)).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None

# ── Trades ────────────────────────────────────────────────────────────────────
def upsert_trade(trade):
    try:
        trade["updated_at"] = datetime.utcnow().isoformat()
        # Remove any keys not in actual schema
        allowed = {"trade_id","session_id","session_date","instrument","display_name","isin",
                   "exchange","segment","expiry_date","buy_time","sell_time","holding_duration_mins",
                   "quantity","avg_buy_price","avg_sell_price","gross_pnl","brokerage","gst",
                   "misc_charges","stt","total_charges","net_pnl","trade_direction",
                   "kotak_order_ids","is_open","debrief_done","updated_at"}
        clean = {k: v for k, v in trade.items() if k in allowed}
        r = sb().table("tl_trades").upsert(clean, on_conflict="trade_id").execute()
        return r.data[0] if r.data else {}
    except Exception:
        return {}

def get_trades(session_date=None, limit=500, segment=None, instrument=None, debrief_pending=False):
    try:
        q = sb().table("tl_trades").select("*")
        if session_date: q = q.eq("session_date", str(session_date))
        if segment: q = q.eq("segment", segment)
        if instrument: q = q.ilike("instrument", f"%{instrument}%")
        if debrief_pending: q = q.eq("debrief_done", False).eq("is_open", False)
        r = q.order("session_date", desc=True).order("created_at", desc=True).limit(limit).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def get_trades_daterange(start, end):
    try:
        r = (sb().table("tl_trades").select("*")
             .gte("session_date", str(start)).lte("session_date", str(end))
             .order("session_date", desc=False).order("created_at", desc=False).execute())
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def get_all_trades():
    try:
        r = sb().table("tl_trades").select("*").order("session_date", desc=True).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def get_trade_by_id(trade_id):
    try:
        r = sb().table("tl_trades").select("*").eq("trade_id", str(trade_id)).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None

# ── Debriefs ──────────────────────────────────────────────────────────────────
def save_debrief(debrief):
    try:
        debrief["updated_at"] = datetime.utcnow().isoformat()
        r = sb().table("tl_debrief").upsert(debrief, on_conflict="trade_id").execute()
        sb().table("tl_trades").update({"debrief_done": True}).eq("trade_id", str(debrief["trade_id"])).execute()
        return r.data[0] if r.data else {}
    except Exception:
        return {}

def get_debrief(trade_id):
    try:
        r = sb().table("tl_debrief").select("*").eq("trade_id", str(trade_id)).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None

def get_all_debriefs():
    try:
        r = sb().table("tl_debrief").select("*").order("created_at", desc=True).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# ── Positions ─────────────────────────────────────────────────────────────────
def save_positions_snapshot(positions):
    try:
        today = str(date.today())
        sb().table("tl_positions").update({"is_latest": False}).eq("snapshot_date", today).execute()
        for p in positions:
            p["snapshot_date"] = today
            p["snapshot_time"] = datetime.utcnow().isoformat()
            p["is_latest"] = True
        if positions: sb().table("tl_positions").insert(positions).execute()
    except Exception:
        pass

def get_latest_positions():
    try:
        r = sb().table("tl_positions").select("*").eq("is_latest", True).order("unrealized_pnl", desc=True).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def get_positions_history(instrument=None, days=30):
    try:
        start = str(date.today() - timedelta(days=days))
        q = sb().table("tl_positions").select("*").gte("snapshot_date", start)
        if instrument: q = q.ilike("instrument", f"%{instrument}%")
        r = q.order("snapshot_date", desc=True).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# ── Playbook ──────────────────────────────────────────────────────────────────
def get_playbook(active_only=True):
    try:
        q = sb().table("tl_playbook").select("*")
        if active_only: q = q.eq("active", True)
        r = q.order("priority").order("rule_type").execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def add_rule(rule):
    try:
        r = sb().table("tl_playbook").insert(rule).execute()
        return r.data[0] if r.data else {}
    except Exception:
        return {}

def update_rule(rule_id, data):
    try:
        data["updated_at"] = datetime.utcnow().isoformat()
        return sb().table("tl_playbook").update(data).eq("rule_id", str(rule_id)).execute()
    except Exception:
        return None

def record_rule_outcome(rule_id, followed, pnl_impact):
    try:
        r = sb().table("tl_playbook").select("*").eq("rule_id", str(rule_id)).execute()
        if not r.data: return
        rule = r.data[0]
        update = {"times_tested": rule["times_tested"]+1, "updated_at": datetime.utcnow().isoformat()}
        if followed:
            update["times_followed"] = rule["times_followed"]+1
            update["pnl_when_followed"] = (rule["pnl_when_followed"] or 0) + pnl_impact
        else:
            update["times_violated"] = rule["times_violated"]+1
            update["pnl_when_violated"] = (rule["pnl_when_violated"] or 0) + pnl_impact
        sb().table("tl_playbook").update(update).eq("rule_id", str(rule_id)).execute()
    except Exception:
        pass

# ── Patterns ──────────────────────────────────────────────────────────────────
def get_patterns(severity=None):
    try:
        q = sb().table("tl_patterns").select("*").eq("acknowledged", False)
        if severity: q = q.eq("severity", severity)
        r = q.order("severity").order("occurrence_count", desc=True).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def upsert_pattern(pattern):
    try:
        pattern["updated_at"] = datetime.utcnow().isoformat()
        sb().table("tl_patterns").upsert(pattern, on_conflict="pattern_key").execute()
    except Exception:
        pass

def acknowledge_pattern(pattern_id):
    try:
        sb().table("tl_patterns").update({"acknowledged": True}).eq("pattern_id", str(pattern_id)).execute()
    except Exception:
        pass

# ── Violations ────────────────────────────────────────────────────────────────
def log_violation(trade_id, rule_id, session_id, vtype, desc, pnl):
    try:
        sb().table("tl_violations").insert({
            "trade_id": str(trade_id), "rule_id": str(rule_id), "session_id": str(session_id),
            "violation_type": vtype, "description": desc, "pnl_impact": pnl
        }).execute()
    except Exception:
        pass

# ── Metrics ───────────────────────────────────────────────────────────────────
def get_latest_metrics():
    try:
        r = sb().table("tl_daily_metrics").select("*").order("metric_date", desc=True).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None

def get_metrics_history(days=90):
    try:
        start = str(date.today() - timedelta(days=days))
        r = sb().table("tl_daily_metrics").select("*").gte("metric_date", start).order("metric_date", desc=False).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def recompute_daily_metrics():
    try:
        today = str(date.today())
        all_trades = get_all_trades()
        if all_trades.empty: return
        df = all_trades.copy()
        df["net_pnl"] = pd.to_numeric(df["net_pnl"], errors="coerce").fillna(0)
        df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
        closed = df[~df.get("is_open", pd.Series([False]*len(df))).fillna(False)]
        wins = closed[closed["net_pnl"]>0]; losses = closed[closed["net_pnl"]<0]
        def wr(s): return round(len(s[s["net_pnl"]>0])/len(s),4) if len(s)>0 else None
        today_dt = date.today()
        d7   = closed[closed["session_date"]>=today_dt-timedelta(days=7)]
        d30  = closed[closed["session_date"]>=today_dt-timedelta(days=30)]
        fy_start = date(2026,4,1) if today_dt>=date(2026,4,1) else date(2025,4,1)
        fy   = closed[closed["session_date"]>=fy_start]
        td   = closed[closed["session_date"]==today_dt]
        aw   = float(wins["net_pnl"].mean())   if len(wins)>0   else 0
        al   = float(losses["net_pnl"].mean()) if len(losses)>0 else 0
        payoff = abs(aw/al) if al!=0 else None
        streak, stype = 0, "Neutral"
        sorted_t = closed.sort_values("session_date", ascending=False)
        if not sorted_t.empty:
            fp_ = sorted_t.iloc[0]["net_pnl"]
            stype = "Win" if fp_>0 else "Loss"
            for _, row in sorted_t.iterrows():
                if (stype=="Win" and row["net_pnl"]>0) or (stype=="Loss" and row["net_pnl"]<0): streak+=1
                else: break
        seg_pnl = closed.groupby("segment")["net_pnl"].sum().to_dict() if "segment" in closed.columns else {}
        metrics = {
            "metric_date": today,
            "total_trades_td": len(td), "winning_trades_td": len(td[td["net_pnl"]>0]), "losing_trades_td": len(td[td["net_pnl"]<0]),
            "win_rate_7d": wr(d7), "win_rate_30d": wr(d30), "win_rate_alltime": wr(closed),
            "pnl_td": float(td["net_pnl"].sum()), "pnl_7d": float(d7["net_pnl"].sum()),
            "pnl_30d": float(d30["net_pnl"].sum()), "pnl_fy": float(fy["net_pnl"].sum()),
            "pnl_alltime": float(closed["net_pnl"].sum()), "cumulative_pnl": float(closed["net_pnl"].sum()),
            "avg_win": aw, "avg_loss": al, "payoff_ratio": payoff,
            "streak_current": streak, "streak_type": stype,
            "pnl_by_segment": json.dumps(seg_pnl), "updated_at": datetime.utcnow().isoformat(),
        }
        sb().table("tl_daily_metrics").upsert(metrics, on_conflict="metric_date").execute()
    except Exception:
        pass

# ── Insights ──────────────────────────────────────────────────────────────────
def save_insight(insight):
    try:
        sb().table("tl_insights").insert(insight).execute()
    except Exception:
        pass

def get_insights(limit=20):
    try:
        r = sb().table("tl_insights").select("*").eq("dismissed", False).order("created_at", desc=True).limit(limit).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def dismiss_insight(insight_id):
    try:
        sb().table("tl_insights").update({"dismissed": True}).eq("insight_id", str(insight_id)).execute()
    except Exception:
        pass

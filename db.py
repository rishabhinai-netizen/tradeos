import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime, timedelta
import json

@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])

def sb(): return get_client()

def get_or_create_session(session_date):
    r = sb().table("tl_sessions").select("*").eq("session_date", str(session_date)).execute()
    if r.data: return r.data[0]
    r = sb().table("tl_sessions").insert({"session_date": str(session_date)}).execute()
    return r.data[0]

def update_session(session_id, data):
    data["updated_at"] = datetime.utcnow().isoformat()
    return sb().table("tl_sessions").update(data).eq("session_id", session_id).execute()

def get_sessions(limit=90):
    r = sb().table("tl_sessions").select("*").order("session_date", desc=True).limit(limit).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def get_session_by_date(d):
    r = sb().table("tl_sessions").select("*").eq("session_date", str(d)).execute()
    return r.data[0] if r.data else None

def upsert_trade(trade):
    trade["updated_at"] = datetime.utcnow().isoformat()
    r = sb().table("tl_trades").upsert(trade, on_conflict="trade_id").execute()
    return r.data[0] if r.data else {}

def get_trades(session_date=None, limit=500, segment=None, instrument=None, debrief_pending=False):
    q = sb().table("tl_trades").select("*")
    if session_date: q = q.eq("session_date", str(session_date))
    if segment: q = q.eq("segment", segment)
    if instrument: q = q.ilike("instrument", f"%{instrument}%")
    if debrief_pending: q = q.eq("debrief_done", False).eq("is_open", False)
    r = q.order("session_date", desc=True).order("buy_time", desc=True).limit(limit).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def get_trades_daterange(start, end):
    r = (sb().table("tl_trades").select("*")
         .gte("session_date", str(start)).lte("session_date", str(end))
         .order("session_date", desc=False).execute())
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def get_all_trades():
    r = sb().table("tl_trades").select("*").order("session_date", desc=True).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def get_trade_by_id(trade_id):
    r = sb().table("tl_trades").select("*").eq("trade_id", trade_id).execute()
    return r.data[0] if r.data else None

def save_debrief(debrief):
    debrief["updated_at"] = datetime.utcnow().isoformat()
    r = sb().table("tl_debrief").upsert(debrief, on_conflict="trade_id").execute()
    sb().table("tl_trades").update({"debrief_done": True}).eq("trade_id", debrief["trade_id"]).execute()
    return r.data[0] if r.data else {}

def get_debrief(trade_id):
    r = sb().table("tl_debrief").select("*").eq("trade_id", trade_id).execute()
    return r.data[0] if r.data else None

def get_all_debriefs():
    r = sb().table("tl_debrief").select("*").order("created_at", desc=True).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def save_positions_snapshot(positions):
    today = str(date.today())
    sb().table("tl_positions").update({"is_latest": False}).eq("snapshot_date", today).execute()
    for p in positions:
        p["snapshot_date"] = today
        p["snapshot_time"] = datetime.utcnow().isoformat()
        p["is_latest"] = True
    if positions: sb().table("tl_positions").insert(positions).execute()

def get_latest_positions():
    r = (sb().table("tl_positions").select("*").eq("is_latest", True).order("unrealized_pnl", desc=True).execute())
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def get_playbook(active_only=True):
    q = sb().table("tl_playbook").select("*")
    if active_only: q = q.eq("active", True)
    r = q.order("priority").order("rule_type").execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def add_rule(rule):
    r = sb().table("tl_playbook").insert(rule).execute()
    return r.data[0] if r.data else {}

def update_rule(rule_id, data):
    data["updated_at"] = datetime.utcnow().isoformat()
    return sb().table("tl_playbook").update(data).eq("rule_id", rule_id).execute()

def get_patterns(severity=None):
    q = sb().table("tl_patterns").select("*").eq("acknowledged", False)
    if severity: q = q.eq("severity", severity)
    r = q.order("severity").order("occurrence_count", desc=True).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def upsert_pattern(pattern):
    pattern["updated_at"] = datetime.utcnow().isoformat()
    sb().table("tl_patterns").upsert(pattern, on_conflict="pattern_key").execute()

def acknowledge_pattern(pattern_id):
    sb().table("tl_patterns").update({"acknowledged": True}).eq("pattern_id", pattern_id).execute()

def log_violation(trade_id, rule_id, session_id, vtype, desc, pnl):
    sb().table("tl_violations").insert({"trade_id": trade_id, "rule_id": rule_id, "session_id": session_id, "violation_type": vtype, "description": desc, "pnl_impact": pnl}).execute()

def get_latest_metrics():
    r = sb().table("tl_daily_metrics").select("*").order("metric_date", desc=True).limit(1).execute()
    return r.data[0] if r.data else None

def get_metrics_history(days=90):
    start = str(date.today() - timedelta(days=days))
    r = sb().table("tl_daily_metrics").select("*").gte("metric_date", start).order("metric_date", desc=False).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def recompute_daily_metrics():
    today = str(date.today())
    all_trades = get_all_trades()
    if all_trades.empty: return
    df = all_trades.copy()
    df["net_pnl"] = pd.to_numeric(df["net_pnl"], errors="coerce").fillna(0)
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
    closed = df[~df.get("is_open", pd.Series([False]*len(df))).fillna(False)]
    wins = closed[closed["net_pnl"] > 0]
    losses = closed[closed["net_pnl"] < 0]
    def wr(s): return round(len(s[s["net_pnl"]>0])/len(s),4) if len(s)>0 else None
    today_dt = date.today()
    d7 = closed[closed["session_date"] >= today_dt - timedelta(days=7)]
    d30 = closed[closed["session_date"] >= today_dt - timedelta(days=30)]
    fy_start = date(2026,4,1) if today_dt >= date(2026,4,1) else date(2025,4,1)
    fy = closed[closed["session_date"] >= fy_start]
    td = closed[closed["session_date"] == today_dt]
    aw = float(wins["net_pnl"].mean()) if len(wins)>0 else 0
    al = float(losses["net_pnl"].mean()) if len(losses)>0 else 0
    payoff = abs(aw/al) if al!=0 else None
    streak, stype = 0, "Neutral"
    sorted_t = closed.sort_values("session_date", ascending=False)
    if not sorted_t.empty:
        fp = sorted_t.iloc[0]["net_pnl"]
        stype = "Win" if fp>0 else "Loss"
        for _, row in sorted_t.iterrows():
            if (stype=="Win" and row["net_pnl"]>0) or (stype=="Loss" and row["net_pnl"]<0): streak+=1
            else: break
    seg_pnl = closed.groupby("segment")["net_pnl"].sum().to_dict() if "segment" in closed.columns else {}
    metrics = {
        "metric_date": today, "total_trades_td": len(td), "winning_trades_td": len(td[td["net_pnl"]>0]),
        "losing_trades_td": len(td[td["net_pnl"]<0]), "win_rate_7d": wr(d7), "win_rate_30d": wr(d30),
        "win_rate_alltime": wr(closed), "pnl_td": float(td["net_pnl"].sum()), "pnl_7d": float(d7["net_pnl"].sum()),
        "pnl_30d": float(d30["net_pnl"].sum()), "pnl_fy": float(fy["net_pnl"].sum()),
        "pnl_alltime": float(closed["net_pnl"].sum()), "cumulative_pnl": float(closed["net_pnl"].sum()),
        "avg_win": aw, "avg_loss": al, "payoff_ratio": payoff, "streak_current": streak, "streak_type": stype,
        "pnl_by_segment": json.dumps(seg_pnl), "updated_at": datetime.utcnow().isoformat(),
    }
    sb().table("tl_daily_metrics").upsert(metrics, on_conflict="metric_date").execute()

def save_insight(insight):
    sb().table("tl_insights").insert(insight).execute()

def get_insights(limit=20):
    r = sb().table("tl_insights").select("*").eq("dismissed", False).order("created_at", desc=True).limit(limit).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

def dismiss_insight(insight_id):
    sb().table("tl_insights").update({"dismissed": True}).eq("insight_id", insight_id).execute()

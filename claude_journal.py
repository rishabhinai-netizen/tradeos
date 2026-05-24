"""
claude_journal.py
Standalone Supabase push functions for use when Claude chat does the journaling.
Claude pulls trades from Kotak MCP, asks questions in chat, then calls these functions.
Run: pip install supabase
"""
import os, uuid, json
from datetime import date, datetime
from supabase import create_client

SUPABASE_URL = "https://pqhipbnjkbhlguvrjcah.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def save_session(session_date, market_bias, max_loss, mental_state):
    r = sb().table("tl_sessions").select("session_id").eq("session_date", str(session_date)).execute()
    if r.data:
        sid = r.data[0]["session_id"]
        sb().table("tl_sessions").update({
            "market_bias": market_bias, "max_loss_limit": max_loss,
            "mental_state": mental_state, "updated_at": datetime.utcnow().isoformat()
        }).eq("session_id", sid).execute()
        return sid
    r = sb().table("tl_sessions").insert({
        "session_date": str(session_date), "market_bias": market_bias,
        "max_loss_limit": max_loss, "mental_state": mental_state
    }).execute()
    return r.data[0]["session_id"]

def save_trade(session_id, instrument, exchange, segment, qty,
               buy_price, sell_price, gross_pnl, charges, net_pnl,
               buy_time=None, sell_time=None, holding_mins=None, expiry=None):
    trade_id = str(uuid.uuid4())
    sb().table("tl_trades").insert({
        "trade_id": trade_id, "session_id": session_id,
        "session_date": str(date.today()),
        "instrument": instrument, "exchange": exchange, "segment": segment,
        "quantity": qty, "avg_buy_price": buy_price, "avg_sell_price": sell_price,
        "gross_pnl": gross_pnl, "total_charges": charges, "net_pnl": net_pnl,
        "buy_time": buy_time, "sell_time": sell_time,
        "holding_duration_mins": holding_mins,
        "expiry_date": str(expiry) if expiry else None,
        "is_open": sell_price is None, "debrief_done": False,
    }).execute()
    return trade_id

def save_debrief(trade_id, session_id, setup_type, had_sl, had_target,
                 size_rationale, emotion_score, influence_source,
                 exit_type, added_to_position, exec_quality,
                 lesson_text, playbook_flag):
    sb().table("tl_debrief").upsert({
        "trade_id": trade_id, "session_id": session_id,
        "setup_type": setup_type, "had_stoploss": had_sl,
        "had_target": had_target, "size_rationale": size_rationale,
        "emotion_score_entry": emotion_score,
        "influence_source": influence_source,
        "exit_type": exit_type, "added_to_position": added_to_position,
        "execution_quality": exec_quality, "lesson_text": lesson_text,
        "playbook_flag": playbook_flag, "debrief_method": "Claude chat",
        "updated_at": datetime.utcnow().isoformat()
    }, on_conflict="trade_id").execute()
    sb().table("tl_trades").update({"debrief_done": True}).eq("trade_id", trade_id).execute()

def save_eod(session_id, session_quality, loss_limit_respected,
             breach_amount=0, personal_context=None):
    sb().table("tl_sessions").update({
        "session_quality": session_quality,
        "loss_limit_respected": loss_limit_respected,
        "loss_limit_breach_amt": breach_amount,
        "personal_context": personal_context,
        "session_complete": True,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("session_id", session_id).execute()

def save_positions(positions: list):
    """positions = list of dicts from Kotak MCP holdings"""
    today = str(date.today())
    sb().table("tl_positions").update({"is_latest": False}).eq("snapshot_date", today).execute()
    for p in positions:
        p["snapshot_date"] = today
        p["snapshot_time"] = datetime.utcnow().isoformat()
        p["is_latest"] = True
    if positions:
        sb().table("tl_positions").insert(positions).execute()

if __name__ == "__main__":
    # Quick smoke test
    print("Testing Supabase connection...")
    r = sb().table("tl_playbook").select("rule_short").execute()
    print(f"Playbook rules: {[x['rule_short'] for x in r.data]}")
    print("Connection OK")

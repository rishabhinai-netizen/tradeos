import streamlit as st, pandas as pd
from datetime import date, datetime
import db
from kotak import parse_tradebook_csv, parse_holdings_to_positions, detect_patterns_from_trades

st.set_page_config(page_title="Journal · TradeOS", page_icon="📓", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.block-container{padding:1.5rem 2rem;max-width:1000px;}
.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}
.qwhy{font-size:11px;color:#888;font-style:italic;margin-bottom:8px;}
</style>""", unsafe_allow_html=True)

st.markdown("## 📓 Journal Today")
today = date.today()
st.caption(today.strftime('%A, %d %B %Y'))

tab1, tab2, tab3 = st.tabs(["📥 Import Trades", "🗒️ Session Debrief", "💬 Debrief Trades"])

with tab1:
    st.markdown('<div class="sec">Import from Kotak Neo</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Trade Book CSV**"); st.caption("Kotak Neo → Reports → Transaction Statement")
        tf = st.file_uploader("Transaction CSV", type=["csv"], key="tcsvk")
    with c2:
        st.markdown("**Holdings CSV**"); st.caption("Kotak Neo → Portfolio → Holdings → Export")
        hf = st.file_uploader("Holdings CSV", type=["csv"], key="hcsvk")
    if (tf or hf) and st.button("🚀 Process & Save", type="primary", use_container_width=True):
        session = db.get_or_create_session(today); sid = session["session_id"]
        if hf:
            raw = hf.read().decode("utf-8")
            positions = parse_holdings_to_positions(raw)
            db.save_positions_snapshot(positions)
            st.success(f"✅ {len(positions)} positions saved")
        if tf:
            raw = tf.read().decode("utf-8")
            trades = parse_tradebook_csv(raw, today, sid)
            if trades:
                for t in trades: db.upsert_trade(t)
                closed = [t for t in trades if not t["is_open"]]
                db.update_session(sid, {"total_trades":len(closed),"total_pnl_net":sum(t["net_pnl"] for t in closed),"total_charges":sum(t["total_charges"] for t in trades)})
                all_t = db.get_all_trades(); all_d = db.get_all_debriefs()
                for p in detect_patterns_from_trades(all_t, all_d): db.upsert_pattern(p)
                db.recompute_daily_metrics()
                st.success(f"✅ {len(trades)} trades imported")
            else: st.info("No trades found for today.")
    today_trades = db.get_trades(session_date=today)
    if not today_trades.empty:
        st.markdown('<div class="sec">Today\'s trades</div>', unsafe_allow_html=True)
        st.dataframe(today_trades[["instrument","segment","quantity","net_pnl","debrief_done"]].rename(columns={"net_pnl":"Net P&L","debrief_done":"✓ Done"}), use_container_width=True, hide_index=True)

with tab2:
    st.markdown('<div class="sec">Session journal — once per day</div>', unsafe_allow_html=True)
    session = db.get_or_create_session(today); sid = session["session_id"]
    c1,c2 = st.columns(2)
    with c1:
        bias = st.selectbox("A1 · Market bias", ["—","Bullish","Bearish","Neutral","No view — just reacting"])
        st.markdown('<div class="qwhy">Are you trading with conviction or just reacting?</div>', unsafe_allow_html=True)
        max_loss = st.number_input("A2 · Max loss limit today (₹)", min_value=0, step=5000)
        st.markdown('<div class="qwhy">Your daily risk commitment — you will be held accountable at EOD</div>', unsafe_allow_html=True)
    with c2:
        mental = st.selectbox("A3 · Mental state", ["—","Sharp","Normal","Tired","Stressed","Distracted"])
        st.markdown('<div class="qwhy">Most underrated trading variable. Tired/stressed days show worse outcomes over time</div>', unsafe_allow_html=True)
        sess_q = st.select_slider("D2 · Session quality", [1,2,3,4,5], value=3, format_func=lambda x:{1:"1·Disaster",2:"2·Poor",3:"3·Average",4:"4·Good",5:"5·Excellent"}[x])
    c3,c4 = st.columns(2)
    with c3:
        respected = st.selectbox("D1 · Respected max loss limit?", ["—","Yes","No"])
        breach = 0
        if respected=="No": breach = st.number_input("Exceeded by (₹)", min_value=0, step=1000)
    with c4:
        eod = st.text_area("D3 · Personal context (optional, private)", height=80)
    if st.button("💾 Save Session", type="primary", use_container_width=True):
        db.update_session(sid, {"market_bias": None if bias=="—" else bias, "max_loss_limit": max_loss or None, "mental_state": None if mental=="—" else mental, "session_quality": sess_q, "loss_limit_respected": None if respected=="—" else (respected=="Yes"), "loss_limit_breach_amt": breach if respected=="No" else 0, "personal_context": eod or None, "session_complete": respected!="—"})
        db.recompute_daily_metrics()
        st.success("✅ Session journal saved!")

with tab3:
    st.markdown('<div class="sec">Per-trade debrief (B + C questions)</div>', unsafe_allow_html=True)
    pending = db.get_trades(debrief_pending=True, limit=20)
    if pending.empty:
        st.success("✅ All trades debriefed!")
    else:
        st.info(f"**{len(pending)}** trade(s) need debrief")
        opts = {}
        for _,t in pending.iterrows():
            pnl = t.get("net_pnl",0) or 0
            opts[f"{t['instrument'][:28]} · {t['session_date']} · {'+ ' if pnl>=0 else ''}{pnl:,.0f}"] = t["trade_id"]
        sel = st.selectbox("Select trade", list(opts.keys()))
        tid = opts[sel]; trade = db.get_trade_by_id(tid)
        if trade:
            pnl = trade.get("net_pnl",0) or 0
            st.markdown(f"**{trade['instrument']}** · {trade['session_date']} · {trade.get('segment','')} · Qty {trade.get('quantity','')} · Net P&L: {'+ ' if pnl>=0 else ''}₹{abs(pnl):,.0f}")
            existing = db.get_debrief(tid) or {}
            st.markdown("#### Section B — Entry")
            c1,c2 = st.columns(2)
            with c1:
                setup = st.selectbox("B1 · Setup type", ["—","Breakout","Trend-follow","Reversal","News/Event","Commodity momentum","Index play","Gut feel","Other"])
                st.markdown('<div class="qwhy">Win rate by setup = where your edge lives</div>', unsafe_allow_html=True)
                snotes = st.text_input("Setup notes", placeholder="Context...")
                had_sl = st.selectbox("B2 · Stop-loss in mind?", ["—","Yes","No","Mental stop only"])
                sl_lvl = st.number_input("SL level", min_value=0.0, step=0.5) if had_sl=="Yes" else None
            with c2:
                had_tgt = st.selectbox("B3 · Profit target?", ["—","Yes","No","Trail and see"])
                tgt_lvl = st.number_input("Target level", min_value=0.0, step=0.5) if had_tgt=="Yes" else None
                size_r = st.selectbox("B4 · Size rationale", ["—","Standard size","Sized up — high conviction","Sized down — uncertain","Oversized — be honest"])
                emo = st.select_slider("B5 · Emotion at entry", [1,2,3,4,5], value=3, format_func=lambda x:{1:"1·Calm",2:"2·Eager",3:"3·Neutral",4:"4·FOMO",5:"5·Panic"}[x])
                st.markdown('<div class="qwhy">Most important long-term data point</div>', unsafe_allow_html=True)
            influence = st.multiselect("B6 · Influenced by", ["Own analysis","News/tip","Someone else's call","Social media","Previous trade outcome"])
            st.markdown("#### Section C — Exit")
            c3,c4 = st.columns(2)
            with c3:
                exit_t = st.selectbox("C1 · How did you exit?", ["—","Hit target","Hit stop","Trailed and exited","Cut early (fear)","Held too long (greed)","Force-closed by expiry","Partial exit"])
                added = st.selectbox("C2 · Added to position?", ["No","Yes — planned","Yes — impulsive"])
            with c4:
                exec_q = st.select_slider("C3 · Execution quality", [1,2,3,4,5], value=3, format_func=lambda x:{1:"1·Off-plan",2:"2·Mostly off",3:"3·Mixed",4:"4·Mostly on",5:"5·Perfect"}[x])
                pb_flag = st.selectbox("C5 · Playbook candidate?", ["No","Yes — repeatable setup","Maybe — flag for review"])
            lesson = st.text_area("C4 · One thing you\'d do differently", height=70)
            if st.button("💾 Save Debrief", type="primary", use_container_width=True, key=f"sd_{tid}"):
                sess_d = db.get_or_create_session(date.fromisoformat(str(trade["session_date"])))
                db.save_debrief({"trade_id":tid,"session_id":sess_d["session_id"],"setup_type":None if setup=="—" else setup,"setup_notes":snotes or None,"had_stoploss":None if had_sl=="—" else had_sl,"stoploss_level":sl_lvl,"had_target":None if had_tgt=="—" else had_tgt,"target_level":tgt_lvl,"size_rationale":None if size_r=="—" else size_r,"emotion_score_entry":emo,"influence_source":influence or None,"exit_type":None if exit_t=="—" else exit_t,"added_to_position":added,"execution_quality":exec_q,"lesson_text":lesson or None,"playbook_flag":pb_flag,"debrief_method":"Manual"})
                db.recompute_daily_metrics()
                st.success(f"✅ Debrief saved!"); st.rerun()

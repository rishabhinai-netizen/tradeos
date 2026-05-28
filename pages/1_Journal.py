import streamlit as st
import pandas as pd
from datetime import date, timedelta
import db

st.set_page_config(page_title="Journal · TradeOS", page_icon="📓", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.block-container{padding:1.5rem 2rem;max-width:1100px;}
.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}
.scard{background:#fff;border:1px solid #E8E6E1;border-radius:12px;padding:1rem 1.25rem;margin-bottom:8px;}
.slabel{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;}
.sval{font-size:15px;font-weight:500;}
.trow{padding:10px 0;border-bottom:1px solid #F0EEE9;}
.trow:last-child{border-bottom:none;}
.green{color:#1A7A3C;font-weight:500;} .red{color:#B91C1C;font-weight:500;}
.badge{font-size:10px;font-weight:600;padding:2px 8px;border-radius:4px;letter-spacing:.04em;}
.bpead{background:#EAF3DE;color:#27500A;}
.bopen{background:#E6F1FB;color:#0C447C;}
.bpend{background:#FEF2F2;color:#A32D2D;}
.bdone{background:#F0F0EE;color:#444;}
.lbox{background:#F9F8F6;border-left:3px solid #378ADD;border-radius:0 8px 8px 0;padding:10px 14px;font-size:13px;color:#444;line-height:1.65;margin-top:8px;}
.lbox-warn{border-left-color:#EF4444;}
.empty{background:#F9F8F6;border:1px dashed #D4D0C8;border-radius:12px;padding:2rem;text-align:center;color:#888;font-size:13px;}
.hint{background:#EBF5FF;border:1px solid #BFDBFE;border-radius:8px;padding:12px 16px;font-size:13px;color:#1E40AF;line-height:1.6;margin-bottom:1rem;}
.meta-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;}
.meta-pill{font-size:11px;background:#F3F2EF;color:#555;border-radius:4px;padding:3px 9px;}
</style>""", unsafe_allow_html=True)

st.markdown("## 📓 Journal")

# Date picker
col1, col2 = st.columns([2, 5])
with col1:
    selected_date = st.date_input("Date", value=date.today(), max_value=date.today())

session = db.get_session_by_date(selected_date)
trades_df = db.get_trades(session_date=selected_date)
debriefs_df = db.get_all_debriefs()

# Claude chat hint
st.markdown("""<div class="hint">
💬 <strong>All journaling happens in Claude chat.</strong> Say <em>"Journal Today"</em> to Rishabh's Claude — 
it logs into Kotak Neo, pulls today's trades, asks all debrief questions here, and pushes everything to this dashboard automatically.
This page is read-only.
</div>""", unsafe_allow_html=True)

# ── Session summary ──────────────────────────────────────────────────────────
if session:
    st.markdown('<div class="sec">Session summary</div>', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    def pill(label, val, col):
        with col:
            st.markdown(f'<div class="scard"><div class="slabel">{label}</div><div class="sval">{val or "—"}</div></div>', unsafe_allow_html=True)
    pill("Market bias", session.get("market_bias"), c1)
    pill("Mental state", session.get("mental_state"), c2)
    sq = session.get("session_quality")
    q_label = {1:"1 · Disaster",2:"2 · Poor",3:"3 · Average",4:"4 · Good",5:"5 · Excellent"}.get(sq, "—")
    pill("Session quality", q_label, c3)
    ll = session.get("loss_limit_respected")
    pill("Loss limit", "✅ Respected" if ll==True else ("❌ Breached" if ll==False else "—"), c4)
    pnl_net = session.get("total_pnl_net") or 0
    pnl_color = "green" if pnl_net >= 0 else "red"
    with c5:
        st.markdown(f'<div class="scard"><div class="slabel">Net P&L</div><div class="sval {pnl_color}">{"+" if pnl_net>=0 else ""}₹{abs(pnl_net):,.0f}</div></div>', unsafe_allow_html=True)
    eod = session.get("eod_notes") or session.get("personal_context")
    if eod:
        st.markdown(f'<div class="lbox">{eod}</div>', unsafe_allow_html=True)
else:
    st.info(f"No session recorded for {selected_date.strftime('%d %b %Y')}. Say 'Journal Today' to Claude to create one.")

# ── Trades ───────────────────────────────────────────────────────────────────
st.markdown('<div class="sec">Trades</div>', unsafe_allow_html=True)

if trades_df.empty:
    st.markdown('<div class="empty">No trades recorded for this date.</div>', unsafe_allow_html=True)
else:
    trades_df["net_pnl"] = pd.to_numeric(trades_df["net_pnl"], errors="coerce").fillna(0)
    closed = trades_df[~trades_df.get("is_open", pd.Series([False]*len(trades_df))).fillna(False)]
    open_t = trades_df[trades_df.get("is_open", pd.Series([False]*len(trades_df))).fillna(False)]

    total_pnl = closed["net_pnl"].sum()
    wins = len(closed[closed["net_pnl"]>0]); losses = len(closed[closed["net_pnl"]<0])
    debriefed = len(closed[closed.get("debrief_done", pd.Series([False]*len(closed))).fillna(False)])
    pending = len(closed) - debriefed

    mc1,mc2,mc3,mc4 = st.columns(4)
    def metric(col, label, val, color=""):
        with col: st.markdown(f'<div class="scard"><div class="slabel">{label}</div><div class="sval {color}">{val}</div></div>', unsafe_allow_html=True)
    metric(mc1, "Closed trades", len(closed))
    metric(mc2, "Realized P&L", f'{"+" if total_pnl>=0 else ""}₹{abs(total_pnl):,.0f}', "green" if total_pnl>=0 else "red")
    metric(mc3, "W / L", f"{wins} / {losses}", "green" if wins>losses else "red" if losses>wins else "")
    metric(mc4, "Debriefed", f"{debriefed} / {len(closed)}", "green" if pending==0 else "red")

    if pending > 0:
        st.warning(f"**{pending}** trade(s) not yet debriefed. Say **'Journal Today'** to Claude to complete them.")

    # Closed trades table
    if not closed.empty:
        st.markdown("**Closed trades**")
        for _, t in closed.sort_values("created_at").iterrows():
            pnl = float(t.get("net_pnl", 0) or 0)
            pnl_str = f'<span class="{"green" if pnl>=0 else "red"}">{"+" if pnl>=0 else ""}₹{abs(pnl):,.0f}</span>'
            done = bool(t.get("debrief_done", False))
            badge = '<span class="badge bdone">✓ Debriefed</span>' if done else '<span class="badge bpend">Pending debrief</span>'
            seg = str(t.get("segment","")).replace("_"," ")
            dur = t.get("holding_duration_mins")
            dur_str = f"{int(dur)}m" if dur and pd.notna(dur) else "—"
            qty = t.get("quantity","")
            buy = t.get("avg_buy_price")
            sell = t.get("avg_sell_price")
            price_str = f"₹{float(buy):,.2f} → ₹{float(sell):,.2f}" if buy and sell and float(buy)>0 and float(sell)>0 else "—"

            # Get debrief if exists
            debrief = None
            if not debriefs_df.empty and "trade_id" in debriefs_df.columns:
                match = debriefs_df[debriefs_df["trade_id"]==t["trade_id"]]
                if not match.empty: debrief = match.iloc[0]

            with st.expander(f"**{t.get('instrument','')}** · {pnl_str} · {badge}", expanded=False):
                dc1,dc2,dc3,dc4 = st.columns(4)
                with dc1: st.markdown(f'<div class="slabel">Segment</div><div>{seg}</div>', unsafe_allow_html=True)
                with dc2: st.markdown(f'<div class="slabel">Qty</div><div>{qty}</div>', unsafe_allow_html=True)
                with dc3: st.markdown(f'<div class="slabel">Price</div><div>{price_str}</div>', unsafe_allow_html=True)
                with dc4: st.markdown(f'<div class="slabel">Held</div><div>{dur_str}</div>', unsafe_allow_html=True)

                if debrief is not None:
                    st.markdown("---")
                    dd1,dd2,dd3,dd4 = st.columns(4)
                    with dd1: st.markdown(f'<div class="slabel">Setup</div><div>{debrief.get("setup_type","—")}</div>', unsafe_allow_html=True)
                    with dd2: st.markdown(f'<div class="slabel">Emotion</div><div>{debrief.get("emotion_score_entry","—")}/5</div>', unsafe_allow_html=True)
                    with dd3: st.markdown(f'<div class="slabel">Exit type</div><div>{debrief.get("exit_type","—")}</div>', unsafe_allow_html=True)
                    with dd4: st.markdown(f'<div class="slabel">Execution</div><div>{debrief.get("execution_quality","—")}/5</div>', unsafe_allow_html=True)
                    lesson = debrief.get("lesson_text")
                    if lesson:
                        warn = "lbox-warn" if debrief.get("playbook_flag")=="No" else "lbox"
                        st.markdown(f'<div class="{warn}">💡 {lesson}</div>', unsafe_allow_html=True)

    # Open positions
    if not open_t.empty:
        st.markdown("**Open / carried positions**")
        for _, t in open_t.sort_values("created_at").iterrows():
            seg = str(t.get("segment","")).replace("_"," ")
            buy = t.get("avg_buy_price")
            buy_str = f"₹{float(buy):,.2f}" if buy and pd.notna(buy) and float(buy)>0 else "—"
            st.markdown(f'<div class="scard" style="margin-bottom:6px;"><span class="badge bopen">OPEN</span> &nbsp; <strong>{t.get("instrument","")}</strong> · {seg} · Qty {t.get("quantity","")} · Entry {buy_str}</div>', unsafe_allow_html=True)

# ── Past sessions navigator ──────────────────────────────────────────────────
st.markdown('<div class="sec">Recent sessions</div>', unsafe_allow_html=True)
sessions_df = db.get_sessions(limit=14)
if not sessions_df.empty:
    sessions_df["total_pnl_net"] = pd.to_numeric(sessions_df["total_pnl_net"], errors="coerce").fillna(0)
    cols = st.columns(7)
    for i, (_, s) in enumerate(sessions_df.head(7).iterrows()):
        d = pd.to_datetime(s["session_date"]).date()
        pnl = float(s["total_pnl_net"])
        sq = s.get("session_quality") or 0
        with cols[i % 7]:
            color = "#1A7A3C" if pnl > 0 else "#B91C1C" if pnl < 0 else "#888"
            st.markdown(f"""<div class="scard" style="text-align:center;cursor:pointer;">
                <div style="font-size:11px;color:#888">{d.strftime('%d %b')}</div>
                <div style="font-size:15px;font-weight:600;color:{color};">{"+" if pnl>=0 else ""}₹{abs(pnl)/1000:.0f}k</div>
                <div style="font-size:10px;color:#aaa">{'⭐'*sq if sq else '—'}</div>
            </div>""", unsafe_allow_html=True)

import streamlit as st, pandas as pd
from datetime import date, timedelta
import db
st.set_page_config(page_title="Trade Log · TradeOS", page_icon="📋", layout="wide")
st.markdown("<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');html,body,[class*=\"css\"]{font-family:'DM Sans',sans-serif;}.block-container{padding:1.5rem 2rem;max-width:1400px;}.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}</style>", unsafe_allow_html=True)
st.markdown("## 📋 Trade Log")
c1,c2,c3,c4 = st.columns([2,2,2,1])
with c1: days_back = st.selectbox("Period",[30,90,180,365,9999],format_func=lambda x:f"Last {x} days" if x<9999 else "All time")
with c2: seg = st.selectbox("Segment",["All","FUT_COMMODITY","FUT_EQUITY","FUT_INDEX","EQ_INTRADAY","EQ_DELIVERY"])
with c3: instr = st.text_input("Search instrument",placeholder="GOLD, BSE...")
with c4: pend = st.checkbox("Pending only")
start = date.today()-timedelta(days=days_back) if days_back<9999 else date(2020,1,1)
trades = db.get_trades_daterange(start, date.today())
debriefs = db.get_all_debriefs()
if trades.empty: st.info("No trades yet. Import via Journal page."); st.stop()
if seg!="All" and "segment" in trades.columns: trades = trades[trades["segment"]==seg]
if instr: trades = trades[trades["instrument"].str.contains(instr,case=False,na=False)]
if pend and "debrief_done" in trades.columns: trades = trades[~trades["debrief_done"].fillna(False)]
trades["net_pnl"] = pd.to_numeric(trades["net_pnl"],errors="coerce").fillna(0)
if not debriefs.empty: trades = trades.merge(debriefs[["trade_id","setup_type","emotion_score_entry","exit_type"]].rename(columns={"setup_type":"Setup","emotion_score_entry":"Emo","exit_type":"Exit"}),on="trade_id",how="left")
st.markdown(f'<div class="sec">{len(trades)} trades · Total P&L: {"+"if trades["net_pnl"].sum()>=0 else ""}₹{trades["net_pnl"].sum():,.0f}</div>', unsafe_allow_html=True)
disp = [c for c in ["session_date","instrument","segment","quantity","avg_buy_price","avg_sell_price","net_pnl","holding_duration_mins","debrief_done","Setup","Emo","Exit"] if c in trades.columns]
show = trades[disp].copy()
for c in ["avg_buy_price","avg_sell_price"]:
    if c in show.columns: show[c] = pd.to_numeric(show[c],errors="coerce").apply(lambda x:f"₹{x:,.2f}" if pd.notna(x) else "—")
if "net_pnl" in show.columns: show["net_pnl"] = pd.to_numeric(show["net_pnl"],errors="coerce").apply(lambda x:f"+₹{x:,.0f}" if x>=0 else f"-₹{abs(x):,.0f}" if pd.notna(x) else "—")
if "holding_duration_mins" in show.columns: show["holding_duration_mins"] = show["holding_duration_mins"].apply(lambda x:f"{int(x)}m" if pd.notna(x) else "—")
show.columns = [c.replace("_"," ").title() for c in show.columns]
show = show.rename(columns={"Debrief Done":"✓","Holding Duration Mins":"Held","Net Pnl":"Net P&L","Avg Buy Price":"Buy","Avg Sell Price":"Sell"})
st.dataframe(show, use_container_width=True, hide_index=True, height=600)

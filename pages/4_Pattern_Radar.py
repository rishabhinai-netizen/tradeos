import streamlit as st, pandas as pd
import db
from kotak import detect_patterns_from_trades
st.set_page_config(page_title="Pattern Radar · TradeOS", page_icon="🔍", layout="wide")
st.markdown("<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');html,body,[class*=\"css\"]{font-family:'DM Sans',sans-serif;}.block-container{padding:1.5rem 2rem;max-width:1200px;}.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}.pc{background:white;border:1px solid #E8E6E1;border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:10px;}.pd{border-left:4px solid #EF4444;}.pw{border-left:4px solid #F59E0B;}.pi{border-left:4px solid #3B82F6;}</style>", unsafe_allow_html=True)
st.markdown("## 🔍 Pattern Radar")
st.caption("AI-detected behavioral patterns in your trading history")
if st.button("🔄 Re-analyse Now", type="primary"):
    with st.spinner("Analysing..."):
        at=db.get_all_trades(); ad=db.get_all_debriefs()
        pats=detect_patterns_from_trades(at,ad)
        for p in pats: db.upsert_pattern(p)
        st.success(f"Found {len(pats)} patterns"); st.rerun()
pdf = db.get_patterns()
dc = len(pdf[pdf["severity"]=="danger"]) if not pdf.empty else 0
wc = len(pdf[pdf["severity"]=="warning"]) if not pdf.empty else 0
ic = len(pdf[pdf["severity"]=="info"]) if not pdf.empty else 0
c1,c2,c3 = st.columns(3)
with c1: st.metric("🔴 Danger", dc)
with c2: st.metric("🟡 Warning", wc)
with c3: st.metric("🔵 Info", ic)
if pdf.empty:
    st.info("No patterns yet. Import trades and run the analyser. Minimum ~10 trades needed.")
else:
    so = {"danger":0,"warning":1,"info":2}
    pdf["so"] = pdf["severity"].map(so).fillna(3)
    pdf = pdf.sort_values("so")
    st.markdown('<div class="sec">Active patterns</div>', unsafe_allow_html=True)
    for _,p in pdf.iterrows():
        sev=p.get("severity","info")
        pnl=p.get("avg_pnl_impact") or 0; tot=p.get("total_pnl_impact") or 0
        imp=f"Avg impact: ₹{pnl:+,.0f} · Total: ₹{tot:+,.0f}" if pnl else ""
        sbadge={"danger":"🔴 DANGER","warning":"🟡 WARNING","info":"🔵 INFO"}.get(sev,"")
        col1,col2 = st.columns([5,1])
        with col1:
            st.markdown(f'<div class="pc p{sev[0]}"><div style=\"margin-bottom:6px\"><strong>{sbadge}</strong> &nbsp; {p.get("pattern_type","")} &nbsp; <span style=\"font-size:11px;color:#888\">{p.get("occurrence_count",0)} times · Last: {p.get("last_seen","")}</span></div><div style=\"font-size:13px;color:#444;margin-bottom:4px\">{p.get("description","")}</div><div style=\"font-size:12px;color:#888\">{p.get("detail_text","")}</div>{f'<div style="font-size:12px;color:#B91C1C;font-family:monospace">{imp}</div>' if imp else ""}</div>', unsafe_allow_html=True)
        with col2:
            if st.button("Dismiss", key=f"ack_{p['pattern_id']}"): db.acknowledge_pattern(p["pattern_id"]); st.rerun()
st.markdown('<div class="sec">Win rate by mental state</div>', unsafe_allow_html=True)
sessions=db.get_sessions(limit=200)
if not sessions.empty and "mental_state" in sessions.columns:
    at=db.get_all_trades()
    if not at.empty:
        at["net_pnl"]=pd.to_numeric(at["net_pnl"],errors="coerce").fillna(0)
        mg=at.merge(sessions[["session_id","mental_state"]],on="session_id",how="left")
        mg=mg[mg["mental_state"].notna()]
        if not mg.empty:
            ms=mg.groupby("mental_state").agg(Trades=("net_pnl","count"),Win_Rate=("net_pnl",lambda x:f"{(x>0).sum()/len(x)*100:.1f}%"),Avg_PnL=("net_pnl",lambda x:f"₹{x.mean():+,.0f}"),Total_PnL=("net_pnl",lambda x:f"₹{x.sum():+,.0f}")).reset_index()
            ms.columns=["Mental State","Trades","Win Rate","Avg P&L","Total P&L"]
            st.dataframe(ms,use_container_width=True,hide_index=True)

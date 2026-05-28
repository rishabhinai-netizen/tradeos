import streamlit as st, pandas as pd, plotly.graph_objects as go, plotly.express as px
from datetime import date, timedelta
import db

st.set_page_config(page_title="Analytics · TradeOS", page_icon="📈", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.block-container{padding:1.5rem 2rem;max-width:1400px;}
.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}
.mcard{background:#fff;border:1px solid #E8E6E1;border-radius:12px;padding:1rem 1.25rem;}
.mlabel{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;}
.mval{font-size:22px;font-weight:600;font-family:'DM Mono',monospace;}
.green{color:#1A7A3C;}.red{color:#B91C1C;}.amber{color:#B45309;}
</style>""", unsafe_allow_html=True)

CHART = dict(plot_bgcolor="white", paper_bgcolor="white", font=dict(family="DM Sans", size=11), margin=dict(l=0,r=80,t=20,b=0))

st.markdown("## 📈 Analytics")
c1,c2,c3 = st.columns([2,2,1])
with c1: period = st.selectbox("Period",["Last 30 days","Last 90 days","FY 2026-27","FY 2025-26","All time"])
with c2: seg = st.selectbox("Segment",["All","FUT_COMMODITY","FUT_EQUITY","FUT_INDEX","EQ_INTRADAY","EQ_DELIVERY"])
with c3:
    if st.button("🔄 Recompute"): db.recompute_daily_metrics(); st.rerun()

today = date.today()
pm = {"Last 30 days":today-timedelta(days=30),"Last 90 days":today-timedelta(days=90),"FY 2025-26":date(2025,4,1),"FY 2026-27":date(2026,4,1),"All time":date(2024,1,1)}
trades = db.get_trades_daterange(pm[period], today)
debriefs = db.get_all_debriefs()
if trades.empty: st.info("No trade data yet."); st.stop()
if seg != "All" and "segment" in trades.columns: trades = trades[trades["segment"]==seg]
trades["net_pnl"] = pd.to_numeric(trades["net_pnl"], errors="coerce").fillna(0)
trades["session_date"] = pd.to_datetime(trades["session_date"]).dt.date
closed = trades[~trades.get("is_open", pd.Series([False]*len(trades))).fillna(False)]
wins = closed[closed["net_pnl"]>0]; losses = closed[closed["net_pnl"]<0]
wr = len(wins)/len(closed)*100 if len(closed)>0 else 0
aw = float(wins["net_pnl"].mean()) if len(wins)>0 else 0
al = float(losses["net_pnl"].mean()) if len(losses)>0 else 0
payoff = abs(aw/al) if al!=0 else 0
pf = abs(wins["net_pnl"].sum()/losses["net_pnl"].sum()) if losses["net_pnl"].sum()!=0 else 0
total = closed["net_pnl"].sum()

# Key metrics
cs = st.columns(6)
for col,(lbl,val,clr) in zip(cs,[
    ("Net P&L",f'{"+"if total>=0 else ""}₹{abs(total):,.0f}',"green" if total>=0 else "red"),
    ("Win Rate",f"{wr:.1f}%","green" if wr>=50 else "red"),
    ("Payoff",f"{payoff:.2f}","green" if payoff>=1.5 else "amber" if payoff>=1 else "red"),
    ("Prof Factor",f"{pf:.2f}","green" if pf>=1.5 else "amber"),
    ("Avg Win",f"₹{aw:,.0f}","green"),
    ("Avg Loss",f"₹{abs(al):,.0f}","red"),
]):
    with col: st.markdown(f'<div class="mcard"><div class="mlabel">{lbl}</div><div class="mval {clr}">{val}</div></div>', unsafe_allow_html=True)

# Cumulative P&L
st.markdown('<div class="sec">Cumulative P&L</div>', unsafe_allow_html=True)
dp = closed.groupby("session_date")["net_pnl"].sum().reset_index().sort_values("session_date")
dp["cum"] = dp["net_pnl"].cumsum()
fig = go.Figure(go.Scatter(x=dp["session_date"], y=dp["cum"], mode="lines", fill="tozeroy",
    line=dict(color="#042C53", width=2), fillcolor="rgba(4,44,83,0.07)",
    hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>"))
fig.update_layout(height=240, **{**CHART, "margin":dict(l=0,r=0,t=10,b=0)},
    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#F0EEE9", tickprefix="₹", tickformat=",.0f"),
    hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

col_l, col_r = st.columns(2)

with col_l:
    # Win rate by setup
    if not debriefs.empty and "setup_type" in debriefs.columns:
        st.markdown('<div class="sec">Win rate by setup</div>', unsafe_allow_html=True)
        merged = closed.merge(debriefs[["trade_id","setup_type"]], on="trade_id", how="inner")
        merged = merged[merged["setup_type"].notna()]
        if not merged.empty:
            ss = merged.groupby("setup_type").agg(c=("net_pnl","count"), wr=("net_pnl", lambda x:(x>0).sum()/len(x)*100)).reset_index().sort_values("wr")
            fig2 = go.Figure(go.Bar(x=ss["wr"], y=ss["setup_type"], orientation="h",
                marker_color=["#10B981" if v>=50 else "#EF4444" for v in ss["wr"]],
                text=[f"{v:.0f}% ({int(c)})" for v,c in zip(ss["wr"],ss["c"])], textposition="outside"))
            fig2.update_layout(height=220, **CHART, xaxis=dict(showgrid=True, gridcolor="#F0EEE9", range=[0,115]), yaxis=dict(showgrid=False))
            st.plotly_chart(fig2, use_container_width=True)

with col_r:
    # P&L by segment
    if "segment" in closed.columns:
        st.markdown('<div class="sec">P&L by segment</div>', unsafe_allow_html=True)
        sp = closed.groupby("segment")["net_pnl"].sum().reset_index().sort_values("net_pnl")
        fig3 = go.Figure(go.Bar(x=sp["net_pnl"], y=sp["segment"].str.replace("_"," "), orientation="h",
            marker_color=["#EF4444" if v<0 else "#10B981" for v in sp["net_pnl"]],
            text=[f"₹{v:+,.0f}" for v in sp["net_pnl"]], textposition="outside"))
        fig3.update_layout(height=220, **CHART, xaxis=dict(showgrid=True, gridcolor="#F0EEE9"), yaxis=dict(showgrid=False))
        st.plotly_chart(fig3, use_container_width=True)

col_l2, col_r2 = st.columns(2)

with col_l2:
    # Emotion vs P&L
    if not debriefs.empty and "emotion_score_entry" in debriefs.columns:
        st.markdown('<div class="sec">Emotion at entry vs P&L</div>', unsafe_allow_html=True)
        m2 = closed.merge(debriefs[["trade_id","emotion_score_entry"]], on="trade_id", how="inner")
        m2["emotion_score_entry"] = pd.to_numeric(m2["emotion_score_entry"], errors="coerce")
        m2 = m2[m2["emotion_score_entry"].notna()]
        if not m2.empty:
            es = m2.groupby("emotion_score_entry").agg(ap=("net_pnl","mean"), wr=("net_pnl", lambda x:(x>0).sum()/len(x)*100), c=("net_pnl","count")).reset_index()
            el = {1:"1·Calm",2:"2·Eager",3:"3·Neutral",4:"4·FOMO",5:"5·Panic"}
            fig4 = go.Figure(go.Bar(x=[el.get(int(e),str(e)) for e in es["emotion_score_entry"]], y=es["ap"],
                marker_color=["#10B981" if v>=0 else "#EF4444" for v in es["ap"]],
                text=[f"₹{v:+,.0f} | {r:.0f}% WR" for v,r in zip(es["ap"],es["wr"])], textposition="outside"))
            fig4.update_layout(height=240, **{**CHART,"margin":dict(l=0,r=0,t=20,b=0)},
                yaxis=dict(showgrid=True,gridcolor="#F0EEE9",tickprefix="₹"), xaxis=dict(showgrid=False))
            st.plotly_chart(fig4, use_container_width=True)
        else: st.info("Debrief more trades.")

with col_r2:
    # Holding duration vs P&L (PEAD trades)
    if not debriefs.empty:
        st.markdown('<div class="sec">Holding duration vs P&L (PEAD trades)</div>', unsafe_allow_html=True)
        pead_d = debriefs[debriefs["setup_type"]=="News/Event"][["trade_id"]]
        if not pead_d.empty:
            m3 = closed.merge(pead_d, on="trade_id", how="inner")
            m3["holding_duration_mins"] = pd.to_numeric(m3.get("holding_duration_mins"), errors="coerce")
            m3 = m3[m3["holding_duration_mins"].notna() & (m3["holding_duration_mins"]>0)]
            if len(m3) >= 3:
                fig5 = go.Figure(go.Scatter(x=m3["holding_duration_mins"], y=m3["net_pnl"],
                    mode="markers", marker=dict(size=10, color=["#10B981" if v>0 else "#EF4444" for v in m3["net_pnl"]], opacity=0.8),
                    text=m3["instrument"], hovertemplate="<b>%{text}</b><br>Held: %{x}m<br>P&L: ₹%{y:,.0f}<extra></extra>"))
                fig5.add_hline(y=0, line_color="#ccc")
                fig5.add_vline(x=5, line_dash="dash", line_color="#F59E0B", annotation_text="5 min")
                fig5.update_layout(height=240, **{**CHART,"margin":dict(l=0,r=0,t=20,b=0)},
                    xaxis=dict(title="Minutes held", showgrid=True, gridcolor="#F0EEE9"),
                    yaxis=dict(title="Net P&L", showgrid=True, gridcolor="#F0EEE9", tickprefix="₹"))
                st.plotly_chart(fig5, use_container_width=True)
            else: st.info("Need more PEAD trades.")
        else: st.info("No PEAD trades yet.")

# Monthly P&L
st.markdown('<div class="sec">Monthly P&L</div>', unsafe_allow_html=True)
at = db.get_all_trades()
if not at.empty:
    at["net_pnl"] = pd.to_numeric(at["net_pnl"],errors="coerce").fillna(0)
    at["month"] = pd.to_datetime(at["session_date"]).dt.to_period("M").astype(str)
    mon = at.groupby("month")["net_pnl"].sum().reset_index()
    fig6 = go.Figure(go.Bar(x=mon["month"], y=mon["net_pnl"],
        marker_color=["#10B981" if v>=0 else "#EF4444" for v in mon["net_pnl"]],
        text=[f"₹{v:+,.0f}" for v in mon["net_pnl"]], textposition="outside"))
    fig6.update_layout(height=220, **{**CHART,"margin":dict(l=0,r=0,t=10,b=0)},
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True,gridcolor="#F0EEE9",tickprefix="₹"))
    st.plotly_chart(fig6, use_container_width=True)

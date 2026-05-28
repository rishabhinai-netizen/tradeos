import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime
import db

st.set_page_config(page_title="TradeOS", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.block-container{padding:1.5rem 2rem;max-width:1400px;}
.mcard{background:#fff;border:1px solid #E8E6E1;border-radius:12px;padding:1rem 1.25rem;}
.mlabel{font-size:11px;color:#888;letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px;}
.mval{font-size:22px;font-weight:600;font-family:'DM Mono',monospace;}
.msub{font-size:12px;color:#888;margin-top:2px;}
.green{color:#1A7A3C;}.red{color:#B91C1C;}
.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}
.alert-w{background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;color:#92400E;}
.alert-d{background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px;color:#991B1B;}
.empty-state{background:#F9F8F6;border:1px dashed #D4D0C8;border-radius:12px;padding:2rem;text-align:center;color:#888;}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 📊 TradeOS")
    st.caption("Personal Trading OS · YIPQH")
    st.divider()
    st.page_link("app.py", label="🏠 Live Cockpit")
    st.page_link("pages/1_Journal.py", label="📓 Journal Today")
    st.page_link("pages/2_Trade_Log.py", label="📋 Trade Log")
    st.page_link("pages/3_Analytics.py", label="📈 Analytics")
    st.page_link("pages/4_Pattern_Radar.py", label="🔍 Pattern Radar")
    st.page_link("pages/5_Playbook.py", label="📚 Playbook")
    st.page_link("pages/6_Weekly_Report.py", label="📆 Weekly Report")
    st.divider()
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear(); st.rerun()

today = date.today()
st.markdown(f"## Live Cockpit")
st.caption(f"{today.strftime('%A, %d %B %Y')} · {datetime.now().strftime('%H:%M')}")

# --- Safe DB calls — never crash on startup ---
try:
    positions_df = db.get_latest_positions()
except Exception:
    positions_df = pd.DataFrame()

try:
    metrics = db.get_latest_metrics()
except Exception:
    metrics = None

try:
    patterns_df = db.get_patterns()
except Exception:
    patterns_df = pd.DataFrame()

# Alerts
if not positions_df.empty and "days_to_expiry" in positions_df.columns:
    expiring = positions_df[positions_df["days_to_expiry"].notna() & (positions_df["days_to_expiry"]<=2)]
    for _,p in expiring.iterrows():
        dte = int(p["days_to_expiry"]); pnl = float(p.get("unrealized_pnl",0) or 0)
        label = "TODAY" if dte==0 else "TOMORROW"
        cls = "alert-d" if dte<=1 else "alert-w"
        st.markdown(f'<div class="{cls}">⚠️ <strong>{p.get("display_name","")}</strong> expires {label} · P&L: {"+"}₹{abs(pnl):,.0f}</div>', unsafe_allow_html=True)

if not patterns_df.empty:
    for _,pat in patterns_df[patterns_df["severity"]=="danger"].iterrows():
        st.markdown(f'<div class="alert-d">🔴 <strong>{pat["pattern_type"]}</strong> — {pat["description"]}</div>', unsafe_allow_html=True)

# Metrics
st.markdown('<div class="sec">Portfolio Overview</div>', unsafe_allow_html=True)
total_invested = pd.to_numeric(positions_df.get("invested_value",pd.Series([])), errors="coerce").sum() if not positions_df.empty else 0
total_unreal = pd.to_numeric(positions_df.get("unrealized_pnl",pd.Series([])), errors="coerce").sum() if not positions_df.empty else 0
pnl_td = metrics.get("pnl_td",0) or 0 if metrics else 0
pnl_fy = metrics.get("pnl_fy",0) or 0 if metrics else 0
wr30 = metrics.get("win_rate_30d") if metrics else None

def fp(v): return f"+₹{abs(v):,.0f}" if v>=0 else f"-₹{abs(v):,.0f}"
def fc(v): return "green" if v>=0 else "red"

c1,c2,c3,c4,c5 = st.columns(5)
mdata = [
    ("Deployed", f"₹{total_invested:,.0f}", "All positions", ""),
    ("Unrealized P&L", fp(total_unreal), f"{total_unreal/total_invested*100:.1f}%" if total_invested else "—", fc(total_unreal)),
    ("Today's P&L", fp(pnl_td), "Net realized", fc(pnl_td)),
    ("FY P&L", fp(pnl_fy), "Net realized", fc(pnl_fy)),
    ("Win Rate 30d", f"{wr30*100:.1f}%" if wr30 else "—", "Last 30 days", ""),
]
for col,(lbl,val,sub,color) in zip([c1,c2,c3,c4,c5],mdata):
    with col: st.markdown(f'<div class="mcard"><div class="mlabel">{lbl}</div><div class="mval {color}">{val}</div><div class="msub">{sub}</div></div>', unsafe_allow_html=True)

# Positions
st.markdown('<div class="sec">Open Positions</div>', unsafe_allow_html=True)
if not positions_df.empty:
    show = positions_df.copy()
    for c in ["invested_value","market_value","avg_cost","current_price"]:
        if c in show.columns: show[c] = pd.to_numeric(show[c],errors="coerce").apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else "—")
    if "unrealized_pnl" in show.columns:
        show["unrealized_pnl"] = pd.to_numeric(show["unrealized_pnl"],errors="coerce").apply(lambda x: f"+₹{x:,.0f}" if (pd.notna(x) and x>=0) else (f"-₹{abs(x):,.0f}" if pd.notna(x) else "—"))
    if "unrealized_pnl_pct" in show.columns:
        show["unrealized_pnl_pct"] = pd.to_numeric(show["unrealized_pnl_pct"],errors="coerce").apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    if "days_to_expiry" in show.columns:
        show["days_to_expiry"] = show["days_to_expiry"].apply(lambda x: f"{int(x)}d" if pd.notna(x) else "—")
    disp = [c for c in ["display_name","segment","quantity","avg_cost","current_price","unrealized_pnl","unrealized_pnl_pct","days_to_expiry"] if c in show.columns]
    st.dataframe(show[disp].rename(columns={"display_name":"Instrument","unrealized_pnl":"P&L","unrealized_pnl_pct":"P&L %","days_to_expiry":"DTE","avg_cost":"Avg Cost","current_price":"LTP"}), use_container_width=True, hide_index=True)

    chart = positions_df.copy()
    chart["unrealized_pnl"] = pd.to_numeric(chart["unrealized_pnl"],errors="coerce").fillna(0)
    chart["name"] = (chart.get("ticker",chart.get("display_name",""))).apply(lambda x: str(x)[:14])
    chart = chart.sort_values("unrealized_pnl")
    fig = go.Figure(go.Bar(x=chart["unrealized_pnl"], y=chart["name"], orientation="h",
        marker_color=["#EF4444" if v<0 else "#10B981" for v in chart["unrealized_pnl"]],
        text=[f"₹{v:+,.0f}" for v in chart["unrealized_pnl"]], textposition="outside"))
    fig.update_layout(height=max(180,len(chart)*34), margin=dict(l=0,r=80,t=10,b=10),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(showgrid=True,gridcolor="#F0EEE9",zeroline=True,zerolinecolor="#ccc"),
        yaxis=dict(showgrid=False), font=dict(family="DM Sans",size=12))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown('<div class="empty-state">📭 No positions yet.<br><span style="font-size:13px">Import your holdings CSV via the <strong>Journal</strong> page to see positions here.</span></div>', unsafe_allow_html=True)

# Pending debriefs
try:
    pending = db.get_trades(debrief_pending=True, limit=5)
    if not pending.empty:
        st.markdown('<div class="sec">Pending Debriefs</div>', unsafe_allow_html=True)
        st.warning(f"**{len(pending)}** trade(s) waiting for debrief. Say **'Journal Today'** to Claude — it asks all questions and pushes everything here automatically.")
except Exception:
    pass

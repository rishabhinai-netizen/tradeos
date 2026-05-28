import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
import db

st.set_page_config(page_title="Position Review · TradeOS", page_icon="🔬", layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.block-container{padding:1.5rem 2rem;max-width:1400px;}
.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}
.mcard{background:#fff;border:1px solid #E8E6E1;border-radius:12px;padding:1rem 1.25rem;}
.mlabel{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;}
.mval{font-size:20px;font-weight:600;font-family:'DM Mono',monospace;}
.green{color:#1A7A3C;}.red{color:#B91C1C;}.amber{color:#B45309;}.blue{color:#042C53;}
.verdict-sh{background:#EAF3DE;color:#1A7A3C;font-size:11px;font-weight:600;padding:2px 10px;border-radius:4px;}
.verdict-h{background:#E6F1FB;color:#042C53;font-size:11px;font-weight:600;padding:2px 10px;border-radius:4px;}
.verdict-w{background:#FFFBEB;color:#B45309;font-size:11px;font-weight:600;padding:2px 10px;border-radius:4px;}
.verdict-e{background:#FEF2F2;color:#B91C1C;font-size:11px;font-weight:600;padding:2px 10px;border-radius:4px;}
.hint{background:#EBF5FF;border:1px solid #BFDBFE;border-radius:8px;padding:10px 14px;font-size:13px;color:#1E40AF;margin-bottom:1rem;}
</style>""", unsafe_allow_html=True)

st.markdown("## 🔬 Position Review")
st.caption("Daily technofunda scoring of all open positions — updated automatically after each journal session")

st.markdown("""<div class="hint">
💡 <strong>This page updates automatically.</strong> After each "Journal Today" session, Claude researches all open positions, scores them on 10+ parameters, and pushes the analysis here. Track how your thesis evolves daily.
</div>""", unsafe_allow_html=True)

# ── Date selector ─────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    selected_date = st.date_input("Analysis date", value=date.today(), max_value=date.today())
with col2:
    show_only = st.selectbox("Filter", ["All", "Strong Hold", "Hold", "Watch", "Exit Plan Needed"])
with col3:
    compare_prev = st.checkbox("Compare with previous analysis", value=False)

# ── Load data ─────────────────────────────────────────────────────────────────
def load_analysis(d):
    try:
        r = db.sb().table("tl_position_analysis").select("*").eq("analysis_date", str(d)).order("score_composite", desc=True).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def load_prev_analysis(d):
    try:
        r = db.sb().table("tl_position_analysis").select("analysis_date,instrument,score_composite,verdict,unrealized_pnl").lt("analysis_date", str(d)).order("analysis_date", desc=True).limit(200).execute()
        df = pd.DataFrame(r.data) if r.data else pd.DataFrame()
        if df.empty: return pd.DataFrame()
        return df.sort_values("analysis_date").drop_duplicates("instrument", keep="last")
    except Exception:
        return pd.DataFrame()

df = load_analysis(selected_date)

# Fallback — find latest available date
if df.empty:
    try:
        r = db.sb().table("tl_position_analysis").select("analysis_date").order("analysis_date", desc=True).limit(1).execute()
        if r.data:
            latest = r.data[0]["analysis_date"]
            df = load_analysis(latest)
            selected_date = pd.to_datetime(latest).date()
            st.info(f"No analysis for selected date — showing latest available: {latest}")
    except Exception:
        pass

if df.empty:
    st.markdown('<div style="background:#F9F8F6;border:1px dashed #D4D0C8;border-radius:12px;padding:2rem;text-align:center;color:#888;">No position analysis yet. Say <strong>"Journal Today"</strong> to Claude — it will research all your open positions and push analysis here.</div>', unsafe_allow_html=True)
    st.stop()

prev_df = load_prev_analysis(selected_date) if compare_prev else pd.DataFrame()

# Filter
if show_only != "All":
    df = df[df["verdict"] == show_only]

# ── Portfolio summary metrics ─────────────────────────────────────────────────
st.markdown('<div class="sec">Portfolio overview</div>', unsafe_allow_html=True)
total_unreal = pd.to_numeric(df["unrealized_pnl"], errors="coerce").sum()
avg_comp = pd.to_numeric(df["score_composite"], errors="coerce").mean()
n_strong = len(df[df["verdict"] == "Strong Hold"])
n_exit = len(df[df["verdict"].isin(["Exit Plan Needed", "Exit", "Reduce"])])

mc1, mc2, mc3, mc4, mc5 = st.columns(5)
def metric_card(col, label, val, color=""):
    with col: st.markdown(f'<div class="mcard"><div class="mlabel">{label}</div><div class="mval {color}">{val}</div></div>', unsafe_allow_html=True)
metric_card(mc1, "Positions", len(df))
metric_card(mc2, "Unrealized P&L", f'{"+" if total_unreal>=0 else ""}₹{abs(total_unreal)/100000:.1f}L', "green" if total_unreal>=0 else "red")
metric_card(mc3, "Avg composite score", f"{avg_comp:.1f}/10")
metric_card(mc4, "Strong hold", n_strong, "green")
metric_card(mc5, "Need exit plan", n_exit, "red" if n_exit > 0 else "")

# ── Score chart ───────────────────────────────────────────────────────────────
st.markdown('<div class="sec">Composite score by position</div>', unsafe_allow_html=True)
chart_df = df.sort_values("score_composite")
colors = {"Strong Hold":"#10B981","Hold":"#378ADD","Watch":"#F59E0B","Exit Plan Needed":"#EF4444","Exit":"#EF4444","Reduce":"#F97316","Add":"#059669"}
bar_colors = [colors.get(v,"#888") for v in chart_df["verdict"]]

fig = go.Figure(go.Bar(
    x=chart_df["score_composite"],
    y=chart_df["instrument"],
    orientation="h",
    marker_color=bar_colors,
    text=[f"{s}/10 · {v}" for s,v in zip(chart_df["score_composite"], chart_df["verdict"])],
    textposition="outside"
))
fig.update_layout(height=max(300, len(chart_df)*36), margin=dict(l=0,r=200,t=10,b=0),
    plot_bgcolor="white", paper_bgcolor="white",
    xaxis=dict(range=[0,12], showgrid=True, gridcolor="#F0EEE9"),
    yaxis=dict(showgrid=False), font=dict(family="DM Sans", size=12))
st.plotly_chart(fig, use_container_width=True)

# ── Detailed cards ────────────────────────────────────────────────────────────
st.markdown('<div class="sec">Detailed analysis</div>', unsafe_allow_html=True)

verdict_badge = {
    "Strong Hold": "verdict-sh", "Hold": "verdict-h", "Watch": "verdict-w",
    "Exit Plan Needed": "verdict-e", "Exit": "verdict-e", "Reduce": "verdict-e", "Add": "verdict-sh"
}

for _, row in df.sort_values("score_composite", ascending=False).iterrows():
    unreal = float(row.get("unrealized_pnl", 0) or 0)
    unreal_pct = float(row.get("unrealized_pnl_pct", 0) or 0)
    comp = row.get("score_composite") or 0
    fund = row.get("score_fundamental_overall") or 0
    tech = row.get("score_technical_overall") or 0
    verdict = row.get("verdict", "Watch")
    badge_cls = verdict_badge.get(verdict, "verdict-w")
    pnl_color = "green" if unreal >= 0 else "red"
    pnl_str = f'{"+" if unreal>=0 else ""}₹{abs(unreal)/1000:.1f}K ({unreal_pct:+.1f}%)'

    # Score change vs previous
    score_delta = ""
    if not prev_df.empty and row["instrument"] in prev_df["instrument"].values:
        prev_row = prev_df[prev_df["instrument"] == row["instrument"]].iloc[0]
        delta = int(comp) - int(prev_row.get("score_composite") or 0)
        if delta > 0: score_delta = f" ↑{delta}"
        elif delta < 0: score_delta = f" ↓{abs(delta)}"

    with st.expander(f"**{row.get('display_name', row['instrument'])}** · Score {comp}/10{score_delta} · {pnl_str}", expanded=(verdict in ["Exit Plan Needed","Exit"])):

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="mlabel">Verdict</div><span class="{badge_cls}">{verdict}</span>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="mlabel">Fundamental</div><div style="font-size:16px;font-weight:600">{fund}/10</div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="mlabel">Technical</div><div style="font-size:16px;font-weight:600">{tech}/10</div>', unsafe_allow_html=True)
        with c4:
            sl = row.get("suggested_sl"); tgt = row.get("suggested_target")
            sl_str = f"₹{float(sl):,.0f}" if sl else "—"
            tgt_str = f"₹{float(tgt):,.0f}" if tgt else "—"
            st.markdown(f'<div class="mlabel">SL / Target</div><div style="font-size:13px;font-weight:500"><span class="red">{sl_str}</span> / <span class="green">{tgt_str}</span></div>', unsafe_allow_html=True)

        # Score breakdown bar
        scores = {
            "Revenue": row.get("score_revenue_growth") or 0,
            "Margins": row.get("score_margin_quality") or 0,
            "Valuation": row.get("score_valuation") or 0,
            "Balance Sheet": row.get("score_balance_sheet") or 0,
            "Mgmt": row.get("score_management") or 0,
            "Trend": row.get("score_trend") or 0,
            "Momentum": row.get("score_momentum") or 0,
            "Volume": row.get("score_volume") or 0,
            "RS Rank": row.get("score_rs_rank") or 0,
        }
        fig_score = go.Figure(go.Bar(
            x=list(scores.keys()), y=list(scores.values()),
            marker_color=["#10B981" if v>=7 else "#F59E0B" if v>=5 else "#EF4444" for v in scores.values()],
            text=[str(v) for v in scores.values()], textposition="outside"
        ))
        fig_score.update_layout(height=180, margin=dict(l=0,r=0,t=20,b=0),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(showgrid=False), yaxis=dict(range=[0,12], showgrid=True, gridcolor="#F0EEE9"),
            font=dict(family="DM Sans", size=11))
        st.plotly_chart(fig_score, use_container_width=True)

        # Thesis and context
        ta, tb = st.columns(2)
        with ta:
            if row.get("recent_result"): st.markdown(f"**Q4 Result:** {row['recent_result']}")
            if row.get("key_catalysts"): st.markdown(f"**Catalysts:** {row['key_catalysts']}")
            if row.get("thesis_current"): st.markdown(f"**Thesis:** {row['thesis_current']}")
        with tb:
            if row.get("key_risks"): st.markdown(f"**Risks:** {row['key_risks']}")
            if row.get("recent_news"): st.markdown(f"**Latest:** {row['recent_news']}")

        st.markdown(f'<div style="background:#F9F8F6;border-left:3px solid #378ADD;padding:8px 12px;margin-top:8px;font-size:13px;border-radius:0 8px 8px 0;">'
                    f'💡 <strong>Verdict:</strong> {row.get("verdict_reason","")}</div>', unsafe_allow_html=True)

# ── Thesis change tracker ─────────────────────────────────────────────────────
st.markdown('<div class="sec">Historical score tracker</div>', unsafe_allow_html=True)
try:
    r = db.sb().table("tl_position_analysis").select("analysis_date,instrument,score_composite,verdict,unrealized_pnl_pct").order("analysis_date", desc=False).execute()
    hist = pd.DataFrame(r.data) if r.data else pd.DataFrame()
    if not hist.empty and len(hist["analysis_date"].unique()) > 1:
        hist["analysis_date"] = pd.to_datetime(hist["analysis_date"])
        hist["score_composite"] = pd.to_numeric(hist["score_composite"], errors="coerce")
        instruments = hist["instrument"].unique().tolist()
        sel_instr = st.multiselect("Select positions to track", instruments, default=instruments[:6])
        if sel_instr:
            fig_hist = go.Figure()
            for instr in sel_instr:
                sub = hist[hist["instrument"]==instr].sort_values("analysis_date")
                fig_hist.add_trace(go.Scatter(x=sub["analysis_date"], y=sub["score_composite"],
                    mode="lines+markers", name=instr, hovertemplate=f"<b>{instr}</b><br>%{{x}}<br>Score: %{{y}}<extra></extra>"))
            fig_hist.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0),
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(showgrid=False), yaxis=dict(range=[0,11], showgrid=True, gridcolor="#F0EEE9", title="Score"),
                legend=dict(orientation="h", y=-0.15), font=dict(family="DM Sans", size=11))
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Historical tracking starts from the second day of analysis. Come back tomorrow.")
except Exception:
    st.info("Historical tracking available after multiple analysis days.")

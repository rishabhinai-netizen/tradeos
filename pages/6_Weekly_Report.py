import streamlit as st, pandas as pd, json
from datetime import date, timedelta
import anthropic
import db
st.set_page_config(page_title="Weekly Report · TradeOS", page_icon="📆", layout="wide")
st.markdown("<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');html,body,[class*=\"css\"]{font-family:'DM Sans',sans-serif;}.block-container{padding:1.5rem 2rem;max-width:900px;}.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}.rbox{background:white;border:1px solid #E8E6E1;border-radius:12px;padding:1.5rem 2rem;line-height:1.7;}</style>", unsafe_allow_html=True)
st.markdown("## 📆 Weekly Report")
st.caption("AI-generated analysis of your trading week")
c1,c2=st.columns([2,3])
with c1:
    we=st.date_input("Week ending",value=date.today())
    ws=we-timedelta(days=6)
    st.caption(f"{ws.strftime('%d %b')} → {we.strftime('%d %b %Y')}")
with c2:
    gen=st.button("✨ Generate Weekly Report",type="primary",use_container_width=True)
if gen:
    trades=db.get_trades_daterange(ws,we); debriefs=db.get_all_debriefs()
    patterns=db.get_patterns(); playbook=db.get_playbook()
    if trades.empty: st.warning("No trades this week.")
    else:
        trades["net_pnl"]=pd.to_numeric(trades["net_pnl"],errors="coerce").fillna(0)
        closed=trades[~trades.get("is_open",pd.Series([False]*len(trades))).fillna(False)]
        wins=closed[closed["net_pnl"]>0]; losses=closed[closed["net_pnl"]<0]
        wr=len(wins)/len(closed)*100 if len(closed)>0 else 0
        tp=closed["net_pnl"].sum()
        aw=float(wins["net_pnl"].mean()) if len(wins)>0 else 0
        al=float(losses["net_pnl"].mean()) if len(losses)>0 else 0
        payoff=abs(aw/al) if al!=0 else 0
        lessons=[]
        if not debriefs.empty and "lesson_text" in debriefs.columns:
            mg=closed.merge(debriefs[["trade_id","lesson_text"]],on="trade_id",how="left")
            lessons=mg["lesson_text"].dropna().tolist()[:5]
        emo_avg=None
        if not debriefs.empty and "emotion_score_entry" in debriefs.columns:
            mg2=closed.merge(debriefs[["trade_id","emotion_score_entry"]],on="trade_id",how="left")
            emo_avg=round(float(mg2["emotion_score_entry"].mean()),1) if mg2["emotion_score_entry"].notna().any() else None
        ctx={"week":f"{ws} to {we}","total_trades":len(closed),"total_pnl_net":round(float(tp),2),"win_rate_pct":round(wr,1),"avg_win":round(aw,2),"avg_loss":round(al,2),"payoff_ratio":round(payoff,2),"top_winner":closed.nlargest(1,"net_pnl")[["instrument","net_pnl"]].to_dict("records") if len(closed)>0 else [],"top_loser":closed.nsmallest(1,"net_pnl")[["instrument","net_pnl"]].to_dict("records") if len(closed)>0 else [],"lessons_this_week":lessons,"avg_emotion_score":emo_avg,"active_patterns":patterns[["pattern_type","description","severity"]].to_dict("records") if not patterns.empty else [],"playbook_rules":playbook[["rule_type","rule_short","times_followed","times_violated"]].head(8).to_dict("records") if not playbook.empty else []}
        sys="""You are a professional trading performance coach for Rishabh Agrawal — CA, CFE, Lead Fraud Investigator at ICICI HFC, active NSE/MCX trader.
Generate a structured weekly report:
1. Week summary (honest, not just positive)
2. Best trade — what went right
3. Worst mistake — what to learn
4. Key pattern this week
5. One rule to add to playbook
6. One reflection question for next week
7. Focus for next week (one concrete action)
Be direct, use rupee amounts. Reference known patterns (Gold reversal loop, payoff ratio). Write as a trusted advisor who watched every trade."""
        with st.spinner("Claude is analysing your week..."):
            try:
                client=anthropic.Anthropic(api_key=(lambda: (lambda k: k if k else "")(st.secrets["ANTHROPIC_API_KEY"]) if "ANTHROPIC_API_KEY" in st.secrets else "")())
                resp=client.messages.create(model="claude-haiku-4-5-20251001",max_tokens=1500,system=sys,messages=[{"role":"user","content":f"Trading data:\n{json.dumps(ctx,indent=2)}\n\nGenerate my weekly report."}])
                rt=resp.content[0].text
                db.save_insight({"insight_type":"Weekly","week_start":str(ws),"title":f"Weekly Report — {ws.strftime('%d %b')} to {we.strftime('%d %b %Y')}","insight_text":rt,"data_snapshot":json.dumps(ctx)})
                st.markdown('<div class="sec">Weekly Report</div>',unsafe_allow_html=True)
                st.markdown(f'<div class="rbox">{rt.replace(chr(10),"<br>")}</div>',unsafe_allow_html=True)
                c1,c2,c3,c4=st.columns(4)
                with c1: st.metric("Net P&L",f"{'+'if tp>=0 else ''}₹{abs(tp):,.0f}")
                with c2: st.metric("Win Rate",f"{wr:.1f}%")
                with c3: st.metric("Payoff",f"{payoff:.2f}")
                with c4: st.metric("Trades",len(closed))
            except Exception as e: st.error(f"Claude API error: {e}")
st.markdown('<div class="sec">Past reports</div>',unsafe_allow_html=True)
ins=db.get_insights(limit=10)
if not ins.empty:
    wk=ins[ins["insight_type"]=="Weekly"] if "insight_type" in ins.columns else pd.DataFrame()
    if not wk.empty:
        for _,i in wk.iterrows():
            with st.expander(f"📄 {i.get('title','Report')} — {i.get('insight_date','')}"):
                st.markdown(i.get("insight_text",""))
    else: st.info("No past reports yet.")
else: st.info("Generate your first report above.")

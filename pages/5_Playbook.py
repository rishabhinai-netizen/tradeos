import streamlit as st, pandas as pd
import db
st.set_page_config(page_title="Playbook · TradeOS", page_icon="📚", layout="wide")
st.markdown("<style>@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');html,body,[class*=\"css\"]{font-family:'DM Sans',sans-serif;}.block-container{padding:1.5rem 2rem;max-width:1200px;}.sec{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#888;margin:1.5rem 0 .75rem;padding-bottom:6px;border-bottom:1px solid #E8E6E1;}.rc{background:white;border:1px solid #E8E6E1;border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:10px;}</style>", unsafe_allow_html=True)
st.markdown("## 📚 Playbook")
st.caption("Your living rulebook — built from your own trade data")
tab1,tab2 = st.tabs(["Active Rules","Add Rule"])
with tab1:
    rules = db.get_playbook(active_only=True)
    if rules.empty: st.info("No rules yet.")
    else:
        tc = {"Entry":"#10B981","Exit":"#3B82F6","Sizing":"#8B5CF6","Psychology":"#EF4444","Risk":"#F59E0B","Instrument-specific":"#6B7280","Time-based":"#0891B2"}
        for rtype in sorted(rules["rule_type"].unique() if "rule_type" in rules.columns else []):
            st.markdown(f'<div class="sec" style="color:{tc.get(rtype,"#888")}">{rtype}</div>', unsafe_allow_html=True)
            for _,rule in rules[rules["rule_type"]==rtype].iterrows():
                tested=rule.get("times_tested",0) or 0; followed=rule.get("times_followed",0) or 0; violated=rule.get("times_violated",0) or 0
                fr=f"{followed/tested*100:.0f}%" if tested>0 else "—"
                pf=rule.get("pnl_when_followed",0) or 0; pv=rule.get("pnl_when_violated",0) or 0
                pl={1:"🔴 Critical",2:"🟠 High",3:"🟡 Medium",4:"🟢 Low",5:"⚪ Info"}.get(rule.get("priority",3),"")
                c1,c2=st.columns([5,1])
                with c1:
                    st.markdown(f'<div class="rc"><div style=\"margin-bottom:6px\"><span style=\"font-size:11px;background:#F3F4F6;color:#374151;padding:2px 7px;border-radius:4px\">{pl}</span> &nbsp; <strong>{rule.get("rule_short","")}</strong></div><div style=\"font-size:13px;color:#444;line-height:1.6;margin-bottom:8px\">{rule.get("rule_text","")}</div><div style=\"font-size:12px;color:#888;display:flex;gap:16px\"><span>Tested: <strong>{tested}</strong></span><span>Follow rate: <strong>{fr}</strong></span><span>P&L followed: <strong style=\"color:#1A7A3C\">₹{pf:+,.0f}</strong></span><span>P&L violated: <strong style=\"color:#B91C1C\">₹{pv:+,.0f}</strong></span></div>{f'<div style="font-size:11px;color:#888;margin-top:6px">Source: {rule["source_pattern"]}</div>' if rule.get("source_pattern") else ""}</div>', unsafe_allow_html=True)
                with c2:
                    if st.button("Archive",key=f"a_{rule['rule_id']}"): db.update_rule(rule["rule_id"],{"active":False}); st.rerun()
with tab2:
    with st.form("nr"):
        c1,c2=st.columns(2)
        with c1:
            rt=st.selectbox("Type",["Entry","Exit","Sizing","Psychology","Risk","Instrument-specific","Time-based"])
            rs=st.text_input("Short name",placeholder="No Gold within 48h of big win")
            pri=st.select_slider("Priority",[1,2,3,4,5],format_func=lambda x:{1:"1·Critical",2:"2·High",3:"3·Medium",4:"4·Low",5:"5·Info"}[x],value=3)
        with c2:
            rtx=st.text_area("Full rule text",placeholder="Be specific and actionable.",height=100)
            src=st.text_input("Source/reason",placeholder="Based on what pattern or trade?")
        if st.form_submit_button("Add Rule",type="primary",use_container_width=True):
            if rtx and rs: db.add_rule({"rule_type":rt,"rule_short":rs,"rule_text":rtx,"source_pattern":src or None,"priority":pri,"active":True}); st.success(f"✅ Rule added: {rs!r}"); st.rerun()
            else: st.error("Fill in short name and full rule text.")

import re, io, uuid, pandas as pd
from datetime import datetime, date

def detect_segment(instrument, exchange):
    inst = instrument.upper(); exch = (exchange or "").upper()
    if exch == "MCX" or any(c in inst for c in ["GOLD","SILVER","CRUDEOIL","NATURALGAS","COPPER","ZINC"]):
        return "FUT_COMMODITY"
    if exch == "NSEDERV":
        if "FUTIDX" in inst or "BANKNIFTY" in inst or ("NIFTY" in inst and "FUT" in inst): return "FUT_INDEX"
        if "OPTIDX" in inst or "OPTSTK" in inst: return "OPT_INDEX" if "IDX" in inst else "OPT_EQUITY"
        return "FUT_EQUITY"
    if exch in ("NSE","BSE"): return "EQ_INTRADAY"
    return "EQ_INTRADAY"

def detect_expiry(instrument):
    months = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}
    m = re.search(r"(\d{1,2})([A-Z]{3})(\d{4})", instrument.upper())
    if m:
        try: return date(int(m.group(3)), months[m.group(2)], int(m.group(1)))
        except: return None
    return None

def days_to_expiry(expiry):
    if not expiry: return None
    return (expiry - date.today()).days

def parse_holdings_to_positions(raw_csv):
    df = pd.read_csv(io.StringIO(raw_csv.strip()))
    positions = []
    for _, row in df.iterrows():
        instrument = str(row.get("Stock Name","")).strip()
        ticker = str(row.get("Stock Ticker","")).strip()
        exchange = str(row.get("Market Segment","")).strip().upper()
        xmap = {"NSE_CM":"NSE","NSE_FO":"NSEDERV","MCX_FO":"MCX","BSE_CM":"BSE"}
        exchange = xmap.get(exchange, exchange)
        invested = float(row.get("Total Cost of Holdings",0) or 0)
        mkt_val = float(row.get("Market Value",0) or 0)
        avg_cost = float(row.get("Average Purchase Price",0) or 0)
        cur_price = float(row.get("Current Price",0) or 0)
        qty = float(row.get("Shares Owned",0) or 0)
        unreal_pnl = mkt_val - invested
        unreal_pct = (unreal_pnl/invested*100) if invested else 0
        expiry = detect_expiry(instrument)
        segment = detect_segment(instrument, exchange)
        if exchange == "NSE" and str(row.get("Market Segment","")).lower() == "nse_cm": segment = "EQ_DELIVERY"
        positions.append({
            "instrument": instrument, "display_name": instrument, "ticker": ticker,
            "exchange": exchange, "segment": segment,
            "expiry_date": str(expiry) if expiry else None,
            "days_to_expiry": days_to_expiry(expiry),
            "quantity": qty, "avg_cost": avg_cost, "invested_value": invested,
            "current_price": cur_price, "market_value": mkt_val,
            "unrealized_pnl": round(unreal_pnl,2), "unrealized_pnl_pct": round(unreal_pct,4), "day_pnl": None,
        })
    return positions

def parse_tradebook_csv(raw_csv, session_date, session_id):
    df = pd.read_csv(io.StringIO(raw_csv.strip()))
    df.columns = [c.strip() for c in df.columns]
    df["Trade Date"] = pd.to_datetime(df["Trade Date"], dayfirst=True)
    df["Trade Time"] = pd.to_datetime(df["Trade Time"], format="%H:%M:%S", errors="coerce").dt.time
    df = df[df["Trade Date"].dt.date == session_date].copy()
    if df.empty: return []
    trades = []
    for instrument, grp in df.groupby("Security Name"):
        buys = grp[grp["Transaction Type"].str.strip().str.lower()=="buy"].sort_values("Trade Time")
        sells = grp[grp["Transaction Type"].str.strip().str.lower()=="sell"].sort_values("Trade Time")
        exchange = str(grp["Exchange"].iloc[0]).strip()
        segment = detect_segment(instrument, exchange)
        expiry = detect_expiry(instrument)
        isin = str(grp["ISIN"].iloc[0]) if "ISIN" in grp.columns else None
        if buys.empty or sells.empty:
            side = buys if not buys.empty else sells
            direction = "LONG" if not buys.empty else "SHORT"
            qty = float(side["Quantity"].sum())
            avg_price = float(side["Total"].sum()/qty) if qty else 0
            bt = None
            if not buys.empty and pd.notna(buys.iloc[0]["Trade Time"]):
                bt = datetime.combine(session_date, buys.iloc[0]["Trade Time"]).isoformat()
            trades.append({"trade_id":str(uuid.uuid4()),"session_id":session_id,"session_date":str(session_date),"instrument":instrument,"display_name":instrument,"isin":isin,"exchange":exchange,"segment":segment,"expiry_date":str(expiry) if expiry else None,"buy_time":bt,"sell_time":None,"holding_duration_mins":None,"quantity":qty,"avg_buy_price":avg_price if direction=="LONG" else 0,"avg_sell_price":avg_price if direction=="SHORT" else 0,"gross_pnl":0,"brokerage":float(side["Brokerage"].sum()),"gst":float(side["GST"].sum()),"misc_charges":float(side["Misc."].sum()) if "Misc." in side.columns else 0,"stt":float(side["STT/CTT"].sum()) if "STT/CTT" in side.columns else 0,"total_charges":float(side["Total Charges"].sum()),"net_pnl":0,"trade_direction":direction,"is_open":True,"debrief_done":False})
            continue
        bq = float(buys["Quantity"].sum()); sq = float(sells["Quantity"].sum()); mq = min(bq,sq)
        bt_total = float(buys["Total"].sum())*(mq/bq) if bq else 0
        st_total = float(sells["Total"].sum())*(mq/sq) if sq else 0
        gross_pnl = st_total - bt_total
        brok = float(grp["Brokerage"].sum()); gst = float(grp["GST"].sum())
        misc = float(grp["Misc."].sum()) if "Misc." in grp.columns else 0
        stt = float(grp["STT/CTT"].sum()) if "STT/CTT" in grp.columns else 0
        tc = float(grp["Total Charges"].sum()); net = gross_pnl - tc
        btv = buys.iloc[0]["Trade Time"] if pd.notna(buys.iloc[0]["Trade Time"]) else None
        stv = sells.iloc[-1]["Trade Time"] if pd.notna(sells.iloc[-1]["Trade Time"]) else None
        bdt = datetime.combine(session_date, btv).isoformat() if btv else None
        sdt = datetime.combine(session_date, stv).isoformat() if stv else None
        hm = int(abs((datetime.combine(session_date,stv)-datetime.combine(session_date,btv)).total_seconds())/60) if btv and stv else None
        trades.append({"trade_id":str(uuid.uuid4()),"session_id":session_id,"session_date":str(session_date),"instrument":instrument,"display_name":instrument,"isin":isin,"exchange":exchange,"segment":segment,"expiry_date":str(expiry) if expiry else None,"buy_time":bdt,"sell_time":sdt,"holding_duration_mins":hm,"quantity":mq,"avg_buy_price":round(bt_total/mq,4) if mq else 0,"avg_sell_price":round(st_total/mq,4) if mq else 0,"gross_pnl":round(gross_pnl,2),"brokerage":round(brok,2),"gst":round(gst,2),"misc_charges":round(misc,2),"stt":round(stt,2),"total_charges":round(tc,2),"net_pnl":round(net,2),"trade_direction":"LONG","is_open":False,"debrief_done":False})
    return trades

def detect_patterns_from_trades(trades_df, debriefs_df):
    patterns = []
    if trades_df.empty: return patterns
    df = trades_df.copy()
    df["net_pnl"] = pd.to_numeric(df["net_pnl"], errors="coerce").fillna(0)
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
    closed = df[~df.get("is_open", pd.Series([False]*len(df))).fillna(False)].copy()
    gold = closed[closed["instrument"].str.contains("GOLD|SILVER",case=False,na=False)].sort_values("session_date")
    reversals = []
    for i in range(len(gold)-1):
        r,n = gold.iloc[i], gold.iloc[i+1]
        if r["net_pnl"]>200000 and n["net_pnl"]<-100000 and (n["session_date"]-r["session_date"]).days<=2:
            reversals.append(n["net_pnl"])
    if reversals:
        patterns.append({"pattern_type":"Reversal loop","pattern_key":"gold_reversal_loop","description":"Big win on Gold/Silver followed by big loss within 48 hours","detail_text":f"Detected {len(reversals)} occurrences. Avg loss after reversal: INR{abs(sum(reversals)/len(reversals)):,.0f}","occurrence_count":len(reversals),"avg_pnl_impact":round(sum(reversals)/len(reversals),2),"total_pnl_impact":round(sum(reversals),2),"severity":"danger","last_seen":str(date.today()),"related_instrument":"GOLD/SILVER"})
    if not debriefs_df.empty and "emotion_score_entry" in debriefs_df.columns:
        merged = closed.merge(debriefs_df[["trade_id","emotion_score_entry"]], on="trade_id", how="inner")
        merged["emotion_score_entry"] = pd.to_numeric(merged["emotion_score_entry"],errors="coerce")
        hi = merged[merged["emotion_score_entry"]>=4]; lo = merged[merged["emotion_score_entry"]<=2]
        if len(hi)>=3 and len(lo)>=3:
            he = len(hi[hi["net_pnl"]>0])/len(hi); le = len(lo[lo["net_pnl"]>0])/len(lo)
            if le-he>0.1:
                patterns.append({"pattern_type":"Emotion impact","pattern_key":"high_emotion_underperformance","description":f"Calm trades win {le*100:.0f}% vs emotional trades {he*100:.0f}%","detail_text":f"Based on {len(merged)} debriefed trades.","occurrence_count":len(hi),"avg_pnl_impact":round(hi["net_pnl"].mean()-lo["net_pnl"].mean(),2),"severity":"warning" if le-he<0.2 else "danger","last_seen":str(date.today())})
    daily = closed.groupby("session_date").size()
    ot = daily[daily>6]
    if len(ot)>=2:
        otpnl = closed[closed["session_date"].isin(ot.index)].groupby("session_date")["net_pnl"].sum()
        patterns.append({"pattern_type":"Overtrading","pattern_key":"overtrading_sessions","description":f"{len(ot)} sessions with 7+ round-trips","detail_text":f"Avg P&L on high-trade days: INR{float(otpnl.mean()):,.0f}","occurrence_count":len(ot),"avg_pnl_impact":round(float(otpnl.mean()),2),"severity":"warning","last_seen":str(date.today())})
    wins = closed[closed["net_pnl"]>0]; losses = closed[closed["net_pnl"]<0]
    if len(wins)>=5 and len(losses)>=5:
        aw,al = float(wins["net_pnl"].mean()), float(losses["net_pnl"].mean())
        if abs(al)>aw:
            patterns.append({"pattern_type":"Payoff ratio below 1.0","pattern_key":"payoff_ratio_below_1","description":f"Avg win INR{aw:,.0f} < Avg loss INR{abs(al):,.0f}","detail_text":"Win more often but losses are larger. Cut losers shorter.","occurrence_count":len(losses),"avg_pnl_impact":round(al-aw,2),"severity":"warning","last_seen":str(date.today())})
    return patterns

def detect_pead_patterns(trades_df, debriefs_df):
    """PEAD-specific pattern detection — Rishabh's primary trading system."""
    patterns = []
    if trades_df.empty or debriefs_df.empty: return patterns

    df = trades_df.copy()
    df["net_pnl"] = pd.to_numeric(df["net_pnl"], errors="coerce").fillna(0)
    closed = df[~df.get("is_open", pd.Series([False]*len(df))).fillna(False)].copy()
    if closed.empty: return patterns

    merged = closed.merge(debriefs_df, on="trade_id", how="inner")
    if merged.empty: return patterns

    # PEAD score compliance from setup_notes
    pead_trades = merged[merged["setup_type"] == "News/Event"].copy()
    if len(pead_trades) >= 3:
        # Detect trades where lesson mentions "below 40" or "score"
        violations = pead_trades[pead_trades["lesson_text"].str.contains("below 40|RULE VIOLATION|violation", case=False, na=False)]
        if len(violations) >= 2:
            viol_pnl = violations["net_pnl"].sum()
            patterns.append({
                "pattern_type": "PEAD score violation",
                "pattern_key": "pead_below_40_trades",
                "description": f"Traded {len(violations)} PEAD setups with score below 40",
                "detail_text": f"Total P&L on below-40 trades: ₹{viol_pnl:,.0f}. Rule: PEAD score must be ≥40 before entry.",
                "occurrence_count": len(violations),
                "avg_pnl_impact": round(float(violations["net_pnl"].mean()), 2),
                "total_pnl_impact": round(float(viol_pnl), 2),
                "severity": "danger",
                "last_seen": str(date.today()),
            })

        # Quick exit compliance — PEAD trades held > 5 min
        if "holding_duration_mins" in pead_trades.columns:
            pead_trades["holding_duration_mins"] = pd.to_numeric(pead_trades["holding_duration_mins"], errors="coerce")
            long_holds = pead_trades[pead_trades["holding_duration_mins"] > 5]
            short_holds = pead_trades[pead_trades["holding_duration_mins"] <= 5]
            if len(long_holds) >= 2 and len(short_holds) >= 2:
                avg_long = float(long_holds["net_pnl"].mean())
                avg_short = float(short_holds["net_pnl"].mean())
                if avg_short > avg_long:
                    patterns.append({
                        "pattern_type": "PEAD holding duration",
                        "pattern_key": "pead_long_hold_underperformance",
                        "description": f"Quick exits (≤5min) avg ₹{avg_short:,.0f} vs long holds (>5min) avg ₹{avg_long:,.0f}",
                        "detail_text": "Data confirms: exit PEAD trades within 2 minutes for best outcomes.",
                        "occurrence_count": len(long_holds),
                        "avg_pnl_impact": round(avg_long - avg_short, 2),
                        "total_pnl_impact": round(float(long_holds["net_pnl"].sum()), 2),
                        "severity": "warning",
                        "last_seen": str(date.today()),
                    })

        # Emotion FOMO on PEAD trades
        if "emotion_score_entry" in pead_trades.columns:
            pead_trades["emotion_score_entry"] = pd.to_numeric(pead_trades["emotion_score_entry"], errors="coerce")
            fomo = pead_trades[pead_trades["emotion_score_entry"] >= 4]
            calm = pead_trades[pead_trades["emotion_score_entry"] <= 2]
            if len(fomo) >= 2 and len(calm) >= 1:
                avg_fomo = float(fomo["net_pnl"].mean())
                avg_calm = float(calm["net_pnl"].mean())
                if avg_calm > avg_fomo:
                    patterns.append({
                        "pattern_type": "PEAD emotion impact",
                        "pattern_key": "pead_fomo_underperformance",
                        "description": f"Calm PEAD trades avg ₹{avg_calm:,.0f} vs FOMO trades avg ₹{avg_fomo:,.0f}",
                        "detail_text": f"{len(fomo)} FOMO entries vs {len(calm)} calm entries.",
                        "occurrence_count": len(fomo),
                        "avg_pnl_impact": round(avg_fomo - avg_calm, 2),
                        "severity": "warning",
                        "last_seen": str(date.today()),
                    })

    return patterns


import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from data_sources import mlb_schedule, standings, sportsbook_odds, flatten_odds
from model import build_game_models, value_board, decimal_odds

st.set_page_config(page_title="Diamond Edge MLB v5", page_icon="⚾", layout="wide")
TODAY = datetime.now(ZoneInfo("America/Chicago")).date()
SEASON = TODAY.year

st.markdown("""
<style>
.stApp{background:linear-gradient(180deg,#f8fbff 0%,#edf4fa 100%);color:#12263a}
.block-container{max-width:1500px;padding-top:1rem}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #d7e3ee}
[data-testid="stMetric"],.card{background:#fff;border:1px solid #d7e3ee;border-radius:17px;padding:16px;box-shadow:0 5px 16px rgba(35,72,105,.08)}
.card{margin-bottom:14px}.green{border-left:6px solid #16a34a}.yellow{border-left:6px solid #d97706}.red{border-left:6px solid #dc2626}
.badge{display:inline-block;padding:4px 9px;border-radius:999px;font-size:.74rem;font-weight:800;margin-right:5px}
.bg-green{background:#dcfce7;color:#166534}.bg-yellow{background:#fef3c7;color:#92400e}.bg-red{background:#fee2e2;color:#991b1b}.bg-blue{background:#dbeafe;color:#1e40af}
.muted{color:#62768a;font-size:.88rem}.pick{font-size:1.12rem;font-weight:850;margin:.5rem 0}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚾ Diamond Edge v5")
    page = st.radio("Page", ["🏠 Dashboard","⭐ Best Bets","⚾ Games","🎯 Player Props","🌦️ Weather","📈 Market","💼 Tracker","⚙️ Sources"], label_visibility="collapsed")
    st.divider()
    slate_date = st.date_input("Slate date", TODAY)
    api_key = st.text_input("The Odds API key", value=st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY","")), type="password")
    region = st.selectbox("Odds region", ["us","us2","eu","uk","au"])
    bankroll = st.number_input("Bankroll", min_value=0.0, value=500.0, step=25.0)
    unit_pct = st.slider("Unit size (%)", .25, 5.0, 1.0, .25)
    st.metric("1 unit", f"${bankroll*unit_pct/100:,.2f}")

try: schedule = mlb_schedule(str(slate_date))
except Exception: schedule = pd.DataFrame()
try: table = standings(SEASON)
except Exception: table = pd.DataFrame()
models = build_game_models(schedule, table, SEASON) if not schedule.empty and not table.empty else pd.DataFrame()

odds = pd.DataFrame(); quota = None; odds_error = None
if api_key:
    try:
        raw, quota = sportsbook_odds(api_key, region)
        odds = flatten_odds(raw)
    except Exception as exc:
        odds_error = str(exc)
board = value_board(models, odds)

def header(title, subtitle):
    a,b=st.columns([4,1])
    with a:
        st.title(title); st.caption(subtitle)
    with b:
        label="LIVE ODDS" if not odds.empty else "MODEL ONLY"
        css="bg-green" if not odds.empty else "bg-yellow"
        st.markdown(f'<div style="text-align:right"><span class="badge {css}">{label}</span></div>',unsafe_allow_html=True)

def cards(frame, limit=12):
    if frame.empty:
        st.info("No qualifying live value bets are available.")
        return
    cols=st.columns(3)
    for i,(_,r) in enumerate(frame.head(limit).iterrows()):
        border="green" if r.Grade in ("A","B") else "yellow" if r.Grade=="C" else "red"
        badge="bg-green" if r.Grade in ("A","B") else "bg-yellow" if r.Grade=="C" else "bg-red"
        with cols[i%3]:
            st.markdown(f"""<div class="card {border}">
            <span class="badge {badge}">GRADE {r.Grade}</span><span class="badge bg-blue">{r.Score}/99</span>
            <div class="muted" style="margin-top:8px">{r.Game} • {r.Start}</div>
            <div class="pick">{r.Pick} ({r.Odds:+d})</div>
            <b>{r.Book}</b><br>Model: <b>{r.ModelProb*100:.1f}%</b> • Fair: <b>{r.FairOdds:+d}</b><br>
            Edge: <b>{r.Edge:.1f}%</b> • EV: <b>${r.EV:.2f}/$100</b>
            <div class="muted" style="margin-top:8px">{r.Reason}</div></div>""",unsafe_allow_html=True)

if page=="🏠 Dashboard":
    header("Diamond Edge MLB","A transparent daily betting research dashboard.")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Games",len(schedule)); c2.metric("Predictions",len(models))
    c3.metric("Sportsbooks",odds.Book.nunique() if not odds.empty else 0)
    c4.metric("Positive-edge bets",int((board.Edge>=1.5).sum()) if not board.empty else 0)
    st.subheader("Top plays")
    if board.empty:
        st.info("The matchup model is active. Add an Odds API key to calculate live edge and expected value.")
        if not models.empty:
            preview=models.copy()
            preview["Pick"]=preview.apply(lambda r:r.HomeTeam if r.HomeProb>=r.AwayProb else r.AwayTeam,axis=1)
            preview["Probability"]=(preview[["AwayProb","HomeProb"]].max(axis=1)*100).round(1).astype(str)+"%"
            st.dataframe(preview[["Game","Start","Pick","Probability","AwayFair","HomeFair","ProjectedTotal"]],use_container_width=True,hide_index=True)
    else: cards(board[board.Edge>=1.5],9)

elif page=="⭐ Best Bets":
    header("Best Bets","Filter live prices by model edge and confidence.")
    if odds_error: st.error(odds_error)
    e=st.slider("Minimum edge",0.0,12.0,1.5,.5); s=st.slider("Minimum score",1,99,55)
    filtered=board[(board.Edge>=e)&(board.Score>=s)] if not board.empty else pd.DataFrame()
    cards(filtered)

elif page=="⚾ Games":
    header("Games","Starting pitchers, weather, park context, probabilities, and fair odds.")
    if models.empty: st.warning("No model data is available for this date.")
    for _,r in models.iterrows():
        pick=r.HomeTeam if r.HomeProb>=r.AwayProb else r.AwayTeam
        with st.expander(f"{r.Game} • {r.Start} • {pick}"):
            a,b,c=st.columns([1,1,1])
            with a:
                st.subheader(r.AwayTeam); st.write(f"Starter: {r.AwayPitcher}")
                st.write(f"ERA: {r.AwayERA or 'N/A'} • K/9: {r.AwayK9 or 'N/A'}")
                st.metric("Win probability",f"{r.AwayProb*100:.1f}%"); st.metric("Fair odds",f"{r.AwayFair:+d}")
            with b:
                st.subheader(r.HomeTeam); st.write(f"Starter: {r.HomePitcher}")
                st.write(f"ERA: {r.HomeERA or 'N/A'} • K/9: {r.HomeK9 or 'N/A'}")
                st.metric("Win probability",f"{r.HomeProb*100:.1f}%"); st.metric("Fair odds",f"{r.HomeFair:+d}")
            with c:
                st.subheader("Environment"); st.metric("Projected total",r.ProjectedTotal)
                st.write(f"Park factor: {r.ParkFactor:.2f}")
                if r.Weather:
                    st.write(f"{r.Weather['Temperature']}°F • Wind {r.Weather['WindSpeed']} mph")
                    st.write(f"Rain chance: {r.Weather['RainChance']}%")
                else: st.write("Weather unavailable")
            if not odds.empty:
                game_odds=odds[odds.Game==r.Game]
                if not game_odds.empty: st.dataframe(game_odds.sort_values("Odds",ascending=False),use_container_width=True,hide_index=True)

elif page=="🎯 Player Props":
    header("Player Props","Architecture for strikeouts, total bases, hits, walks, and home runs.")
    st.warning("Live player-prop prices require an event-markets data plan. This page does not invent unavailable lines.")
    st.dataframe(pd.DataFrame([
        ["Pitcher strikeouts","Ready for feed","K/9, opponent K%, pitch count, umpire"],
        ["Total bases","Ready for feed","Platoon, hard-hit%, pitch mix, park, weather"],
        ["Hits","Ready for feed","Contact%, xBA, lineup position"],
        ["Home run","Ready for feed","Barrel%, fly-ball%, park, temperature, wind"],
        ["Walks","Ready for feed","BB%, chase%, pitcher BB%, umpire"],
    ],columns=["Market","Status","Planned factors"]),use_container_width=True,hide_index=True)

elif page=="🌦️ Weather":
    header("Weather Center","Game-time temperature, wind, humidity, and precipitation risk.")
    rows=[]
    for _,r in models.iterrows():
        w=r.Weather
        rows.append({
            "Game":r.Game,"Start":r.Start,"Venue":r.Venue,
            "Temperature":None if not w else w["Temperature"],
            "Wind mph":None if not w else w["WindSpeed"],
            "Wind direction":None if not w else w["WindDirection"],
            "Humidity %":None if not w else w["Humidity"],
            "Rain chance %":None if not w else w["RainChance"],
            "Projected total":r.ProjectedTotal,
        })
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

elif page=="📈 Market":
    header("Market Center","Compare moneylines, run lines, and totals across connected sportsbooks.")
    if odds.empty: st.info("Add your Odds API key to load market prices.")
    else:
        markets={"h2h":"Moneyline","spreads":"Run Line","totals":"Total"}
        display=odds.copy(); display["Market"]=display.Market.map(markets)
        st.dataframe(display.sort_values(["Game","Market","Selection","Odds"],ascending=[True,True,True,False]),use_container_width=True,hide_index=True)
        if quota is not None: st.caption(f"API requests remaining: {quota}")

elif page=="💼 Tracker":
    header("Bet Tracker","Session-based tracking with CSV export.")
    st.info("Streamlit Community Cloud does not guarantee permanent local storage. Download the CSV before closing or redeploying.")
    if "bets" not in st.session_state:
        st.session_state.bets=pd.DataFrame(columns=["Date","Bet","Market","Odds","Stake","Result","Profit"])
    with st.form("add",clear_on_submit=True):
        a,b,c=st.columns(3)
        bet=a.text_input("Bet"); market=b.selectbox("Market",["Moneyline","Run Line","Total","Player Prop"])
        price=c.number_input("Odds",value=-110,step=5)
        d,e=st.columns(2); stake=d.number_input("Stake",min_value=1.0,value=10.0); result=e.selectbox("Result",["Pending","Win","Loss","Push"])
        submitted=st.form_submit_button("Add bet")
    if submitted and bet:
        profit=stake*(decimal_odds(price)-1) if result=="Win" else -stake if result=="Loss" else 0
        row=pd.DataFrame([[str(slate_date),bet,market,price,stake,result,round(profit,2)]],columns=st.session_state.bets.columns)
        st.session_state.bets=pd.concat([st.session_state.bets,row],ignore_index=True)
    if not st.session_state.bets.empty:
        settled=st.session_state.bets[st.session_state.bets.Result.isin(["Win","Loss","Push"])]
        risk=settled.Stake.sum(); profit=settled.Profit.sum(); roi=profit/risk*100 if risk else 0
        a,b,c=st.columns(3); a.metric("Profit",f"${profit:.2f}"); b.metric("ROI",f"{roi:.1f}%"); c.metric("Bets",len(st.session_state.bets))
        st.dataframe(st.session_state.bets,use_container_width=True,hide_index=True)
        st.download_button("Download tracker CSV",st.session_state.bets.to_csv(index=False),"diamond_edge_tracker.csv","text/csv")

elif page=="⚙️ Sources":
    header("Data Sources","Connection status and honest limitations.")
    st.write("✅ MLB schedule, standings, and probable pitchers" if not schedule.empty else "⚠️ MLB feed unavailable")
    st.write("✅ Open-Meteo game-time forecast" if not models.empty else "⚠️ Weather not loaded")
    st.write("✅ The Odds API sportsbook prices" if not odds.empty else "⚠️ The Odds API key not connected")
    st.write("⚠️ Confirmed lineups, injuries, umpires, advanced Statcast splits, and player props need additional feeds")
    st.markdown("""### Streamlit secret
```toml
ODDS_API_KEY = "your_key_here"
```""")
    st.caption("Open-Meteo attribution: Weather data by Open-Meteo.com.")

st.divider()
st.caption("Research tool only. Predictions are estimates, not guarantees. Verify every price and lineup before betting.")

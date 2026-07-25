
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from data_sources import (
    mlb_schedule, standings, sportsbook_odds, flatten_odds,
    MLB_PROP_MARKETS, event_prop_odds, flatten_props
)
from model import (
    build_game_models, value_board, decimal_odds,
    prop_best_prices, prop_value_board
)

st.set_page_config(page_title="Diamond Edge MLB v6", page_icon="⚾", layout="wide")
TODAY = datetime.now(ZoneInfo("America/Chicago")).date()
SEASON = TODAY.year

st.markdown("""
<style>
.stApp{background:linear-gradient(180deg,#f8fbff 0%,#edf4fa 100%);color:#12263a}
.block-container{max-width:1550px;padding-top:1rem}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #d7e3ee}
[data-testid="stMetric"],.card{background:#fff;border:1px solid #d7e3ee;border-radius:17px;padding:16px;box-shadow:0 5px 16px rgba(35,72,105,.08)}
.card{margin-bottom:14px}.green{border-left:6px solid #16a34a}.yellow{border-left:6px solid #d97706}.red{border-left:6px solid #dc2626}
.badge{display:inline-block;padding:4px 9px;border-radius:999px;font-size:.74rem;font-weight:800;margin-right:5px}
.bg-green{background:#dcfce7;color:#166534}.bg-yellow{background:#fef3c7;color:#92400e}.bg-red{background:#fee2e2;color:#991b1b}.bg-blue{background:#dbeafe;color:#1e40af}.bg-gray{background:#eef2f7;color:#334155}
.muted{color:#62768a;font-size:.88rem}.pick{font-size:1.12rem;font-weight:850;margin:.5rem 0}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚾ Diamond Edge v6")
    page = st.radio(
        "Page",
        ["🏠 Dashboard","🔥 All Best Bets","🎯 Player Props","⚾ Games",
         "🌦️ Weather","📈 Market","💼 Tracker","⚙️ Sources"],
        label_visibility="collapsed"
    )
    st.divider()
    slate_date = st.date_input("Slate date", TODAY)
    api_key = st.text_input(
        "The Odds API key",
        value=st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY","")),
        type="password"
    )
    region = st.selectbox("Odds region", ["us","us2","eu","uk","au"])
    bankroll = st.number_input("Bankroll", min_value=0.0, value=500.0, step=25.0)
    unit_pct = st.slider("Unit size (%)", .25, 5.0, 1.0, .25)
    st.metric("1 unit", f"${bankroll*unit_pct/100:,.2f}")

try:
    schedule = mlb_schedule(str(slate_date))
except Exception:
    schedule = pd.DataFrame()
try:
    table = standings(SEASON)
except Exception:
    table = pd.DataFrame()
models = build_game_models(schedule, table, SEASON) if not schedule.empty and not table.empty else pd.DataFrame()

odds = pd.DataFrame()
quota = {}
odds_error = None
if api_key:
    try:
        raw, quota = sportsbook_odds(api_key, region)
        odds = flatten_odds(raw)
    except Exception as exc:
        odds_error = str(exc)
board = value_board(models, odds)

if "props" not in st.session_state:
    st.session_state.props = pd.DataFrame()
if "prop_status" not in st.session_state:
    st.session_state.prop_status = ""
if "prop_quota" not in st.session_state:
    st.session_state.prop_quota = {}

MARKET_LABELS = {v:k for k,v in MLB_PROP_MARKETS.items()}

def header(title, subtitle):
    a,b=st.columns([4,1])
    with a:
        st.title(title)
        st.caption(subtitle)
    with b:
        label="LIVE ODDS" if not odds.empty else "MODEL ONLY"
        css="bg-green" if not odds.empty else "bg-yellow"
        st.markdown(f'<div style="text-align:right"><span class="badge {css}">{label}</span></div>',unsafe_allow_html=True)

def bet_cards(frame, limit=15, prop=False):
    if frame.empty:
        st.info("No qualifying bets are available with the current filters.")
        return
    cols=st.columns(3)
    for i,(_,r) in enumerate(frame.head(limit).iterrows()):
        border="green" if r.Grade in ("A","B") else "yellow" if r.Grade=="C" else "red"
        badge="bg-green" if r.Grade in ("A","B") else "bg-yellow" if r.Grade=="C" else "bg-red"
        with cols[i%3]:
            if prop:
                market=MARKET_LABELS.get(r.Market,r.Market)
                pick=f"{r.Player} {r.Side} {r.Line:g}"
                detail=f"{market} • {r.Game}"
                probability=r.ConsensusProb
                probability_label="No-vig consensus"
            else:
                pick=f"{r.Pick} ({r.Odds:+d})"
                detail=f"{r.Game} • {r.Start}"
                probability=r.ModelProb
                probability_label="Model"
            st.markdown(f"""<div class="card {border}">
            <span class="badge {badge}">GRADE {r.Grade}</span>
            <span class="badge bg-blue">{r.Score}/99</span>
            <div class="muted" style="margin-top:8px">{detail}</div>
            <div class="pick">{pick}</div>
            <b>{r.Book} ({r.Odds:+d})</b><br>
            {probability_label}: <b>{probability*100:.1f}%</b><br>
            Edge: <b>{r.Edge:.1f}%</b> • EV: <b>${r.EV:.2f}/$100</b>
            </div>""", unsafe_allow_html=True)

def load_props(selected_games, selected_market_names):
    if not api_key:
        st.session_state.prop_status = "Add your Odds API key first."
        return
    if odds.empty:
        st.session_state.prop_status = "Featured odds must load first so event IDs are available."
        return
    market_keys=[MLB_PROP_MARKETS[n] for n in selected_market_names]
    events=[]
    errors=[]
    latest_quota={}
    progress=st.progress(0, text="Loading player props...")
    games = selected_games or sorted(odds.Game.dropna().unique().tolist())
    for i,game in enumerate(games):
        matches=odds[odds.Game==game]
        if matches.empty:
            continue
        event_id=matches.EventID.iloc[0]
        try:
            event,q=event_prop_odds(api_key,event_id,region,market_keys)
            events.append(event)
            latest_quota=q
        except Exception as exc:
            errors.append(f"{game}: {exc}")
        progress.progress((i+1)/max(1,len(games)), text=f"Loading {game}")
    progress.empty()
    st.session_state.props=flatten_props(events)
    st.session_state.prop_quota=latest_quota
    if errors and st.session_state.props.empty:
        st.session_state.prop_status="Props could not load. " + " | ".join(errors[:2])
    elif errors:
        st.session_state.prop_status=f"Loaded {len(st.session_state.props):,} prices, with {len(errors)} game errors."
    else:
        st.session_state.prop_status=f"Loaded {len(st.session_state.props):,} player-prop prices."

if page=="🏠 Dashboard":
    header("Diamond Edge MLB","Daily matchup model plus sportsbook and player-prop line shopping.")
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Games",len(schedule))
    c2.metric("Sportsbooks",odds.Book.nunique() if not odds.empty else 0)
    c3.metric("Game prices",len(odds))
    c4.metric("Prop prices",len(st.session_state.props))
    c5.metric("Positive game edges",int((board.Edge>=1.5).sum()) if not board.empty else 0)
    st.subheader("Best game bets")
    if board.empty:
        st.info("Add a valid Odds API key to compare the matchup model against live prices.")
    else:
        bet_cards(board[board.Edge>=1.5],9)
    if not st.session_state.props.empty:
        st.subheader("Best available prop prices")
        prop_board=prop_value_board(st.session_state.props)
        bet_cards(prop_board[prop_board.Edge>=0],9,prop=True)

elif page=="🔥 All Best Bets":
    header("All Best Available Bets","Moneylines, game-market prices, and loaded player props in one place.")
    tabs=st.tabs(["Model Value","Best Moneylines","Best Run Lines","Best Totals","Best Props"])
    with tabs[0]:
        min_edge=st.slider("Minimum model edge",0.0,12.0,1.5,.5)
        bet_cards(board[board.Edge>=min_edge] if not board.empty else pd.DataFrame())
    for tab,key in zip(tabs[1:4],["h2h","spreads","totals"]):
        with tab:
            frame=odds[odds.Market==key].copy() if not odds.empty else pd.DataFrame()
            if frame.empty:
                st.info("No prices found.")
            else:
                group=["Game","Selection"]
                if key in ("spreads","totals"): group.append("Line")
                idx=frame.groupby(group,dropna=False)["Odds"].idxmax()
                best=frame.loc[idx].sort_values(["Game","Selection","Line"])
                st.dataframe(best[["Game","Selection","Line","Odds","Book","LastUpdate"]],use_container_width=True,hide_index=True)
    with tabs[4]:
        props=st.session_state.props
        if props.empty:
            st.info("Open Player Props and press Load selected props.")
        else:
            prop_board=prop_value_board(props)
            min_prop_edge=st.slider("Minimum consensus edge",-3.0,10.0,0.0,.5)
            bet_cards(prop_board[prop_board.Edge>=min_prop_edge],18,prop=True)
            st.caption("Prop edge uses a no-vig sportsbook consensus, not a trained player-performance projection.")

elif page=="🎯 Player Props":
    header("Player Props","Load every supported MLB prop market for selected games, then compare the best sportsbook prices.")
    if not api_key:
        st.warning("Add your Odds API key in the sidebar.")
    game_options=sorted(odds.Game.dropna().unique().tolist()) if not odds.empty else []
    default_games=game_options[:min(5,len(game_options))]
    selected_games=st.multiselect("Games",game_options,default=default_games)
    market_names=list(MLB_PROP_MARKETS.keys())
    default_markets=["Pitcher Strikeouts","Batter Total Bases","Batter Hits","Batter Home Runs","Batter RBIs"]
    selected_markets=st.multiselect("Prop markets",market_names,default=default_markets)
    estimated_calls=len(selected_games or game_options)
    estimated_credits=estimated_calls*len(selected_markets)
    st.caption(f"Estimated usage: approximately {estimated_calls} event requests and {estimated_credits} market-region credits.")
    if st.button("Load selected props",type="primary",use_container_width=True):
        load_props(selected_games,selected_markets)
    if st.session_state.prop_status:
        st.info(st.session_state.prop_status)
    props=st.session_state.props
    if not props.empty:
        a,b,c,d=st.columns(4)
        a.metric("Prices",len(props))
        b.metric("Players",props.Player.nunique())
        c.metric("Sportsbooks",props.Book.nunique())
        d.metric("Markets",props.Market.nunique())
        filter_market=st.selectbox("Display market",["All"]+sorted(props.Market.map(lambda x:MARKET_LABELS.get(x,x)).unique().tolist()))
        search=st.text_input("Search player")
        display=props.copy()
        display["Market Name"]=display.Market.map(lambda x:MARKET_LABELS.get(x,x))
        if filter_market!="All":
            display=display[display["Market Name"]==filter_market]
        if search:
            display=display[display.Player.str.contains(search,case=False,na=False)]
        view=st.radio("View",["Best prices only","All sportsbook prices"],horizontal=True)
        if view=="Best prices only":
            display=prop_best_prices(display)
            display["Market Name"]=display.Market.map(lambda x:MARKET_LABELS.get(x,x))
        st.dataframe(
            display[["Game","Market Name","Player","Side","Line","Odds","Book","LastUpdate"]]
            .sort_values(["Game","Market Name","Player","Line","Side","Odds"],ascending=[True,True,True,True,True,False]),
            use_container_width=True,hide_index=True
        )
        st.download_button("Download props CSV",display.to_csv(index=False),"diamond_edge_props.csv","text/csv")
        if st.session_state.prop_quota:
            st.caption(f"API requests remaining: {st.session_state.prop_quota.get('remaining','Unknown')}")
    else:
        st.info("Choose games and markets, then load the props. Books may not post every market until closer to first pitch.")

elif page=="⚾ Games":
    header("Games","Starting pitchers, weather, park context, model probabilities, and live prices.")
    if models.empty:
        st.warning("No model data is available for this date.")
    for _,r in models.iterrows():
        pick=r.HomeTeam if r.HomeProb>=r.AwayProb else r.AwayTeam
        with st.expander(f"{r.Game} • {r.Start} • Model: {pick}"):
            a,b,c=st.columns(3)
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
            game_odds=odds[odds.Game==r.Game] if not odds.empty else pd.DataFrame()
            if not game_odds.empty:
                st.dataframe(game_odds[["Market","Selection","Line","Odds","Book","LastUpdate"]].sort_values("Odds",ascending=False),use_container_width=True,hide_index=True)

elif page=="🌦️ Weather":
    header("Weather Center","Game-time temperature, wind, humidity, and precipitation risk.")
    rows=[]
    for _,r in models.iterrows():
        w=r.Weather
        rows.append({"Game":r.Game,"Start":r.Start,"Venue":r.Venue,
            "Temperature":None if not w else w["Temperature"],
            "Wind mph":None if not w else w["WindSpeed"],
            "Wind direction":None if not w else w["WindDirection"],
            "Humidity %":None if not w else w["Humidity"],
            "Rain chance %":None if not w else w["RainChance"],
            "Projected total":r.ProjectedTotal})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

elif page=="📈 Market":
    header("Market Center","Every connected moneyline, run line, and total price.")
    if odds.empty:
        st.info("Add your Odds API key to load prices.")
    else:
        display=odds.copy()
        display["Market"]=display.Market.map({"h2h":"Moneyline","spreads":"Run Line","totals":"Total"})
        st.dataframe(display[["Game","Market","Selection","Line","Odds","Book","LastUpdate"]].sort_values(["Game","Market","Selection","Odds"],ascending=[True,True,True,False]),use_container_width=True,hide_index=True)
        if quota:
            st.caption(f"API requests remaining: {quota.get('remaining','Unknown')}")

elif page=="💼 Tracker":
    header("Bet Tracker","Track and export your bets.")
    if "bets" not in st.session_state:
        st.session_state.bets=pd.DataFrame(columns=["Date","Bet","Market","Odds","Stake","Result","Profit"])
    with st.form("add",clear_on_submit=True):
        a,b,c=st.columns(3)
        bet=a.text_input("Bet"); market=b.selectbox("Market",["Moneyline","Run Line","Total","Player Prop"]); price=c.number_input("Odds",value=-110,step=5)
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
    header("Sources and Coverage","Connection status and reasons some props may still be absent.")
    st.write("✅ Official MLB game and pitcher data" if not schedule.empty else "⚠️ MLB feed unavailable")
    st.write("✅ Open-Meteo weather forecasts" if not models.empty else "⚠️ Weather unavailable")
    st.write("✅ Featured sportsbook markets" if not odds.empty else "⚠️ Add a valid Odds API key")
    st.write("✅ Event-level MLB player-prop integration")
    st.markdown("""
**Why a market can still be missing**
- The sportsbook has not posted it yet.
- The selected region or bookmaker does not offer it.
- The player is not confirmed in the lineup.
- The API account has insufficient remaining credits.
- The API provider does not cover that exact book or prop.
""")
    if odds_error:
        st.error(odds_error)
    st.markdown("""### Streamlit secret
```toml
ODDS_API_KEY = "your_key_here"
```""")

st.divider()
st.caption("Research tool only. Prop rankings based on sportsbook consensus are not guaranteed predictions. Verify every line before betting.")


import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Diamond Edge MLB",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

CENTRAL = ZoneInfo("America/Chicago")
TODAY = datetime.now(CENTRAL).date()
SEASON = TODAY.year

# -------------------- Theme --------------------
st.markdown("""
<style>
.stApp {
  background: linear-gradient(180deg,#f8fbff 0%,#eef4f9 100%);
  color:#14263a;
}
.block-container {max-width:1500px;padding-top:1rem;padding-bottom:3rem;}
[data-testid="stSidebar"] {
  background:#ffffff;
  border-right:1px solid #d9e4ee;
}
[data-testid="stSidebar"] * {color:#14263a;}
div[data-testid="stMetric"] {
  background:#ffffff;
  border:1px solid #d9e4ee;
  border-radius:16px;
  padding:14px;
  box-shadow:0 4px 14px rgba(40,76,110,.07);
}
.card {
  background:#ffffff;
  border:1px solid #d9e4ee;
  border-radius:18px;
  padding:18px;
  box-shadow:0 5px 16px rgba(40,76,110,.08);
  margin-bottom:14px;
}
.card-green {border-left:6px solid #16a34a;}
.card-yellow {border-left:6px solid #d97706;}
.card-red {border-left:6px solid #dc2626;}
.badge {
  display:inline-block;
  padding:4px 9px;
  border-radius:999px;
  font-size:.75rem;
  font-weight:800;
  margin-right:5px;
}
.green {background:#dcfce7;color:#166534;border:1px solid #86efac;}
.yellow {background:#fef3c7;color:#92400e;border:1px solid #fcd34d;}
.red {background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;}
.blue {background:#dbeafe;color:#1e40af;border:1px solid #93c5fd;}
.gray {background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;}
.muted {color:#61758a;font-size:.88rem;}
.title-small {font-size:1.25rem;font-weight:850;color:#10283f;}
.pick {font-size:1.1rem;font-weight:850;color:#10283f;margin:.45rem 0;}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {background:#ffffff;}
.stTabs [data-baseweb="tab"] {background:#fff;border:1px solid #d9e4ee;border-radius:10px;}
</style>
""", unsafe_allow_html=True)

# -------------------- Math --------------------
def clamp(x, low, high):
    return max(low, min(high, x))

def logistic(x):
    return 1 / (1 + math.exp(-x))

def logit(p):
    p = clamp(p, .01, .99)
    return math.log(p / (1-p))

def implied_prob(odds):
    odds = float(odds)
    return 100/(odds+100) if odds > 0 else abs(odds)/(abs(odds)+100)

def decimal_odds(odds):
    return 1 + odds/100 if odds > 0 else 1 + 100/abs(odds)

def ev_per_100(prob, odds):
    d = decimal_odds(float(odds))
    return 100*(prob*(d-1)-(1-prob))

def edge_pct(prob, odds):
    return (prob-implied_prob(odds))*100

def fair_american(p):
    p = clamp(p,.01,.99)
    return -round(100*p/(1-p)) if p >= .5 else round(100*(1-p)/p)

def grade(edge):
    if edge >= 7: return "A"
    if edge >= 4: return "B"
    if edge >= 1.5: return "C"
    return "PASS"

def badge_color(g):
    return "green" if g in ("A","B") else "yellow" if g=="C" else "red"

def card_color(g):
    return "card-green" if g in ("A","B") else "card-yellow" if g=="C" else "card-red"

def fmt_time(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z","+00:00")).astimezone(CENTRAL).strftime("%-I:%M %p CT")
    except Exception:
        return iso

# -------------------- Data connections --------------------
@st.cache_data(ttl=300)
def fetch_schedule(date_string):
    r = requests.get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={"sportId":1,"date":date_string,"hydrate":"probablePitcher,team"},
        timeout=20
    )
    r.raise_for_status()
    rows=[]
    for day in r.json().get("dates",[]):
        for game in day.get("games",[]):
            a=game["teams"]["away"]["team"]
            h=game["teams"]["home"]["team"]
            rows.append({
                "GamePk":game.get("gamePk"),
                "Game":f"{a['name']} @ {h['name']}",
                "AwayTeam":a["name"],"AwayID":a["id"],
                "HomeTeam":h["name"],"HomeID":h["id"],
                "Start":fmt_time(game.get("gameDate","")),
                "Status":game.get("status",{}).get("detailedState",""),
                "AwayPitcher":game["teams"]["away"].get("probablePitcher",{}).get("fullName","TBD"),
                "AwayPitcherID":game["teams"]["away"].get("probablePitcher",{}).get("id"),
                "HomePitcher":game["teams"]["home"].get("probablePitcher",{}).get("fullName","TBD"),
                "HomePitcherID":game["teams"]["home"].get("probablePitcher",{}).get("id"),
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=900)
def fetch_standings(season):
    r=requests.get(
        "https://statsapi.mlb.com/api/v1/standings",
        params={"leagueId":"103,104","season":season,"standingsTypes":"regularSeason"},
        timeout=20
    )
    r.raise_for_status()
    rows=[]
    for group in r.json().get("records",[]):
        for t in group.get("teamRecords",[]):
            w=int(t.get("wins",0)); l=int(t.get("losses",0)); g=max(1,w+l)
            rows.append({
                "TeamID":t["team"]["id"],"Team":t["team"]["name"],
                "Wins":w,"Losses":l,"Games":g,
                "WinPct":w/g,
                "RunDiff":int(t.get("runDifferential",0)),
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=1800)
def fetch_pitcher_stats(pid, season):
    if not pid:
        return {"ERA":None,"WHIP":None,"K9":None,"IP":0}
    try:
        r=requests.get(
            f"https://statsapi.mlb.com/api/v1/people/{pid}/stats",
            params={"stats":"season","group":"pitching","season":season},
            timeout=15
        )
        r.raise_for_status()
        splits=r.json().get("stats",[{}])[0].get("splits",[])
        if not splits: return {"ERA":None,"WHIP":None,"K9":None,"IP":0}
        s=splits[0].get("stat",{})
        def num(k):
            v=s.get(k)
            return None if v in (None,"-.--") else float(v)
        return {"ERA":num("era"),"WHIP":num("whip"),"K9":num("strikeoutsPer9Inn"),"IP":float(s.get("inningsPitched",0) or 0)}
    except Exception:
        return {"ERA":None,"WHIP":None,"K9":None,"IP":0}

@st.cache_data(ttl=180)
def fetch_odds(api_key, region):
    r=requests.get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={"apiKey":api_key,"regions":region,"markets":"h2h,spreads,totals","oddsFormat":"american","dateFormat":"iso"},
        timeout=20
    )
    r.raise_for_status()
    return r.json(), r.headers.get("x-requests-remaining")

def flatten_odds(raw):
    rows=[]
    for game in raw:
        matchup=f"{game.get('away_team')} @ {game.get('home_team')}"
        for book in game.get("bookmakers",[]):
            for market in book.get("markets",[]):
                for o in market.get("outcomes",[]):
                    rows.append({
                        "Game":matchup,"Book":book.get("title",""),
                        "Market":market.get("key",""),"Selection":o.get("name",""),
                        "Line":o.get("point"),"Odds":o.get("price")
                    })
    return pd.DataFrame(rows)

# -------------------- Model --------------------
def team_strength(row):
    rdpg=float(row.RunDiff)/max(1,float(row.Games))
    return logit(float(row.WinPct)) + .11*rdpg

def pitcher_adj(stats):
    if stats["ERA"] is None or stats["IP"] < 5:
        return 0
    era=(4.30-stats["ERA"])*.085
    whip=0 if stats["WHIP"] is None else (1.30-stats["WHIP"])*.20
    k=0 if stats["K9"] is None else (stats["K9"]-8.5)*.018
    return clamp(era+whip+k,-.45,.45)

def build_models(schedule, standings):
    rows=[]
    for _,g in schedule.iterrows():
        a=standings[standings.TeamID==g.AwayID]
        h=standings[standings.TeamID==g.HomeID]
        if a.empty or h.empty: continue
        ar=a.iloc[0]; hr=h.iloc[0]
        ap=fetch_pitcher_stats(g.AwayPitcherID,SEASON)
        hp=fetch_pitcher_stats(g.HomePitcherID,SEASON)
        away_score=team_strength(ar)+pitcher_adj(ap)
        home_score=team_strength(hr)+pitcher_adj(hp)+.13
        hpct=logistic(home_score-away_score)
        apct=1-hpct
        rows.append({
            "Game":g.Game,"Start":g.Start,"Status":g.Status,
            "AwayTeam":g.AwayTeam,"HomeTeam":g.HomeTeam,
            "AwayProb":apct,"HomeProb":hpct,
            "AwayFair":fair_american(apct),"HomeFair":fair_american(hpct),
            "AwayPitcher":g.AwayPitcher,"HomePitcher":g.HomePitcher,
            "AwayERA":ap["ERA"],"HomeERA":hp["ERA"],
            "AwayWinPct":ar.WinPct,"HomeWinPct":hr.WinPct,
            "AwayRunDiff":ar.RunDiff,"HomeRunDiff":hr.RunDiff,
        })
    return pd.DataFrame(rows)

def best_moneylines(odds):
    ml=odds[odds.Market=="h2h"].copy()
    if ml.empty:return ml
    idx=ml.groupby(["Game","Selection"])["Odds"].idxmax()
    return ml.loc[idx].reset_index(drop=True)

def build_value_board(models,odds):
    if models.empty or odds.empty:return pd.DataFrame()
    prices=best_moneylines(odds)
    rows=[]
    for _,g in models.iterrows():
        for side in ("Away","Home"):
            team=g[f"{side}Team"]; prob=g[f"{side}Prob"]
            m=prices[(prices.Game==g.Game)&(prices.Selection==team)]
            if m.empty: continue
            best=m.iloc[0]
            e=edge_pct(prob,best.Odds)
            ev=ev_per_100(prob,best.Odds)
            gr=grade(e)
            rows.append({
                "Game":g.Game,"Start":g.Start,"Pick":team,
                "Odds":int(best.Odds),"Book":best.Book,
                "ModelProb":prob,"FairOdds":g[f"{side}Fair"],
                "Edge":e,"EV":ev,"Grade":gr,
                "Score":int(clamp(round(50+e*5),1,99)),
                "Reason":f"Model {prob*100:.1f}% vs market {implied_prob(best.Odds)*100:.1f}%."
            })
    return pd.DataFrame(rows).sort_values(["Edge","EV"],ascending=False)

# -------------------- Sidebar --------------------
with st.sidebar:
    st.markdown("## ⚾ Diamond Edge")
    page=st.radio(
        "Navigation",
        ["🏠 Dashboard","📅 Today’s Games","🎯 Player Props","⭐ Best Bets","📊 Analytics","💼 Bet Tracker","⚙️ Settings"],
        label_visibility="collapsed"
    )
    st.divider()
    selected_date=st.date_input("Slate date",TODAY)
    api_key=st.text_input(
        "The Odds API key",
        value=st.secrets.get("ODDS_API_KEY",os.getenv("ODDS_API_KEY","")),
        type="password"
    )
    region=st.selectbox("Odds region",["us","us2","eu","uk","au"])
    bankroll=st.number_input("Bankroll",min_value=0.0,value=500.0,step=25.0)
    unit_pct=st.slider("Unit size (%)",.25,5.0,1.0,.25)
    st.metric("1 Unit",f"${bankroll*unit_pct/100:,.2f}")

# -------------------- Load --------------------
try:
    schedule=fetch_schedule(str(selected_date))
except Exception:
    schedule=pd.DataFrame()

try:
    standings=fetch_standings(SEASON)
except Exception:
    standings=pd.DataFrame()

models=build_models(schedule,standings) if not schedule.empty and not standings.empty else pd.DataFrame()

odds=pd.DataFrame(); quota=None; odds_error=None
if api_key:
    try:
        raw,quota=fetch_odds(api_key,region)
        odds=flatten_odds(raw)
    except Exception as e:
        odds_error=str(e)

value_board=build_value_board(models,odds)

# -------------------- Reusable UI --------------------
def top_header(title,subtitle):
    c1,c2=st.columns([4,1])
    with c1:
        st.title(title)
        st.caption(subtitle)
    with c2:
        mode="LIVE ODDS" if not odds.empty else "MODEL ONLY"
        color="green" if not odds.empty else "yellow"
        st.markdown(f'<div style="text-align:right"><span class="badge {color}">{mode}</span></div>',unsafe_allow_html=True)

def show_bet_cards(df,limit=9):
    if df.empty:
        st.info("No qualifying bets are available.")
        return
    cols=st.columns(3)
    for i,(_,r) in enumerate(df.head(limit).iterrows()):
        with cols[i%3]:
            st.markdown(f"""
            <div class="card {card_color(r.Grade)}">
              <span class="badge {badge_color(r.Grade)}">GRADE {r.Grade}</span>
              <span class="badge blue">{r.Score}/99</span>
              <div class="muted" style="margin-top:10px">{r.Game} • {r.Start}</div>
              <div class="pick">{r.Pick} ({r.Odds:+d})</div>
              <div><b>Best book:</b> {r.Book}</div>
              <div style="margin-top:8px">Model: <b>{r.ModelProb*100:.1f}%</b> • Fair: <b>{r.FairOdds:+d}</b></div>
              <div>Edge: <b>{r.Edge:.1f}%</b> • EV: <b>${r.EV:.2f}/$100</b></div>
              <div class="muted" style="margin-top:9px">{r.Reason}</div>
            </div>
            """,unsafe_allow_html=True)

# -------------------- Pages --------------------
if page=="🏠 Dashboard":
    top_header("Diamond Edge MLB","Daily slate overview, strongest model leans, and live value.")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Games",len(schedule))
    c2.metric("Model Predictions",len(models))
    c3.metric("Live Books",odds.Book.nunique() if not odds.empty else 0)
    c4.metric("Value Bets",int((value_board.Edge>=1.5).sum()) if not value_board.empty else 0)

    st.markdown('<div class="title-small">Top Plays Today</div>',unsafe_allow_html=True)
    if value_board.empty:
        st.info("Add your Odds API key to convert model predictions into live value bets.")
        if not models.empty:
            preview=models.copy()
            preview["Model Pick"]=preview.apply(lambda r:r.HomeTeam if r.HomeProb>=r.AwayProb else r.AwayTeam,axis=1)
            preview["Win Probability"]=(preview[["AwayProb","HomeProb"]].max(axis=1)*100).round(1).astype(str)+"%"
            st.dataframe(preview[["Game","Start","Model Pick","Win Probability","AwayFair","HomeFair"]],use_container_width=True,hide_index=True)
    else:
        show_bet_cards(value_board[value_board.Edge>=1.5])

elif page=="📅 Today’s Games":
    top_header("Today’s Games","Click a matchup to see starters, model probabilities, and available prices.")
    if models.empty:
        st.warning("No games or model data are available for this date.")
    else:
        for _,r in models.iterrows():
            pick=r.HomeTeam if r.HomeProb>=r.AwayProb else r.AwayTeam
            with st.expander(f"{r.Game} • {r.Start} • Model pick: {pick}"):
                a,b=st.columns(2)
                with a:
                    st.subheader(r.AwayTeam)
                    st.write(f"Starter: {r.AwayPitcher}")
                    st.write(f"Starter ERA: {r.AwayERA if r.AwayERA is not None else 'N/A'}")
                    st.write(f"Win rate: {r.AwayWinPct*100:.1f}%")
                    st.write(f"Run differential: {int(r.AwayRunDiff):+d}")
                    st.metric("Model probability",f"{r.AwayProb*100:.1f}%")
                    st.metric("Fair odds",f"{r.AwayFair:+d}")
                with b:
                    st.subheader(r.HomeTeam)
                    st.write(f"Starter: {r.HomePitcher}")
                    st.write(f"Starter ERA: {r.HomeERA if r.HomeERA is not None else 'N/A'}")
                    st.write(f"Win rate: {r.HomeWinPct*100:.1f}%")
                    st.write(f"Run differential: {int(r.HomeRunDiff):+d}")
                    st.metric("Model probability",f"{r.HomeProb*100:.1f}%")
                    st.metric("Fair odds",f"{r.HomeFair:+d}")
                if not odds.empty:
                    game_odds=odds[odds.Game==r.Game]
                    if not game_odds.empty:
                        st.dataframe(game_odds.sort_values("Odds",ascending=False),use_container_width=True,hide_index=True)

elif page=="🎯 Player Props":
    top_header("Player Props","Strikeouts, total bases, hits, home runs, RBIs, and walks.")
    st.info("The prop pages are designed and ready. Real player-prop prices require an eligible event-markets API plan.")
    tabs=st.tabs(["Strikeouts","Total Bases","Hits","Home Runs","RBIs","Walks"])
    labels=[
        ("Pitcher Over","K rate, opponent strikeout rate, pitch count"),
        ("Hitter Over","Platoon split, hard-hit rate, park"),
        ("Hitter Over","Contact rate, pitch mix, lineup spot"),
        ("Hitter Yes","Barrel rate, fly-ball rate, weather"),
        ("Hitter Over","Lineup position, team total, traffic"),
        ("Hitter Over","Chase rate, pitcher walk rate, umpire"),
    ]
    for tab,(pick,inputs) in zip(tabs,labels):
        with tab:
            st.dataframe(pd.DataFrame([{
                "Player":"Awaiting live prop feed",
                "Suggested Market":pick,
                "Planned Inputs":inputs,
                "Status":"Data connection needed"
            }]),use_container_width=True,hide_index=True)

elif page=="⭐ Best Bets":
    top_header("Best Bets","Filter the slate by model edge and confidence.")
    if odds_error:
        st.error(f"Live odds could not load: {odds_error}")
    min_edge=st.slider("Minimum edge",0.0,12.0,1.5,.5)
    min_score=st.slider("Minimum score",1,99,55)
    filtered=value_board[(value_board.Edge>=min_edge)&(value_board.Score>=min_score)] if not value_board.empty else pd.DataFrame()
    show_bet_cards(filtered,12)

elif page=="📊 Analytics":
    top_header("Analytics","Model probabilities, fair odds, team strength, and market comparison.")
    if models.empty:
        st.warning("No model data available.")
    else:
        display=models.copy()
        display["Away Probability"]=(display.AwayProb*100).round(1)
        display["Home Probability"]=(display.HomeProb*100).round(1)
        st.dataframe(
            display[["Game","Start","AwayPitcher","HomePitcher","Away Probability","Home Probability","AwayFair","HomeFair","AwayRunDiff","HomeRunDiff"]],
            use_container_width=True,hide_index=True
        )
        if not value_board.empty:
            st.markdown("### Market Value Table")
            st.dataframe(value_board,use_container_width=True,hide_index=True)

elif page=="💼 Bet Tracker":
    top_header("Bet Tracker","Track bets, units, profit, and ROI.")
    if "tracker" not in st.session_state:
        st.session_state.tracker=pd.DataFrame(columns=["Date","Bet","Odds","Stake","Result","Profit"])
    with st.form("bet_form",clear_on_submit=True):
        c1,c2,c3=st.columns(3)
        bet=c1.text_input("Bet")
        b_odds=c2.number_input("Odds",value=-110,step=5)
        stake=c3.number_input("Stake",min_value=1.0,value=10.0,step=5.0)
        c4,c5=st.columns(2)
        result=c4.selectbox("Result",["Pending","Win","Loss","Push"])
        b_date=c5.date_input("Date",selected_date)
        add=st.form_submit_button("Add Bet")
    if add and bet:
        profit=stake*(decimal_odds(b_odds)-1) if result=="Win" else -stake if result=="Loss" else 0
        row=pd.DataFrame([[str(b_date),bet,b_odds,stake,result,round(profit,2)]],columns=st.session_state.tracker.columns)
        st.session_state.tracker=pd.concat([st.session_state.tracker,row],ignore_index=True)
    if not st.session_state.tracker.empty:
        tracked=st.session_state.tracker
        settled=tracked[tracked.Result.isin(["Win","Loss","Push"])]
        total_staked=settled.Stake.sum()
        total_profit=settled.Profit.sum()
        roi=(total_profit/total_staked*100) if total_staked else 0
        a,b,c=st.columns(3)
        a.metric("Profit",f"${total_profit:.2f}")
        b.metric("ROI",f"{roi:.1f}%")
        c.metric("Bets",len(tracked))
        st.dataframe(tracked,use_container_width=True,hide_index=True)
        st.download_button("Download CSV",tracked.to_csv(index=False),"diamond_edge_bets.csv","text/csv")
    else:
        st.info("No bets have been added.")

elif page=="⚙️ Settings":
    top_header("Settings","Data connections and model status.")
    st.write("✅ MLB schedule connection" if not schedule.empty else "⚠️ MLB schedule unavailable")
    st.write("✅ MLB standings connection" if not standings.empty else "⚠️ MLB standings unavailable")
    st.write("✅ Live sportsbook odds" if not odds.empty else "⚠️ Add an Odds API key for live prices")
    st.write("⚠️ Player-prop feed not connected")
    st.write("⚠️ Weather, injuries, confirmed lineups, bullpen workload, and umpire data are planned")
    if quota is not None:
        st.caption(f"Odds API requests remaining: {quota}")
    st.markdown("""
    ### Add the odds key securely
    Open your Streamlit app settings, choose **Secrets**, and add:

    ```toml
    ODDS_API_KEY = "your_key_here"
    ```
    """)

st.divider()
st.caption("Diamond Edge is an analysis tool, not a guarantee of profit. Verify all lines before betting.")

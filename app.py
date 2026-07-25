
import os
from datetime import datetime, timezone, timedelta
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

# -------------------- Theme --------------------
st.markdown("""
<style>
:root {
  --bg:#07111f; --panel:#0d1b2b; --panel2:#10243a;
  --line:#1e3852; --text:#edf5ff; --muted:#8ea6bd;
  --green:#22c55e; --yellow:#f59e0b; --red:#ef4444; --blue:#38bdf8;
}
.stApp {background:linear-gradient(180deg,#06101d 0%,#091728 100%); color:var(--text);}
.block-container {padding-top:1rem; padding-bottom:3rem; max-width:1500px;}
[data-testid="stSidebar"] {background:#081422; border-right:1px solid var(--line);}
div[data-testid="stMetric"] {
  background:linear-gradient(145deg,#0d1b2b,#10243a);
  border:1px solid var(--line); border-radius:16px; padding:14px;
}
.bet-card {
  background:linear-gradient(145deg,#0d1b2b,#10243a);
  border:1px solid var(--line); border-radius:18px;
  padding:18px; margin-bottom:12px; min-height:205px;
}
.grade-a {border-left:5px solid var(--green);}
.grade-b {border-left:5px solid #84cc16;}
.grade-c {border-left:5px solid var(--yellow);}
.grade-pass {border-left:5px solid var(--red);}
.badge {display:inline-block; padding:4px 9px; border-radius:999px; font-size:.75rem; font-weight:800;}
.green {background:rgba(34,197,94,.16);color:#7df3a6;border:1px solid rgba(34,197,94,.35);}
.yellow {background:rgba(245,158,11,.16);color:#ffd177;border:1px solid rgba(245,158,11,.35);}
.red {background:rgba(239,68,68,.16);color:#ff9595;border:1px solid rgba(239,68,68,.35);}
.blue {background:rgba(56,189,248,.16);color:#8edcff;border:1px solid rgba(56,189,248,.35);}
.muted {color:var(--muted); font-size:.88rem;}
.big-pick {font-size:1.18rem;font-weight:850;margin:.5rem 0;}
.section-title {font-size:1.35rem;font-weight:850;margin-top:.4rem;}
hr {border-color:var(--line);}
.stTabs [data-baseweb="tab-list"] {gap:8px;}
.stTabs [data-baseweb="tab"] {background:#0d1b2b;border-radius:10px;padding:8px 14px;}
</style>
""", unsafe_allow_html=True)

CENTRAL = ZoneInfo("America/Chicago")

# -------------------- Math --------------------
def implied_prob(odds):
    odds = float(odds)
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def decimal_odds(odds):
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)

def ev_per_100(prob, odds):
    d = decimal_odds(float(odds))
    return 100 * (prob * (d - 1) - (1 - prob))

def edge(prob, odds):
    return (prob - implied_prob(odds)) * 100

def grade_from_edge(x):
    if x >= 7: return "A"
    if x >= 4: return "B"
    if x >= 1.5: return "C"
    return "PASS"

def color_from_grade(g):
    return "green" if g in ("A","B") else "yellow" if g == "C" else "red"

def css_grade(g):
    return "grade-a" if g == "A" else "grade-b" if g == "B" else "grade-c" if g == "C" else "grade-pass"

def format_start(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z","+00:00")).astimezone(CENTRAL).strftime("%a %-I:%M %p CT")
    except Exception:
        return iso

# -------------------- Data --------------------
@st.cache_data(ttl=300)
def get_schedule(date_str):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"sportId":1, "date":date_str, "hydrate":"probablePitcher"}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    rows = []
    for day in data.get("dates", []):
        for game in day.get("games", []):
            teams = game.get("teams", {})
            away = teams.get("away", {}).get("team", {}).get("name", "")
            home = teams.get("home", {}).get("team", {}).get("name", "")
            away_p = game.get("teams", {}).get("away", {}).get("probablePitcher", {}).get("fullName", "TBD")
            home_p = game.get("teams", {}).get("home", {}).get("probablePitcher", {}).get("fullName", "TBD")
            rows.append({
                "Game": f"{away} @ {home}",
                "Away": away, "Home": home,
                "Start": format_start(game.get("gameDate","")),
                "Status": game.get("status", {}).get("detailedState",""),
                "Away Starter": away_p, "Home Starter": home_p,
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=180)
def get_odds(api_key, regions="us", markets="h2h,spreads,totals"):
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        "apiKey":api_key, "regions":regions, "markets":markets,
        "oddsFormat":"american", "dateFormat":"iso", "includeLinks":"true"
    }
    r = requests.get(url, params=params, timeout=20)
    remaining = r.headers.get("x-requests-remaining")
    used = r.headers.get("x-requests-used")
    r.raise_for_status()
    return r.json(), remaining, used

def flatten_odds(games):
    rows = []
    for g in games:
        matchup = f"{g.get('away_team')} @ {g.get('home_team')}"
        for b in g.get("bookmakers", []):
            for m in b.get("markets", []):
                for o in m.get("outcomes", []):
                    rows.append({
                        "Game":matchup,
                        "Start":format_start(g.get("commence_time","")),
                        "Book":b.get("title",""),
                        "Market":m.get("key",""),
                        "Selection":o.get("name",""),
                        "Line":o.get("point"),
                        "Odds":o.get("price"),
                        "Updated":b.get("last_update",""),
                    })
    return pd.DataFrame(rows)

def best_prices(df):
    if df.empty:
        return df
    x = df.copy()
    x["LineKey"] = x["Line"].fillna(0)
    idx = x.groupby(["Game","Market","Selection","LineKey"])["Odds"].idxmax()
    return x.loc[idx].sort_values(["Game","Market","Selection"]).reset_index(drop=True)

def demo_bets():
    return pd.DataFrame([
        ["Houston Astros @ Texas Rangers","Moneyline","Houston Astros",None,-118,.565,"Starting pitcher + bullpen"],
        ["Los Angeles Dodgers @ San Francisco Giants","Run Line","Los Angeles Dodgers",-1.5,124,.475,"Offense depth + late innings"],
        ["New York Yankees @ Boston Red Sox","Total","Over",8.5,-105,.545,"Park + contact matchup"],
        ["Seattle Mariners @ Minnesota Twins","Pitcher Ks","Starter Over",6.5,110,.505,"Opponent strikeout profile"],
        ["Atlanta Braves @ Miami Marlins","Total Bases","Hitter Over",1.5,135,.455,"Platoon + hard-hit profile"],
        ["Chicago Cubs @ St. Louis Cardinals","Home Run","Hitter Yes",None,390,.235,"Barrel + fly-ball matchup"],
    ], columns=["Game","Market","Pick","Line","Odds","ModelProb","Reason"])

def build_demo_rankings():
    d = demo_bets()
    d["Edge"] = d.apply(lambda r: edge(r.ModelProb,r.Odds),axis=1)
    d["EV"] = d.apply(lambda r: ev_per_100(r.ModelProb,r.Odds),axis=1)
    d["Grade"] = d.Edge.apply(grade_from_edge)
    d["Score"] = (50 + d.Edge*5).clip(1,99).round().astype(int)
    return d.sort_values(["Grade","EV"],ascending=[True,False])

# -------------------- Sidebar --------------------
with st.sidebar:
    st.markdown("## ⚾ Diamond Edge")
    st.caption("MLB analysis dashboard")
    selected_date = st.date_input("Slate date", datetime.now(CENTRAL).date())
    api_key = st.text_input(
        "The Odds API key",
        value=st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY","")),
        type="password",
        help="Needed for real sportsbook odds."
    )
    region = st.selectbox("Odds region", ["us","us2","eu","uk","au"])
    min_edge_filter = st.slider("Minimum model edge",0.0,12.0,1.5,.5)
    min_score = st.slider("Minimum score",1,99,55)
    st.divider()
    bankroll = st.number_input("Bankroll",min_value=0.0,value=500.0,step=25.0)
    unit_pct = st.slider("Unit size (% of bankroll)",.25,5.0,1.0,.25)
    st.metric("1 Unit",f"${bankroll*unit_pct/100:,.2f}")
    st.caption("Only bet money you can afford to lose.")

# -------------------- Load --------------------
schedule_error = None
try:
    schedule = get_schedule(str(selected_date))
except Exception as e:
    schedule = pd.DataFrame()
    schedule_error = str(e)

odds = pd.DataFrame()
quota_remaining = quota_used = None
odds_error = None
if api_key:
    try:
        raw, quota_remaining, quota_used = get_odds(api_key, region)
        odds = flatten_odds(raw)
    except Exception as e:
        odds_error = str(e)

# -------------------- Header --------------------
left, right = st.columns([4,1])
with left:
    st.markdown("# Diamond Edge MLB")
    st.caption("Best prices • matchup board • model grades • EV tools • betting tracker")
with right:
    mode = "LIVE ODDS" if not odds.empty else "DEMO MODE"
    cls = "green" if not odds.empty else "yellow"
    st.markdown(f'<div style="text-align:right"><span class="badge {cls}">{mode}</span></div>',unsafe_allow_html=True)

tabs = st.tabs(["🏆 Top Bets","⚾ Today’s Games","💵 Best Odds","🎯 Player Props","🧮 EV Lab","📒 Bet Tracker","ℹ️ Setup"])

# -------------------- TOP BETS --------------------
with tabs[0]:
    rankings = build_demo_rankings()
    rankings = rankings[(rankings.Edge >= min_edge_filter) & (rankings.Score >= min_score)]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Games Today",len(schedule))
    c2.metric("Qualifying Plays",len(rankings))
    c3.metric("Best Score",f"{rankings.Score.max()}/99" if len(rankings) else "—")
    c4.metric("Live Books",odds.Book.nunique() if not odds.empty else 0)

    st.markdown('<div class="section-title">Top Rated Plays</div>',unsafe_allow_html=True)
    st.caption("Demo model grades are clearly marked until a full projection-data connection is added.")

    if rankings.empty:
        st.warning("No plays meet your filters.")
    else:
        cols = st.columns(3)
        for i,(_,r) in enumerate(rankings.head(9).iterrows()):
            with cols[i%3]:
                line_text = "" if pd.isna(r.Line) else f" {r.Line:g}"
                badge = color_from_grade(r.Grade)
                st.markdown(f"""
                <div class="bet-card {css_grade(r.Grade)}">
                  <span class="badge {badge}">GRADE {r.Grade}</span>
                  <span class="badge blue">{r.Score}/99</span>
                  <div class="muted" style="margin-top:10px">{r.Game}</div>
                  <div class="big-pick">{r.Pick}{line_text} ({int(r.Odds):+d})</div>
                  <div><b>{r.Market}</b></div>
                  <div style="margin-top:10px">Edge: <b>{r.Edge:.1f}%</b> &nbsp; EV: <b>${r.EV:.2f}/$100</b></div>
                  <div class="muted" style="margin-top:10px">{r.Reason}</div>
                </div>
                """,unsafe_allow_html=True)

# -------------------- GAMES --------------------
with tabs[1]:
    st.markdown('<div class="section-title">MLB Slate</div>',unsafe_allow_html=True)
    if schedule_error:
        st.error(f"Schedule could not load: {schedule_error}")
    elif schedule.empty:
        st.info("No MLB games found for this date.")
    else:
        for _,g in schedule.iterrows():
            with st.expander(f"{g.Game}  •  {g.Start}  •  {g.Status}"):
                c1,c2,c3 = st.columns([2,1,2])
                c1.markdown(f"**{g.Away}**  \nStarter: {g['Away Starter']}")
                c2.markdown("<div style='text-align:center;font-size:1.4rem;font-weight:900'>@</div>",unsafe_allow_html=True)
                c3.markdown(f"**{g.Home}**  \nStarter: {g['Home Starter']}")
                matching = odds[odds.Game.eq(g.Game)] if not odds.empty else pd.DataFrame()
                if not matching.empty:
                    st.dataframe(best_prices(matching)[["Market","Selection","Line","Odds","Book"]],use_container_width=True,hide_index=True)
                else:
                    st.caption("No connected sportsbook lines for this game.")

# -------------------- BEST ODDS --------------------
with tabs[2]:
    st.markdown('<div class="section-title">Best Available Prices</div>',unsafe_allow_html=True)
    if odds_error:
        st.error(f"Odds could not load: {odds_error}")
    if odds.empty:
        st.warning("Add your API key in the sidebar to compare real sportsbook prices.")
    else:
        b = best_prices(odds)
        market_map = {"h2h":"Moneyline","spreads":"Run Line","totals":"Total"}
        b["Market"] = b.Market.map(market_map).fillna(b.Market)
        games = st.multiselect("Games",sorted(b.Game.unique()),default=sorted(b.Game.unique()))
        books = st.multiselect("Sportsbooks",sorted(b.Book.unique()),default=sorted(b.Book.unique()))
        view = b[b.Game.isin(games)&b.Book.isin(books)]
        st.dataframe(view[["Game","Start","Market","Selection","Line","Odds","Book"]],use_container_width=True,hide_index=True)
        if quota_remaining is not None:
            st.caption(f"API requests remaining: {quota_remaining} • Used: {quota_used}")

# -------------------- PROPS --------------------
with tabs[3]:
    st.markdown('<div class="section-title">Player Prop Center</div>',unsafe_allow_html=True)
    st.info("The interface is ready. Real player props require an API plan that includes MLB event markets.")
    prop_tabs = st.tabs(["Strikeouts","Total Bases","Hits","Home Runs","RBIs","Walks"])
    examples = {
        "Strikeouts":["Pitcher Over 6.5","K matchup","Velocity","Pitch count"],
        "Total Bases":["Hitter Over 1.5","Platoon split","Hard-hit rate","Park factor"],
        "Hits":["Hitter Over 0.5","Contact rate","Pitch mix","Lineup spot"],
        "Home Runs":["Hitter Yes","Barrel rate","Fly-ball rate","Weather"],
        "RBIs":["Hitter Over 0.5","Lineup position","Team total","On-base traffic"],
        "Walks":["Hitter Over 0.5","Chase rate","Pitcher BB%","Umpire zone"],
    }
    for tab,(name,vals) in zip(prop_tabs,examples.items()):
        with tab:
            st.dataframe(pd.DataFrame([{
                "Player":"Example Player","Pick":vals[0],"Best Odds":"+110",
                "Score":"68/99","Primary Edge":vals[1],"Secondary":vals[2],"Context":vals[3]
            }]),use_container_width=True,hide_index=True)

# -------------------- EV --------------------
with tabs[4]:
    st.markdown('<div class="section-title">Expected Value Lab</div>',unsafe_allow_html=True)
    a,b,c = st.columns(3)
    user_odds = a.number_input("American odds",value=-110,step=5)
    user_prob = b.number_input("Your win probability (%)",1.0,99.0,55.0,.5)
    stake = c.number_input("Stake",1.0,10000.0,100.0,5.0)
    p = user_prob/100
    imp = implied_prob(user_odds)
    ev100 = ev_per_100(p,user_odds)
    evstake = ev100*stake/100
    e = edge(p,user_odds)
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Break-even",f"{imp*100:.1f}%")
    m2.metric("Model edge",f"{e:.1f}%")
    m3.metric("EV per $100",f"${ev100:.2f}")
    m4.metric("EV on stake",f"${evstake:.2f}")
    st.success("Positive expected value." if evstake>0 else "This price is negative expected value based on your estimate.")

# -------------------- TRACKER --------------------
with tabs[5]:
    st.markdown('<div class="section-title">Bet Tracker</div>',unsafe_allow_html=True)
    st.caption("Enter bets below, then download the tracker as a CSV. Persistent cloud storage can be added later.")
    if "tracker" not in st.session_state:
        st.session_state.tracker = pd.DataFrame(columns=["Date","Bet","Odds","Stake","Result","Profit"])
    with st.form("bet_form",clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        bet_name = c1.text_input("Bet")
        bet_odds = c2.number_input("Odds",value=-110,step=5)
        bet_stake = c3.number_input("Stake",min_value=1.0,value=10.0,step=5.0)
        c4,c5 = st.columns(2)
        result = c4.selectbox("Result",["Pending","Win","Loss","Push"])
        bet_date = c5.date_input("Date",selected_date)
        add = st.form_submit_button("Add Bet")
    if add and bet_name:
        if result=="Win": profit = bet_stake*(decimal_odds(bet_odds)-1)
        elif result=="Loss": profit = -bet_stake
        else: profit = 0
        new = pd.DataFrame([[str(bet_date),bet_name,bet_odds,bet_stake,result,round(profit,2)]],
                           columns=st.session_state.tracker.columns)
        st.session_state.tracker = pd.concat([st.session_state.tracker,new],ignore_index=True)
    if not st.session_state.tracker.empty:
        st.dataframe(st.session_state.tracker,use_container_width=True,hide_index=True)
        st.metric("Tracked Profit",f"${st.session_state.tracker.Profit.sum():.2f}")
        st.download_button("Download Tracker CSV",st.session_state.tracker.to_csv(index=False),
                           "mlb_bet_tracker.csv","text/csv")
    else:
        st.info("No bets added yet.")

# -------------------- SETUP --------------------
with tabs[6]:
    st.markdown('<div class="section-title">Connection Status</div>',unsafe_allow_html=True)
    st.write("✅ MLB schedule connection" if not schedule.empty else "⚠️ MLB schedule unavailable")
    st.write("✅ Live sportsbook odds" if not odds.empty else "⚠️ Add The Odds API key for live odds")
    st.write("⚠️ Player-prop feed requires eligible API access")
    st.write("⚠️ Weather, injuries, umpire data, and true projection models need additional data sources")
    st.markdown("""
    ### Add the API key securely
    In Streamlit, open **Manage app → Settings → Secrets** and add:

    ```toml
    ODDS_API_KEY = "your_key_here"
    ```

    Then save and reboot the app.
    """)

st.divider()
st.caption("Diamond Edge is an analysis tool. Model scores are not guarantees. Verify lines before betting.")

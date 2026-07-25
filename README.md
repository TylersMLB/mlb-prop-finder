# Diamond Edge MLB — Version 2

This upgraded Streamlit app includes:

- Polished dark dashboard
- Daily MLB schedule and probable starters
- Top-rated bet cards
- Best sportsbook price comparison
- Moneylines, run lines, and totals
- Player-prop center
- EV calculator
- Bankroll unit calculator
- Downloadable betting tracker
- Mobile-friendly layout

## Replace your current app

Upload these files to the root of your existing GitHub repository:

- `app.py`
- `requirements.txt`

Choose **Replace** when GitHub warns that the files already exist, then commit the changes.

Streamlit should automatically redeploy.

## Live odds setup

Create a key with The Odds API, then add it in Streamlit:

1. Open the app dashboard in Streamlit.
2. Open **Manage app**.
3. Select **Settings**.
4. Open **Secrets**.
5. Add:

```toml
ODDS_API_KEY = "your_key_here"
```

6. Save and reboot.

## Honest limitations

The app includes a polished prop interface and demo model cards. A real predictive model, injuries, umpire data, weather adjustments, public betting percentages, and live player-prop feeds require additional data sources and/or paid API access.

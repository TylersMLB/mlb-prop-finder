# MLB Betting Dashboard

A Streamlit dashboard for:

- MLB moneylines
- Run lines
- Game totals
- Player props
- Expected value
- Confidence grades
- Best-bets filtering
- Live sportsbook lines through The Odds API

## Fastest setup

1. Upload every file in this folder to a new GitHub repository.
2. Go to Streamlit Community Cloud.
3. Click **Create app**.
4. Select your GitHub repository.
5. Set the main file path to:

```text
app.py
```

6. Deploy.

The app works immediately in demo mode.

## Live odds

Create an account with The Odds API and get an API key.

In the app, paste the key into the sidebar.

For a more secure deployment, add this to Streamlit Secrets:

```toml
ODDS_API_KEY = "your_key_here"
```

Then change the app later to read the secret automatically, or set it as an environment variable.

## Important limitation

Live player props often require a paid data plan. This version includes a working props interface and example model output, but not a paid props feed.

## Run it on your computer

Open a terminal inside the project folder and run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

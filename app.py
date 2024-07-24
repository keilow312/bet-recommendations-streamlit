import streamlit as st
import requests
import pandas as pd
import re

def get_bet_recommendations(bankroll, win_rate, access_token):
    # Function to fetch daily picks from the API
    def fetch_daily_picks(access_token):
        url = "http://api.wagergpt.co/daily-picks"
        params = {'access_token': access_token}
        response = requests.get(url, params=params)
        
        # Check for API request errors
        if response.status_code == 401:
            raise Exception("API request failed with status code 401: Unauthorized. Please check your access token.")
        elif response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}: {response.json()}")
        
        return response.json()

    # Calculate max daily risk
    max_daily_risk = 0.5 * bankroll

    # Fetch daily picks from the API
    try:
        daily_picks = fetch_daily_picks(access_token)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

    # Debug: Print the raw API response
    st.write("API Response:", daily_picks)

    # Extract picks from the response
    picks_string = daily_picks.get('picks', '')
    if not picks_string:
        st.error("No picks found in the API response.")
        return None
    
    # Parse the picks for MLB
    pattern = re.compile(r"(\d+\.\s)([\w\s]+)\s([-\d\.]+)\s@\s(\d+\.\d+)")
    picks = pattern.findall(picks_string)
    
    # Debug: Print the extracted picks
    st.write("Extracted Picks:", picks)

    # Prepare the bets list
    bets = []
    for pick in picks:
        bet_number, team, point_spread, odds = pick
        bets.append({
            "Sport": "MLB",
            "Bet Recommendation": f"{team.strip()} {point_spread.strip()}",
            "Odds": float(odds),
            "WinRate": win_rate,
            "ROI": 0.0  # Placeholder as the actual ROI is not given
        })

    # Debug: Print the bets list
    st.write("Bets List:", bets)

    # Convert the data to a DataFrame
    df_bets = pd.DataFrame(bets)

    # Debug: Print the DataFrame
    st.write("DataFrame before calculations:", df_bets)

    if df_bets.empty:
        st.error("No bets available after parsing.")
        return None

    # Assign EV for the bets
    def calculate_ev(row):
        win_rate = row['WinRate']
        return (win_rate * (row['Odds'] - 1) - (1 - win_rate))

    df_bets['EV'] = df_bets.apply(calculate_ev, axis=1)

    # Function to calculate the recommended bet size
    def recommended_bet_size(bankroll, ev, odds):
        kelly_fraction = ev / (odds - 1)
        half_kelly_fraction = kelly_fraction / 2  # Applying half Kelly
        return bankroll * half_kelly_fraction

    # Calculate recommended bet sizes
    df_bets['Recommended Bet Size'] = df_bets.apply(lambda x: recommended_bet_size(bankroll, x['EV'], x['Odds']), axis=1)

    # Ensure total bet size does not exceed max_daily_risk
    if df_bets['Recommended Bet Size'].sum() > max_daily_risk:
        df_bets['Recommended Bet Size'] = (df_bets['Recommended Bet Size'] / df_bets['Recommended Bet Size'].sum()) * max_daily_risk

    return df_bets[['Bet Recommendation', 'Odds', 'Recommended Bet Size']]

# Streamlit Front End
st.title("Bet Recommendations")

# Sidebar Inputs
st.sidebar.title("Input Parameters")
access_token = st.sidebar.text_input("Access Token")
bankroll = st.sidebar.number_input("Bankroll Amount", min_value=0)
win_rate = st.sidebar.slider("Win Rate (%)", min_value=0, max_value=100, value=52) / 100  # Default to 52%

if st.sidebar.button("Get Recommendations"):
    if access_token and bankroll > 0:
        recommendations = get_bet_recommendations(bankroll, win_rate, access_token)
        if recommendations is not None:
            st.markdown("<h2 style='text-align: center;'>Final Bet Recommendations</h2>", unsafe_allow_html=True)
            st.dataframe(
                recommendations.style.applymap(
                    lambda x: 'color: red;' if x < 0 else 'color: green;' if x > 0 else 'color: black;',
                    subset=['Recommended Bet Size']
                ).set_table_styles(
                    [{'selector': 'table', 'props': [('width', '100%')]}]
                )
            )
            st.bar_chart(recommendations.set_index('Bet Recommendation')['Recommended Bet Size'])
            st.line_chart(recommendations.set_index('Bet Recommendation')['Odds'])
    else:
        st.error("Please provide a valid access token and bankroll amount.")

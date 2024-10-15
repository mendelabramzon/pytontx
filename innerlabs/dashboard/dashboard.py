import json
import requests
import pandas as pd
import dash
from dash import html, dash_table, dcc
from dash.dependencies import Input, Output
import datetime

# Load tickers from pairs_data.json
try:
    with open('pairs_data.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print("Error: 'pairs_data.json' not found.")
    exit()

# Extract the list of tickers from the 'data' key
try:
    tickers = [item['name'] for item in data['data']]
    tickers = tickers[:20]  # Limit to first 5 tickers
except KeyError:
    print("Error: Incorrect structure in 'pairs_data.json'. Expected key 'data'.")
    exit()

print(f"Tickers loaded: {tickers}")

# Initialize the Dash app
app = dash.Dash(__name__)
app.title = "Latest Trades Dashboard"

# Define the layout of the app
app.layout = html.Div([
    html.H1("Latest Trades Dashboard"),
    dash_table.DataTable(
        id='trades-table',
        columns=[
            {"name": "Ticker", "id": "ticker"},
            {"name": "Price", "id": "price"},
            {"name": "Amount", "id": "amount"},
            {"name": "Side", "id": "side"},
            {"name": "Timestamp", "id": "timestamp"},
        ],
        data=[],
        page_size=20,
        sort_action='native',
        style_table={'overflowX': 'auto'},
    ),
    dcc.Interval(
        id='interval-component',
        interval=60*1000,  # Update every minute (milliseconds)
        n_intervals=0
    )
])

# Define the callback to update the trades table
@app.callback(
    Output('trades-table', 'data'),
    Input('interval-component', 'n_intervals')
)
def update_table(n):
    print("Update table called")
    all_trades = []
    for ticker in tickers:
        url = f"https://trade.ton-rocket.com/trades/last/{ticker}?limit=100"
        print(f"Fetching data for {ticker}")
        try:
            response = requests.get(url)
            if response.status_code == 200:
                response_json = response.json()
                if response_json.get('success'):
                    trades = response_json.get('data', [])
                    for trade in trades:
                        trade_data = {}
                        trade_data['ticker'] = ticker
                        trade_data['price'] = trade.get('price')
                        trade_data['amount'] = trade.get('amount')
                        trade_data['side'] = trade.get('side')
                        if 'orderTime' in trade:
                            # Parse orderTime from ISO 8601 format
                            trade_data['timestamp'] = datetime.datetime.strptime(
                                trade['orderTime'], '%Y-%m-%dT%H:%M:%S.%fZ'
                            ).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            trade_data['timestamp'] = ''
                        all_trades.append(trade_data)
                else:
                    print(f"Failed to retrieve trades for {ticker}: API returned success=false")
            else:
                print(f"Failed to retrieve trades for {ticker}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")

    # Convert the list of trades to a DataFrame
    df = pd.DataFrame(all_trades)
    if not df.empty:
        # Sort trades by timestamp in descending order
        df = df.sort_values(by='timestamp', ascending=False)
        return df.to_dict('records')
    else:
        print("No trade data available.")
        return []

# Run the Dash app
if __name__ == '__main__':
    print("Starting Dash app...")
    app.run_server(debug=True)
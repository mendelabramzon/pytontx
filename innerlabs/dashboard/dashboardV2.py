import json
import aiohttp
import asyncio
import pandas as pd
import dash
from dash import html, dash_table, dcc
from dash.dependencies import Input, Output
import datetime
from flask import Flask
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
import plotly.express as px

# User-defined parameter: Number of top tickers to process
TOP_N_TICKERS = 50  # You can adjust this number as needed

# MongoDB connection details
MONGO_URI = "mongodb://localhost:27017"  # Replace with your MongoDB URI
DATABASE_NAME = "trade_data"
COLLECTION_NAME = "trades"

# Connect to MongoDB
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[DATABASE_NAME]
    trades_collection = db[COLLECTION_NAME]
    print("Connected to MongoDB")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    exit()

# Create indexes to optimize queries
trades_collection.create_index([("ticker", ASCENDING), ("timestamp_dt", DESCENDING)], unique=True)

# Load tickers and volumes from pairs_data.json
try:
    with open('pairs_data.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print("Error: 'pairs_data.json' not found.")
    exit()

# Extract the list of tickers and their volumes from the 'data' key
try:
    pairs = data['data']
except KeyError:
    print("Error: Incorrect structure in 'pairs_data.json'. Expected key 'data'.")
    exit()

# Create a list of dictionaries with 'name' and 'volume'
tickers_with_volume = []
for item in pairs:
    ticker_name = item.get('name')
    volume = item.get('quoteVolume24h', 0)  # Use 0 if 'quoteVolume24h' is missing
    tickers_with_volume.append({'name': ticker_name, 'volume': volume})

# Sort the tickers by volume in descending order
sorted_tickers = sorted(tickers_with_volume, key=lambda x: x['volume'], reverse=True)

# Select the top N tickers
top_tickers = [item['name'] for item in sorted_tickers[:TOP_N_TICKERS]]

print(f"Top {TOP_N_TICKERS} tickers by volume: {top_tickers}")

# Initialize the Dash app with a Flask server
server = Flask(__name__)
app = dash.Dash(__name__, server=server)
app.title = "Latest Trades Dashboard"

# Define the layout of the app
app.layout = html.Div([
    html.H1("Latest Trades Dashboard"),
    html.Div([
        html.H2("Trade Statistics (Last 24 Hours)"),
        dcc.Graph(id='volume-bar-chart'),
        dcc.Graph(id='price-change-bar-chart'),
    ]),
    html.Div([
        html.H2("Latest Trades"),
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
    ]),
    dcc.Interval(
        id='interval-component',
        interval=60*1000,  # Update every minute (milliseconds)
        n_intervals=0
    )
])

# Asynchronous function to fetch data for a single ticker
async def fetch_ticker_data(session, ticker):
    url = f"https://trade.ton-rocket.com/trades/last/{ticker}?limit=100"
    print(f"Fetching data for {ticker}")
    try:
        async with session.get(url) as response:
            if response.status == 200:
                response_json = await response.json()
                if response_json.get('success'):
                    trades = response_json.get('data', [])
                    trades_data = []
                    for trade in trades:
                        trade_data = {}
                        trade_data['ticker'] = ticker
                        trade_data['price'] = trade.get('price')
                        trade_data['amount'] = trade.get('amount')
                        trade_data['side'] = trade.get('side')
                        if 'orderTime' in trade:
                            # Parse orderTime from ISO 8601 format
                            try:
                                timestamp = datetime.datetime.strptime(
                                    trade['orderTime'], '%Y-%m-%dT%H:%M:%S.%fZ'
                                )
                            except ValueError:
                                # Handle cases where microseconds are missing
                                timestamp = datetime.datetime.strptime(
                                    trade['orderTime'], '%Y-%m-%dT%H:%M:%S.%fZ'
                                )
                            trade_data['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                            # Use timestamp as datetime object for MongoDB
                            trade_data['timestamp_dt'] = timestamp
                        else:
                            trade_data['timestamp'] = ''
                            trade_data['timestamp_dt'] = None
                        # Insert into MongoDB
                        await insert_trade_into_db(trade_data)
                        trades_data.append(trade_data)
                    return trades_data
                else:
                    print(f"Failed to retrieve trades for {ticker}: API returned success=false")
                    return []
            else:
                print(f"Failed to retrieve trades for {ticker}: HTTP {response.status}")
                return []
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return []

# Function to insert trade data into MongoDB
async def insert_trade_into_db(trade_data):
    try:
        # Use a unique identifier for each trade (e.g., ticker + timestamp)
        trade_record = {
            'ticker': trade_data['ticker'],
            'price': trade_data['price'],
            'amount': trade_data['amount'],
            'side': trade_data['side'],
            'timestamp': trade_data['timestamp'],
            'timestamp_dt': trade_data['timestamp_dt'],
        }
        # Insert the trade record into the collection
        # Use upsert to avoid duplicates
        result = trades_collection.update_one(
            {'ticker': trade_record['ticker'], 'timestamp': trade_record['timestamp']},
            {'$setOnInsert': trade_record},
            upsert=True
        )
        if result.upserted_id:
            print(f"Inserted new trade for {trade_data['ticker']} at {trade_data['timestamp']}")
    except DuplicateKeyError:
        # Ignore duplicate entries
        pass
    except Exception as e:
        print(f"Error inserting trade into MongoDB: {e}")

# Asynchronous function to fetch data for all tickers
async def fetch_all_tickers_data():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_ticker_data(session, ticker) for ticker in top_tickers]
        results = await asyncio.gather(*tasks)
        # Flatten the list of lists into a single list of trades
        all_trades = [trade for trades in results for trade in trades]
        return all_trades

# Function to compute statistics from MongoDB
def compute_statistics():
    now = datetime.datetime.utcnow()
    last_24h = now - datetime.timedelta(hours=24)
    
    pipeline = [
        {'$match': {'timestamp_dt': {'$gte': last_24h}, 'ticker': {'$in': top_tickers}}},
        {'$group': {
            '_id': '$ticker',
            'total_volume': {'$sum': '$amount'},
            'average_trade_size': {'$avg': '$amount'},
            'number_of_trades': {'$sum': 1},
            'prices': {'$push': '$price'},
            'timestamps': {'$push': '$timestamp_dt'},
        }},
        {'$project': {
            'total_volume': 1,
            'average_trade_size': 1,
            'number_of_trades': 1,
            'first_price': {'$arrayElemAt': ['$prices', 0]},
            'last_price': {'$arrayElemAt': ['$prices', -1]},
            'first_timestamp': {'$arrayElemAt': ['$timestamps', 0]},
            'last_timestamp': {'$arrayElemAt': ['$timestamps', -1]},
        }},
        {'$addFields': {
            'price_change_percentage': {
                '$cond': [
                    {'$eq': ['$first_price', 0]},
                    0,
                    {'$multiply': [
                        {'$divide': [
                            {'$subtract': ['$last_price', '$first_price']},
                            '$first_price'
                        ]},
                        100
                    ]}
                ]
            }
        }},
    ]

    stats = list(trades_collection.aggregate(pipeline))
    stats_df = pd.DataFrame(stats)
    if not stats_df.empty:
        stats_df.rename(columns={'_id': 'ticker'}, inplace=True)
    return stats_df

# Function to update the trades table and statistics
def update_data(n):
    print("Update data called")
    # Run the asynchronous function to fetch data
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    all_trades = loop.run_until_complete(fetch_all_tickers_data())
    loop.close()

    # Convert the list of trades to a DataFrame
    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        # Sort trades by timestamp in descending order
        trades_df = trades_df.sort_values(by='timestamp', ascending=False)
        # Remove duplicates in the DataFrame (if any)
        trades_df = trades_df.drop_duplicates(subset=['ticker', 'timestamp'])
    else:
        print("No trade data available.")

    # Compute statistics
    stats_df = compute_statistics()

    return trades_df.to_dict('records') if not trades_df.empty else [], stats_df

# Define the callback to update the trades table and statistics
@app.callback(
    [Output('trades-table', 'data'),
     Output('volume-bar-chart', 'figure'),
     Output('price-change-bar-chart', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    trades_data, stats_df = update_data(n)

    # Prepare figures
    if not stats_df.empty:
        # Volume Bar Chart
        fig_volume = px.bar(
            stats_df,
            x='ticker',
            y='total_volume',
            title='Total Trading Volume (Last 24 Hours)',
            labels={'total_volume': 'Volume', 'ticker': 'Ticker'}
        )

        # Price Change Bar Chart
        fig_price_change = px.bar(
            stats_df,
            x='ticker',
            y='price_change_percentage',
            title='Price Change Percentage (Last 24 Hours)',
            labels={'price_change_percentage': 'Price Change (%)', 'ticker': 'Ticker'}
        )
    else:
        fig_volume = {}
        fig_price_change = {}

    return trades_data, fig_volume, fig_price_change

# Run the Dash app
if __name__ == '__main__':
    print("Starting Dash app...")
    app.run_server(debug=True)
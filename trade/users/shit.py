from trade.settings import API_Key, Secret_Key
from binance.client import Client
import requests

try:
    client = Client(API_Key, Secret_Key, testnet=True)
    print("Binance Client initialized successfully.")
except Exception as e:
    client = None
    print(f"Failed to initialize Binance Client: {e}")


# client = Client(API_Key, Secret_Key, testnet=True)

def get_current_price(symbol):
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    except requests.exceptions.ConnectionError:
        return {
            "error": "Check your internet connection"
        }

def get_recent_prices(symbol, limit):
    try:
        klines = client.get_klines(
            symbol=symbol,
            interval=Client.KLINE_INTERVAL_1MINUTE,
            limit=limit
        )
        return [float(k[4]) for k in klines]

    except requests.exceptions.ConnectionError:
        return {
            "error": "Check your internet connection"
        }

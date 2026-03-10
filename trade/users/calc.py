from .models import Transaction
from .models import Wallet


def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    gains = 0.0
    losses = 0.0

    # only last `period` differences
    for i in range(-period, -1):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff  # make positive

    if losses == 0:
        return 100.0  # strong uptrend

    rs = gains / losses
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def get_price_data(symbol="BTCUSDT", limit=30):
    data = []
    base_price = 42000

    for i in range(limit):
        data.append({
            "time": f"T{i+1}",
            "price": base_price + (i * 15)
        })

    return data



def extract_prices(price_data):

    return [item["price"] for item in price_data]


#rsi vs time
def rsi_vs_time(price_data, period=14):
    prices = extract_prices(price_data)
    rsi_points = []

    for i in range(period + 1, len(prices) + 1):
        window = prices[:i]
        rsi_value = calculate_rsi(window, period)

        if rsi_value is not None:
            rsi_points.append({
                "time": price_data[i - 1]["time"],
                "rsi": rsi_value
            })

    return rsi_points


def profit_vs_loss(user):
    transactions = Transaction.objects.filter(user=user).order_by("created_at")

    pnl = 0.0
    data = []

    for tx in transactions:
        if tx.action == "SELL":
            pnl += (tx.balance_after - tx.balance_before)

        data.append({
            "time": tx.created_at.strftime("%H:%M"),
            "pnl": round(pnl, 2)
        })

    return data



def calculate_roi(user):
    wallet = Wallet.objects.get(user=user)

    invested = 10000.0
    current_value = wallet.balance + (wallet.asset_quantity * 42000)

    roi = ((current_value - invested) / invested) * 100

    return {
        "invested": invested,
        "current_value": round(current_value, 2),
        "roi_percent": round(roi, 2)
    }


def next_price(price_data):
    last_price = price_data[-1]["price"]
    slope = 15  # demo-friendly constant

    return {
        "estimated_price": round(last_price + slope, 2),
        "trend": "UP"
    }


def next_rsi(rsi_data):
    if not rsi_data:
        return {
            "estimated_rsi": 50,
            "trend": "NEUTRAL"
        }

    last_rsi = rsi_data[-1]["rsi"]
    next_value = min(last_rsi + 1.0, 100)

    return {
        "estimated_rsi": round(next_value, 2),
        "trend": "STRENGTHENING"
    }


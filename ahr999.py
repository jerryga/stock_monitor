import logging
import os
import math
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
from sklearn.linear_model import LinearRegression
from dotenv import load_dotenv
import requests

# Load .env file
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

dailyFetched = False

# Send Telegram message
def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        logging.warning(f"Telegram message failed (continuing execution): {e}")


# Send Telegram photo
def send_telegram_photo(photo_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        files = {"photo": photo}
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files=files)

# Get BTC historical closing prices
def fetch_close_series():
    df = yf.download("BTC-USD", period="max", interval="1d", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    close_col = next((c for c in ['Close', 'Adj Close'] if c in df.columns), None)
    if close_col is None:
        raise ValueError(f"Close column not found: {df.columns}")
    df = df.dropna(subset=[close_col])
    return df[close_col]

# Calculate ahr999
def calc_ahr999(close, dca_window=200, fit_window=365):
    prices = close.values

    fit_prices = prices[-fit_window:]
    t = np.arange(len(fit_prices)).reshape(-1, 1)
    log_prices = np.log(fit_prices).reshape(-1, 1)
    model = LinearRegression().fit(t, log_prices)
    log_pred = model.predict([[fit_window - 1]])[0, 0]
    exp_val = math.exp(log_pred)

    dca_cost = np.mean(prices[-dca_window:])
    price_now = prices[-1]
    ahr = (price_now / dca_cost) * (price_now / exp_val)

    return price_now, dca_cost, exp_val, ahr

# Strategy recommendations
def get_strategy(ahr):
    if ahr < 0.45:
        return "Bottom buying zone (increase buying)"
    elif ahr < 1.2:
        return "DCA zone (normal buying)"
    elif ahr < 5:
        return "Wait for takeoff zone (pause buying)"
    else:
        return "Extremely overvalued zone (wait and observe, don't sell)"

# Plot chart
def plot_chart(close, ahr, save_path="ahr999_chart.png"):
    # Use a different style or remove the style altogether
    plt.style.use("default")  # or try "ggplot", "bmh", or remove this line entirely
    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.set_title("BTC Price & ahr999", fontsize=16)
    ax1.plot(close.index, close.values, label="BTC Price (USD)", color="blue")
    ax1.set_ylabel("BTC Price (USD)")
    ax1.set_yscale("log")

    ax2 = ax1.twinx()
    ax2.axhline(0.45, color="green", linestyle="--", alpha=0.6)
    ax2.axhline(1.2, color="orange", linestyle="--", alpha=0.6)
    ax2.axhline(5, color="red", linestyle="--", alpha=0.6)
    ax2.set_ylabel("ahr999")
    ax2.set_yscale("log")
    ax2.plot(close.index, calc_ahr999_series(close), label="ahr999", color="purple", alpha=0.6)

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    plt.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close()

# Calculate ahr999 series for entire history
def calc_ahr999_series(close, dca_window=200, fit_window=365):
    ahr_list = []
    prices = close.values
    for i in range(len(prices)):
        if i < max(dca_window, fit_window):
            ahr_list.append(np.nan)
        else:
            fit_prices = prices[i - fit_window + 1:i + 1]
            t = np.arange(len(fit_prices)).reshape(-1, 1)
            log_prices = np.log(fit_prices).reshape(-1, 1)
            model = LinearRegression().fit(t, log_prices)
            log_pred = model.predict([[fit_window - 1]])[0, 0]
            exp_val = math.exp(log_pred)
            dca_cost = np.mean(prices[i - dca_window + 1:i + 1])
            price_now = prices[i]
            ahr = (price_now / dca_cost) * (price_now / exp_val)
            ahr_list.append(ahr)
    return np.array(ahr_list)

def start_bitcoin():
    global dailyFetched
    if dailyFetched:
        return
    else:
        dailyFetched = True
    try:
        close = fetch_close_series()
        price_now, dca_cost, exp_val, ahr = calc_ahr999(close)

        # Generate text information
        msg = (
            f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
            f"💰 Current Price: {price_now:,.2f} USD\n"
            f"📊 200-day DCA Cost: {dca_cost:,.2f} USD\n"
            f"📈 Exponential Valuation: {exp_val:,.2f} USD\n"
            f"🔢 ahr999: {ahr:.4f}\n"
            f"📌 Strategy Recommendation: {get_strategy(ahr)}"
        )

        # Send text message
        send_telegram_message(msg)
        logging.info(msg)
        # Plot chart and send
        plot_chart(close.tail(730), ahr)  # Last two years
        send_telegram_photo("ahr999_chart.png")

    except Exception as e:
        send_telegram_message(f"⚠️ Script execution error: {e}")


if __name__ == "__main__":
    start_bitcoin()
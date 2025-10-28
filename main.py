import time
import os
import yfinance as yf
import pandas as pd
import ta
import requests
import smtplib
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
import sys

from ahr999 import start_bitcoin
from app import app

LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "stock_monitor.log")
os.makedirs(LOG_DIR, exist_ok=True)

root_logger = logging.getLogger()
if root_logger.hasHandlers():
    root_logger.handlers.clear()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)


# Multiple stocks: allow user input at runtime
def get_user_tickers():
    user_input = input("Enter tickers separated by commas (e.g. NFLX,COIN,TQQQ): ").strip()
    if user_input:
        return [t.strip().upper() for t in user_input.split(",") if t.strip()]
    # fallback to default if nothing entered
    return ["NFLX", "COIN", "TQQQ", "SQQQ", "TSLA", "NVDA", "BTC-USD", "ETH-USD"]

TICKERS = None

CHECK_INTERVAL = 300
COOLDOWN_SECONDS = 15 * 60
TAKE_PROFIT_PCT = 0.05
STOP_LOSS_PCT = -0.03

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Folder structure, ensure existence
os.makedirs("static", exist_ok=True)
os.makedirs("entry_state", exist_ok=True)
os.makedirs("signal_history", exist_ok=True)

def get_close_series(df, ticker):
    if isinstance(df.columns, pd.MultiIndex):
        return df['Close'][ticker]
    else:
        return df['Close']

def generate_chart(df, ticker, filename=None):
    import mplfinance as mpf
    if filename is None:
        filename = f"static/{ticker}_chart.png"
    df = df.copy()
    
    # Limit to last 200 data points for better chart readability
    df = df.tail(200)

    close = get_close_series(df, ticker)

    df['RSI'] = ta.momentum.RSIIndicator(close).rsi()
    macd = ta.trend.MACD(close)
    df['MACD'] = macd.macd()
    df['Signal'] = macd.macd_signal()

    apds = [
        mpf.make_addplot(df['MACD'], panel=1, color='blue'),
        mpf.make_addplot(df['Signal'], panel=1, color='orange'),
        mpf.make_addplot(df['RSI'], panel=2, color='purple')
    ]

    mpf.plot(df, type='candle', mav=(5, 20), volume=True,
             addplot=apds, style='yahoo', panel_ratios=(6, 2, 2),
             title=f'{ticker} 15min Chart with Indicators', savefig=filename)

def send_email(subject, body, image_path=None):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg.attach(MIMEText(body, 'plain'))

        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                img = MIMEImage(f.read())
                img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(image_path))
                msg.attach(img)

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info(f"Email sent successfully: {subject}")
    except Exception as e:
        logging.error(f"Email sending failed: {e}")

def send_telegram(message, image_path=None):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': message})
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                              data={'chat_id': TELEGRAM_CHAT_ID}, files={'photo': photo})
        logging.info("Telegram message sent successfully")
    except Exception as e:
        logging.error(f"Telegram message sending failed: {e}")

def save_entry_price(ticker, price):
    path = f"entry_state/{ticker}.json"
    json.dump({"entry_price": price}, open(path, "w"))

def load_entry_price(ticker):
    path = f"entry_state/{ticker}.json"
    if os.path.exists(path):
        return json.load(open(path)).get("entry_price", None)
    return None

def clear_entry_price(ticker):
    path = f"entry_state/{ticker}.json"
    if os.path.exists(path):
        os.remove(path)

def save_latest_data(ticker, close, rsi, macd, macd_signal, bb_lower, bb_upper, signal):
    # Save latest data to file (optional)
    path = f"signal_history/{ticker}_signals.csv"
    file_exists = os.path.exists(path)
    with open(path, "a") as f:
        if not file_exists:
            f.write("datetime,signal,close\n")
        f.write(f"{datetime.now()},{signal},{close:.2f}\n")

def check_signal_for_ticker(ticker):
    # df = yf.download(ticker, period="10d", interval="15m", auto_adjust=True)

    aapl = yf.Ticker(ticker)
    df = aapl.history(period="10d", interval="15m", auto_adjust=True)

    if df.empty:
        logging.warning(f"{ticker} no data available")
        return "HOLD", None, None

    close = get_close_series(df, ticker)

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_lower = bb.bollinger_lband()
    bb_upper = bb.bollinger_hband()
    macd_obj = ta.trend.MACD(close)
    macd = macd_obj.macd()
    macd_signal = macd_obj.macd_signal()

    last_close = close.iloc[-1]
    last_rsi = rsi.iloc[-1]
    last_bb_lower = bb_lower.iloc[-1]
    last_bb_upper = bb_upper.iloc[-1]
    last_macd = macd.iloc[-1]
    last_macd_signal = macd_signal.iloc[-1]

    buy_score = sum([
        2 if last_close < last_bb_lower else 0,
        2 if last_rsi < 30 else 0,
        2 if last_macd > last_macd_signal else 0
    ])
    sell_score = sum([
        2 if last_close > last_bb_upper else 0,
        2 if last_rsi > 70 else 0,
        2 if last_macd < last_macd_signal else 0
    ])

    logging.info(f"{ticker} : \n 🏦 Price {last_close:.2f} \n 💵 BUY SCORE: {buy_score} \n 🤑 SELL SCORE: {sell_score}")

    action = "HOLD"
    if buy_score >= 5:
        action = "BUY(STRONGLY)"
    elif sell_score >= 5:
        action = "SELL(STRONGLY)"
    elif buy_score >= 4 and sell_score ==0:
        action = "BUY"
    elif buy_score == 0 and sell_score >= 4:
        action = "SELL"

    save_latest_data(ticker, last_close, last_rsi, last_macd, last_macd_signal, last_bb_lower, last_bb_upper, action)

    return action, df, last_close

if __name__ == "__main__":
    TICKERS = get_user_tickers()
    last_buy_time = {ticker: 0 for ticker in TICKERS}
    last_sell_time = {ticker: 0 for ticker in TICKERS}
    start_bitcoin()

    while True:
        try:
            for ticker in TICKERS:
                action, df, last_close = check_signal_for_ticker(ticker)
                if last_close is None:
                    continue

                entry_price = load_entry_price(ticker)

                # Take profit and stop loss detection
                if entry_price:
                    change = (last_close - entry_price) / entry_price
                    if change >= TAKE_PROFIT_PCT:
                        msg = f"🎯 {ticker} Take Profit +{TAKE_PROFIT_PCT*100:.1f}%, Current: {last_close:.2f}"
                        send_telegram(msg, image_path=f"static/{ticker}_chart.png")
                        clear_entry_price(ticker)
                        logging.info(f"{ticker} Take profit, clearing entry price")
                    elif change <= STOP_LOSS_PCT:
                        msg = f"⚠️ {ticker} Stop Loss {STOP_LOSS_PCT*100:.1f}%! Current: {last_close:.2f}"
                        send_telegram(msg, image_path=f"static/{ticker}_chart.png")
                        clear_entry_price(ticker)
                        logging.info(f"{ticker} Stop loss, clearing entry price")

                # Buy/sell signal processing
                now = time.time()
                if "BUY" in action and now - last_buy_time[ticker] > COOLDOWN_SECONDS:
                    generate_chart(df, ticker)
                    send_telegram(f"{ticker} 📥 Buy signal triggered! Price {last_close:.2f} Action: {action}", image_path=f"static/{ticker}_chart.png")
                    last_buy_time[ticker] = now
                    save_entry_price(ticker, last_close)
                elif "SELL" in action and now - last_sell_time[ticker] > COOLDOWN_SECONDS:
                    generate_chart(df, ticker)
                    send_telegram(f"{ticker} 📤 Sell signal triggered! Price {last_close:.2f} Action: {action}", image_path=f"static/{ticker}_chart.png")
                    last_sell_time[ticker] = now
                else:
                    logging.info(f"{ticker} 🥶 No buy or sell signals or in cooling-off period!")
                    logging.info("=" * 50)

        except Exception as e:
            logging.error(f"Exception: {e}")
        time.sleep(CHECK_INTERVAL)
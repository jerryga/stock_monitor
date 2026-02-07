import os
import boto3
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
from datetime import datetime, timezone
import io
from dotenv import load_dotenv

load_dotenv()

def get_tickers_from_env():
    """Get TICKERS from environment variable with fallback"""
    default_tickers = ["NFLX", "COIN", "TQQQ", "GOOGL", "TSLA", "NVDA", "MSFT", "AMZN", "BTC-USD", "ETH-USD"]

    tickers_env = os.getenv('TICKERS')
    if tickers_env:
        # Split by comma and clean whitespace
        tickers = [ticker.strip() for ticker in tickers_env.split(',') if ticker.strip()]
        return tickers if tickers else default_tickers

    return default_tickers

TICKERS = get_tickers_from_env()

S3_BUCKET = os.getenv("S3_BUCKET", "stock-monitor-bucket")
STATE_FILE = "entry_state.json"

COOLDOWN_SECONDS = 15 * 60
TAKE_PROFIT_PCT = 0.05
STOP_LOSS_PCT = -0.03

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

s3 = boto3.client("s3")
logging.basicConfig(level=logging.INFO)


def get_close_series(df, ticker):
    if isinstance(df.columns, pd.MultiIndex):
        return df['Close'][ticker]
    else:
        return df['Close']

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

def send_telegram(message, image_bytes=None):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': message})
        if image_bytes:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                          data={'chat_id': TELEGRAM_CHAT_ID},
                          files={'photo': ('chart.png', image_bytes)})
        logging.info("Telegram message sent successfully")
    except Exception as e:
        logging.error(f"Telegram message sending failed: {e}")

def send_telegram(message, image_bytes=None):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': message})
        if image_bytes:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                          data={'chat_id': TELEGRAM_CHAT_ID},
                          files={'photo': ('chart.png', image_bytes)})
        logging.info("Telegram message sent successfully")
    except Exception as e:
        logging.error(f"Telegram message sending failed: {e}")

def send_email(subject, body, image_bytes=None):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg.attach(MIMEText(body, 'plain'))
        if image_bytes:
            img = MIMEImage(image_bytes, name="chart.png")
            msg.attach(img)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        logging.error(f"Email failed: {e}")

def load_state():
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=STATE_FILE)
        return json.loads(obj['Body'].read())
    except s3.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        logging.error(f"Failed to load state: {e}")
        return {}

def save_state(state):
    try:
        s3.put_object(Bucket=S3_BUCKET, Key=STATE_FILE, Body=json.dumps(state))
    except Exception as e:
        logging.error(f"Failed to save state: {e}")

def generate_chart(df, ticker):
    import mplfinance as mpf
    df = df.tail(200)
    buf = io.BytesIO()
    mpf.plot(df, type='candle', style='yahoo', mav=(5, 20), volume=True,
             title=f"{ticker} 15m Chart", savefig=dict(fname=buf, format='png'))
    buf.seek(0)
    return buf.read()

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
    return action, df, last_close

def lambda_handler(event, context):
    logging.info("=== Lambda Stock Monitor Run ===")
    send_telegram("=== Lambda Stock Monitor Run ===")

    state = load_state()
    now = datetime.now(timezone.utc).timestamp()
    # start_bitcoin()
    for ticker in TICKERS:
        try:
            action, df, last_close = check_signal_for_ticker(ticker)
            if df is None or df.empty: continue

            entry_price = state.get(ticker, {}).get("entry_price")
            last_buy = state.get(ticker, {}).get("last_buy", 0)
            last_sell = state.get(ticker, {}).get("last_sell", 0)

            # Profit / loss exit
            if entry_price:
                change = (last_close - entry_price) / entry_price
                if change >= TAKE_PROFIT_PCT:
                    send_telegram(f"🎯 {ticker} Take profit +{TAKE_PROFIT_PCT*100:.1f}%")
                    state[ticker] = {}
                elif change <= STOP_LOSS_PCT:
                    send_telegram(f"⚠️ {ticker} Stop loss {STOP_LOSS_PCT*100:.1f}%")
                    state[ticker] = {}

            if "BUY" in action and now - last_buy > COOLDOWN_SECONDS:
                chart = generate_chart(df, ticker)
                send_telegram(f"{ticker} 📥 BUY @ {last_close:.2f} ({action})", image_bytes=chart)
                state[ticker] = {"entry_price": last_close, "last_buy": now}
            elif "SELL" in action and now - last_sell > COOLDOWN_SECONDS:
                chart = generate_chart(df, ticker)
                send_telegram(f"{ticker} 📤 SELL @ {last_close:.2f} ({action})", image_bytes=chart)
                state[ticker] = {"last_sell": now}
            else:
                logging.info(f"{ticker}: HOLD ({action})")
        except Exception as e:
            logging.error(f"Error processing {ticker}: {e}")
    save_state(state)
    return {"status": "ok"}

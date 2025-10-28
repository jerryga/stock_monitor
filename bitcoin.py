import time
import os
import yfinance as yf
import pandas as pd
import ta
import requests
import logging
import json
from datetime import datetime

LOG_PATH = "fusion_monitor.log"
logging.basicConfig(level=logging.INFO, filename=LOG_PATH, format='%(asctime)s %(message)s')


# Allow user to input tickers at runtime
def get_user_tickers():
    user_input = input("Enter tickers separated by commas (e.g. NFLX,COIN,TQQQ): ").strip()
    if user_input:
        return [t.strip().upper() for t in user_input.split(",") if t.strip()]
    # fallback to default if nothing entered
    return ["NFLX", "COIN", "TQQQ", "TSLA", "BTC-USD", "ETH-USD"]

TICKERS = None
CHECK_INTERVAL = 300
COOLDOWN_SECONDS = 15 * 60
TAKE_PROFIT_PCT = 0.05
STOP_LOSS_PCT = -0.03

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

FIXED_INVEST_AMOUNT = 100
INCREASED_INVEST_AMOUNT = 150
DCA_COOLDOWN_SECONDS = 30 * 60

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

def generate_chart(df, ticker, filename=None):
    import mplfinance as mpf
    if filename is None:
        filename = f"static/{ticker}_chart.png"
    df = df.copy()
    close = df['Close']
    df['RSI'] = ta.momentum.RSIIndicator(close).rsi()
    macd = ta.trend.MACD(close)
    df['MACD'] = macd.macd()
    df['Signal'] = macd.macd_signal()
    apds = [
        mpf.make_addplot(df['MACD'], panel=1, color='blue'),
        mpf.make_addplot(df['Signal'], panel=1, color='orange'),
        mpf.make_addplot(df['RSI'], panel=2, color='purple')
    ]
    mpf.plot(df, type='candle', mav=(5,20), volume=True,
             addplot=apds, style='yahoo', panel_ratios=(6,2,2),
             title=f'{ticker} Chart with Indicators', savefig=filename)

def get_entry_price(ticker):
    path = f"entry_state/{ticker}.json"
    if os.path.exists(path):
        return json.load(open(path)).get("entry_price", None)
    return None

def save_entry_price(ticker, price):
    path = f"entry_state/{ticker}.json"
    json.dump({"entry_price": price}, open(path, "w"))

def clear_entry_price(ticker):
    path = f"entry_state/{ticker}.json"
    if os.path.exists(path):
        os.remove(path)

def check_short_term_signal(ticker):
    df = yf.download(ticker, period="10d", interval="15m", auto_adjust=True)
    if df.empty:
        logging.warning(f"{ticker} no data")
        return "HOLD", None, None

    close = df['Close']
    rsi = ta.momentum.RSIIndicator(close).rsi()
    bb = ta.volatility.BollingerBands(close)
    macd_obj = ta.trend.MACD(close)

    last_close = close.iloc[-1]
    last_rsi = rsi.iloc[-1]
    last_bb_lower = bb.bollinger_lband().iloc[-1]
    last_bb_upper = bb.bollinger_hband().iloc[-1]
    last_macd = macd_obj.macd().iloc[-1]
    last_macd_signal = macd_obj.macd_signal().iloc[-1]

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

    action = "HOLD"
    if buy_score >= 5:
        action = "BUY(STRONG)"
    elif sell_score >= 5:
        action = "SELL(STRONG)"
    elif buy_score >= 4 and sell_score == 0:
        action = "BUY"
    elif sell_score >= 4 and buy_score == 0:
        action = "SELL"

    return action, df, last_close

def check_dca_signal():
    ticker = "BTC-USD"
    df = yf.download(ticker, period="30d", interval="1d", auto_adjust=True)
    if df.empty:
        logging.warning("BTC-USD no data for DCA")
        return None, 0, None

    close = df['Close']
    rsi = ta.momentum.RSIIndicator(close).rsi()
    bb = ta.volatility.BollingerBands(close)
    macd_obj = ta.trend.MACD(close)

    last_close = close.iloc[-1]
    last_rsi = rsi.iloc[-1]
    last_bb_lower = bb.bollinger_lband().iloc[-1]
    last_bb_upper = bb.bollinger_hband().iloc[-1]
    last_macd = macd_obj.macd().iloc[-1]
    last_macd_signal = macd_obj.macd_signal().iloc[-1]

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

    if buy_score >= 5:
        invest_amount = INCREASED_INVEST_AMOUNT
        action = "STRONG BUY"
    elif sell_score >= 5:
        invest_amount = 0
        action = "STRONG SELL"
    else:
        invest_amount = FIXED_INVEST_AMOUNT
        action = "HOLD"

    return action, invest_amount, last_close

def main():
    global TICKERS
    TICKERS = get_user_tickers()
    last_buy_time = {ticker: 0 for ticker in TICKERS}
    last_sell_time = {ticker: 0 for ticker in TICKERS}
    last_dca_signal_time = 0
    last_dca_action = None

    while True:
        now = time.time()

        for ticker in TICKERS:
            try:
                action, df, price = check_short_term_signal(ticker)
                if price is None:
                    continue

                entry_price = get_entry_price(ticker)

                if entry_price:
                    change = (price - entry_price) / entry_price
                    if change >= TAKE_PROFIT_PCT:
                        send_telegram(f"🎯 {ticker} Take Profit +{TAKE_PROFIT_PCT*100:.1f}%，Current：{price:.2f}")
                        clear_entry_price(ticker)
                        logging.info(f"{ticker} Take profit, clearing entry price")
                    elif change <= STOP_LOSS_PCT:
                        send_telegram(f"⚠️ {ticker} Stop Loss -{STOP_LOSS_PCT*100:.1f}%，Current：{price:.2f}")
                        clear_entry_price(ticker)
                        logging.info(f"{ticker} Stop loss, clearing entry price")

                if "BUY" in action and now - last_buy_time[ticker] > COOLDOWN_SECONDS:
                    generate_chart(df, ticker, filename=f"static/{ticker}_chart.png")
                    send_telegram(f"{ticker} 📥 Buy signal triggered! Price {price:.2f}，Action: {action}", image_path=f"static/{ticker}_chart.png")
                    last_buy_time[ticker] = now
                    save_entry_price(ticker, price)

                elif "SELL" in action and now - last_sell_time[ticker] > COOLDOWN_SECONDS:
                    generate_chart(df, ticker, filename=f"static/{ticker}_chart.png")
                    send_telegram(f"{ticker} 📤 Sell signal triggered! Price {price:.2f}，Action: {action}", image_path=f"static/{ticker}_chart.png")
                    last_sell_time[ticker] = now

            except Exception as e:
                logging.error(f"{ticker} Abnormal short-term signals: {e}")

        try:
            action, invest_amount, price = check_dca_signal()
            if action is not None:
                if action != last_dca_action or now - last_dca_signal_time > DCA_COOLDOWN_SECONDS:
                    if invest_amount > 0:
                        df_dca = yf.download("BTC-USD", period="30d", interval="1d", auto_adjust=True)
                        generate_chart(df_dca, "BTC-USD", filename="static/BTC-USD_dca_chart.png")
                        msg = (f"Bitcoin Fixed Investment Reminder\n"
                               f"Current Price: ${price:.2f}\n"
                               f"Buy Recommendation: {action}\n"
                               f"Planned Purchase Amount: ${invest_amount:.2f}")
                        send_telegram(msg, image_path="static/BTC-USD_dca_chart.png")
                        last_dca_signal_time = now
                        last_dca_action = action
                    else:
                        logging.info("Fixed investment signal is strong sell, buy reminder is suspended")
                        last_dca_signal_time = now
                        last_dca_action = action
        except Exception as e:
            logging.error(f"DCA signal exception: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    os.makedirs("entry_state", exist_ok=True)
    logging.info("Fusion monitoring program started")
    main()

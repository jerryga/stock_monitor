# app.py
from flask import Flask, render_template
import pandas as pd
import os
import json

app = Flask(__name__)
SIGNAL_HISTORY_CSV = "signals.csv"

@app.route("/")
def index():
    try:
        with open("latest_data.json") as f:
            data = json.load(f)
    except:
        data = {}

    if os.path.exists(SIGNAL_HISTORY_CSV):
        df = pd.read_csv(SIGNAL_HISTORY_CSV, names=["time", "signal", "price"])
        history = df.tail(20).to_dict(orient="records")
    else:
        history = []

    return render_template("index.html",
                           current_price=data.get("close", "N/A"),
                           rsi=data.get("rsi", "N/A"),
                           macd=data.get("macd", "N/A"),
                           macd_signal=data.get("macd_signal", "N/A"),
                           bb_lower=data.get("bb_lower", "N/A"),
                           bb_upper=data.get("bb_upper", "N/A"),
                           signal=data.get("signal", "N/A"),
                           history=history)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

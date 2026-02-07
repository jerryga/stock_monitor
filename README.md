# Stock Monitor

A Python-based monitoring and alerting system for stocks and cryptocurrencies that integrates technical analysis with automated notifications via Telegram and Email. The system is designed to run as a cloud-native application, specifically optimized for AWS Lambda with S3-backed state persistence.

## Features

* **Multi-Ticker Tracking**: Monitors a customizable list of tickers including major stocks (e.g., AAPL, TSLA, NVDA) and cryptocurrencies (BTC-USD, ETH-USD) via Yahoo Finance.
* **Technical Indicator Analysis**: Automatically calculates key trading indicators to generate signals:
* **Relative Strength Index (RSI)**
* **Bollinger Bands (BB)**
* **Moving Average Convergence Divergence (MACD)**


* **Scoring-Based Signal Logic**: Uses a weighted scoring system to trigger "BUY," "SELL," "STRONGLY BUY," or "STRONGLY SELL" actions.
* **Automated Alerts**:
* **Telegram**: Sends real-time alerts with status updates and generated technical charts.
* **Email**: Delivers notifications via SMTP (Gmail) including chart attachments.


* **Dynamic Risk Management**:
* **Take Profit**: Automatically triggers at +5%.
* **Stop Loss**: Automatically triggers at -3%.
* **Cooldown**: 15-minute window between consecutive signals to prevent alert fatigue.


* **Cloud-Native Architecture**: Built for AWS Lambda with state persistence in Amazon S3 for tracking entry prices and signal history.
* **Visualization**: Generates 15-minute candlestick charts with 5-period and 20-period moving averages using `mplfinance`.

## Project Structure

* `app.py`: The core application logic, containing the AWS Lambda handler, technical analysis functions, and notification dispatchers.
* `Dockerfile`: Configuration for building the Amazon ECR-compatible container image using the Python 3.10 Lambda base.
* `requirements.txt`: Lists essential dependencies including `yfinance`, `pandas`, `ta` (Technical Analysis Library), and `boto3`.
* `entry_state.json`: (Stored in S3) Maintains the current investment state, including entry prices and timestamps for cooldowns.

## Technical Stack

* **Language**: Python 3.10+
* **Data Source**: Yahoo Finance (`yfinance`)
* **Analysis**: `pandas`, `ta`
* **Cloud**: AWS Lambda, Amazon S3, Amazon ECR
* **Visualization**: `matplotlib`, `mplfinance`

## Setup and Deployment

### 1. Environment Variables

The following environment variables must be configured for the application to function:

* `S3_BUCKET`: The name of your AWS S3 bucket for state storage.
* `TICKERS`: Comma-separated list of symbols (e.g., `NVDA,BTC-USD`).
* `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For Telegram notifications.
* `EMAIL_SENDER`, `EMAIL_PASSWORD`, & `EMAIL_RECEIVER`: For SMTP email alerts.

### 2. Local Installation

```bash
pip install -r requirements.txt

```

### 3. Docker Build for AWS ECR

#### Build Image
```bash
docker build --platform linux/amd64 --provenance=false -t stock-monitor .

```
#### Authenticate Docker
```bash
aws ecr create-repository --repository-name stock-monitor --region us-east-1

```

#### Tag Image
```bash
docker tag stock-monitor:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/stock-monitor:latest

```

### Push the image
```bash
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/stock-monitor:latest

```


## Signal Criteria

The system uses a score-based threshold to determine actions:

* **BUY Signal**: Triggered when the score is ≥ 4, influenced by the price being below the lower Bollinger Band, RSI < 30, or a positive MACD crossover.
* **SELL Signal**: Triggered when the score is ≥ 4, influenced by the price being above the upper Bollinger Band, RSI > 70, or a negative MACD crossover.
# Send Telegram message
def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        requests.post(url, data=payload, timeout=10)
        logging.info("Telegram message sent successfully")
    except Exception as e:
        logging.warning(f"Telegram message failed (continuing execution): {e}")

# Send Telegram photo
def send_telegram_photo(photo_path):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            files = {"photo": photo}
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files=files, timeout=10)
        logging.info("Telegram photo sent successfully")
    except Exception as e:
        logging.warning(f"Telegram photo failed (continuing execution): {e}")

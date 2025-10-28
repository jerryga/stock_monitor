def send_telegram(message, image_path=None):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      data={'chat_id': TELEGRAM_CHAT_ID, 'text': message},
                      timeout=10)  # Add timeout to prevent long blocking
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                              data={'chat_id': TELEGRAM_CHAT_ID}, files={'photo': photo},
                              timeout=10)  # Add timeout to prevent long blocking
        logging.info("Telegram message sent successfully")
    except Exception as e:
        logging.warning(f"Telegram message sending failed (continuing): {e}")

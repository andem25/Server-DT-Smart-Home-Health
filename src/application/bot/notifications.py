
from flask import current_app

async def send_alert_to_user(telegram_id: int, plant_name: str, humidity: float):
    try:
        bot = current_app.config["TELEGRAM_BOT"]
        message = (
            f"⚠ Allarme Umidità Bassa!\n\n"
            f"La tua pianta {plant_name} ha raggiunto solo {humidity:.1f}% di umidità.\n"
            f"Controlla se ha bisogno di essere innaffiata 💧"
        )
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")  # ✅ await obbligatorio
        print(f"✅ Notifica Telegram inviata a {telegram_id} per {plant_name}")
    except Exception as e:
        print(f"❌ Errore durante invio notifica Telegram: {e}")
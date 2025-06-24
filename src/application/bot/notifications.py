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
        print(f"❌ Errore durante invio notifica Telegram: {e}")

async def send_emergency_alert(telegram_id: int, device_id: str, dt_name: str):
    """
    Invia una notifica di emergenza al supervisore
    
    Args:
        telegram_id: ID Telegram dell'utente supervisore
        device_id: ID del dispositivo che ha richiesto aiuto
        dt_name: Nome del Digital Twin a cui appartiene il dispositivo
    """
    try:
        bot = current_app.config["TELEGRAM_BOT"]
        message = (
            f"🚨 *ALLARME EMERGENZA*!\n\n"
            f"⚠️ *RICHIESTA DI AIUTO* dal dispositivo `{device_id}`\n"
            f"📍 Appartiene alla casa: *{dt_name}*\n\n"
            f"*Intervento richiesto immediatamente.*"
        )
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")
        print(f"✅ Notifica di emergenza inviata a {telegram_id} per dispositivo {device_id}")
    except Exception as e:
        print(f"❌ Errore durante invio notifica di emergenza: {e}")
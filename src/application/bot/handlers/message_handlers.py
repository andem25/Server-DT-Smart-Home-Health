from telegram import Update
from telegram.ext import ContextTypes
from flask import current_app
from src.application.mqtt import send_mqtt_message
from src.services.database_service import DatabaseService

async def send_message_to_dispenser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Invia un messaggio a un dispenser specifico tramite MQTT.
    Uso: /send_message <id_dispenser> <messaggio>
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❗ **Uso Corretto:**\n`/send_message <id_dispenser> <messaggio>`\n\n"
            "**Esempio:**\n"
            "`/send_message disp1 È ora di prendere la medicina!`\n\n"
            "📝 Puoi trovare l'ID del dispenser usando `/my_medicines`",
            parse_mode="Markdown"
        )
        return

    dispenser_id = args[0]
    message = " ".join(args[1:])

    try:
        # Verifica che l'utente sia autorizzato ad inviare messaggi a questo dispenser
        db: DatabaseService = context.application.bot_data.get('db_service')
        if not db:
            await update.message.reply_text("❌ Errore interno: Servizio database non disponibile.")
            print("Errore critico: 'db_service' non trovato in application.bot_data")
            return

        dispenser = db.get_dr("dispenser_medicine", dispenser_id)
        if not dispenser:
            await update.message.reply_text(f"❌ Dispenser con ID `{dispenser_id}` non trovato.", parse_mode="Markdown")
            return

        if dispenser.get("user_db_id") != user_db_id:
            await update.message.reply_text("❌ Non sei autorizzato a inviare messaggi a questo dispenser.")
            return

        # Invia il messaggio tramite MQTT
        topic = f"{dispenser_id}/message"
        send_mqtt_message(message, topic)
        
        dispenser_name = dispenser.get('data', {}).get('name', dispenser_id)
        await update.message.reply_text(
            f"✅ Messaggio inviato con successo al dispenser '{dispenser_name}' (`{dispenser_id}`):\n\n"
            f"_{message}_", 
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante l'invio del messaggio: {str(e)}")
        print(f"Errore in send_message_to_dispenser_handler: {e}")
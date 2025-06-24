from telegram import Update
from telegram.ext import ContextTypes
from flask import current_app
from datetime import datetime
from telegram.constants import ParseMode

async def create_dt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea un nuovo Digital Twin per l'utente utilizzando il DTManager."""
    user_db_id = context.user_data.get("user_db_id")
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    # Estrai il nome del DT dal comando
    try:
        dt_name = context.args[0]
    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /create_dt <nome_del_dt>")
        return

    # Ottieni il DTManager dalla configurazione dell'app
    dt_manager = current_app.config["DT_MANAGER"]
    
    await update.message.reply_text(f"⏳ Creazione del Digital Twin '{dt_name}' in corso...")

    try:
        # --- INIZIO MODIFICA CRUCIALE ---
        # Chiama il metodo corretto e completo del DTManager
        description = f"Smart Home Health DT di {update.effective_user.first_name}"
        dt_id = dt_manager.create_smart_home_health_dt(
            user_id=user_db_id, 
            name=dt_name, 
            description=description
        )
        # --- FINE MODIFICA CRUCIALE ---
        
        # Ora il DT è stato creato con TUTTI i servizi configurati in dt_manager.py
        dt_doc = dt_manager.dt_factory.get_dt(dt_id) # Usiamo il factory per ottenere il documento
        
        await update.message.reply_text(
            f"✅ Digital Twin '{dt_name}' creato con successo!\n\n"
            f"🆔 *ID*: `{dt_id}`\n"
            f"📝 *Descrizione*: {dt_doc['description']}\n\n"
            "Tutti i servizi sono stati configurati correttamente.\n"
            "Usa `/list_dt` per visualizzare i tuoi Digital Twin.",
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        print(f"Errore catastrofico nella creazione del DT: {e}")
        await update.message.reply_text(f"❌ Errore nella creazione del DT: {e}")



async def list_dt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all Digital Twins associated with the logged-in user."""
    # 1. Verify that the user is logged in
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ You must be logged in. Use /login <username> <password>.")
        return

    try:
        # 2. Get the database service
        db_service = context.application.bot_data['db_service']
        
        # 3. Query the 'digital_twins' collection
        # The user_id is stored in the metadata of the DT document
        dt_collection = db_service.db["digital_twins"]
        query = {"metadata.user_id": user_db_id}
        user_dts = list(dt_collection.find(query))

        # 4. Handle the case where no DTs are found
        if not user_dts:
            await update.message.reply_text("ℹ️ You have no Digital Twins registered. Create one with /create_dt <name>.")
            return

        # 5. Format and send the response
        response = "🤖 *Your Digital Twins:*\n\n"
        for dt in user_dts:
            dt_id = dt.get('_id', 'N/A')
            dt_name = dt.get('name', 'Unnamed DT')
            dt_desc = dt.get('description', 'No description')
            num_devices = len(dt.get('digital_replicas', []))
            num_services = len(dt.get('services', []))

            response += f"🔹 *{dt_name.capitalize()}*\n"
            response += f"   - *ID:* `{dt_id}`\n"
            response += f"   - *Description:* {dt_desc}\n"
            response += f"   - *Connected Devices:* {num_devices}\n"
            response += f"   - *Active Services:* {num_services}\n\n"

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ An error occurred while fetching your Digital Twins: {e}")
        print(f"Error in list_my_dts_handler: {e}")
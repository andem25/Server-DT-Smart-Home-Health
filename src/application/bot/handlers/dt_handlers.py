from telegram import Update
from telegram.ext import ContextTypes
from flask import current_app
from datetime import datetime

async def create_dt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea un nuovo Digital Twin completo con tutti i servizi Smart Home Health"""
    # Verifica che l'utente sia loggato
    user_db_id = context.user_data.get('user_db_id')
    username = context.user_data.get('username')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    # Verifica i parametri
    if len(context.args) < 1:
        await update.message.reply_text("❗ Uso: /create_dt <nome_digital_twin> [descrizione]")
        return

    dt_name = context.args[0]
    dt_description = " ".join(context.args[1:]) if len(context.args) > 1 else f"Smart Home Health DT di {username}"
    
    try:
        # Ottieni il DT Manager e il db_service
        dt_manager = context.application.bot_data.get('dt_manager')
        db_service = context.application.bot_data.get('db_service')
        
        if not dt_manager or not db_service:
            await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
            return
        
        # Verifica se esiste già un DT con questo nome (controllo più robusto)
        existing_dt = db_service.query_drs("digital_twins", {"name": dt_name})
        
        if existing_dt and len(existing_dt) > 0:
            # Genera un nome univoco aggiungendo un timestamp
            import time
            timestamp = int(time.time()) % 10000  # Prendi solo le ultime 4 cifre
            suggested_names = [
                f"{dt_name}_{timestamp}", 
                f"{dt_name}_{username[:5]}", 
                f"{dt_name}_home"
            ]
            suggestions = ", ".join([f"`{name}`" for name in suggested_names])
            
            await update.message.reply_text(
                f"⚠️ *Impossibile creare il Digital Twin*\n\n"
                f"Il nome '{dt_name}' è già in uso da un altro Digital Twin.\n\n"
                f"*Cosa puoi fare:*\n"
                f"1. Usare un nome diverso con `/create_dt NuovoNome`\n"
                f"2. Provare uno dei seguenti nomi suggeriti:\n{suggestions}\n\n"
                f"3. Usare il comando `/create_unique_dt {dt_name}` che genererà automaticamente un nome univoco.", 
                parse_mode="Markdown"
            )
            return
        
        # Procedi con la creazione del DT
        dt_id = dt_manager.create_smart_home_health_dt(user_id=user_db_id, name=dt_name, description=dt_description)
        
        await update.message.reply_text(
            f"✅ Digital Twin '{dt_name}' creato con successo!\n"
            f"ID: `{dt_id}`\n"
            f"Descrizione: {dt_description}\n\n"
            f"Servizi configurati correttamente.\n"
            f"Usa `/list_dt` per visualizzare i tuoi Digital Twin.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        error_message = str(e).lower()
        if "duplicate key" in error_message and "name" in error_message:
            # Cattura specificamente gli errori di nome duplicato che sono sfuggiti al controllo iniziale
            import time
            timestamp = int(time.time()) % 10000
            await update.message.reply_text(
                f"⚠️ *Il nome '{dt_name}' è già utilizzato*\n\n"
                f"Prova con un nome più specifico come:\n"
                f"- `{dt_name}_{timestamp}`\n"
                f"- `{dt_name}_{username}`\n"
                f"- `{dt_name}_home`\n\n"
                f"Oppure usa il comando automatico:\n"
                f"`/create_unique_dt {dt_name}`",
                parse_mode="Markdown"
            )
        else:
            # Altri tipi di errori
            await update.message.reply_text(f"❌ Si è verificato un errore durante la creazione del Digital Twin. Per favore riprova.")
            print(f"Errore in create_dt_handler: {e}")


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
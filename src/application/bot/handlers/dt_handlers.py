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

async def show_dt_telegram_ids_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra gli ID Telegram associati ai Digital Twin dell'utente"""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    try:
        # Ottieni i servizi necessari
        db_service = context.application.bot_data.get('db_service')
        if not db_service:
            await update.message.reply_text("❌ Errore interno: Database non disponibile.")
            return
        
        # Debug: stampa l'ID utente per verificare che sia corretto
        print(f"DEBUG DT_IDS: Cerco Digital Twin per user_id={user_db_id}")
        
        # Usa direttamente il client MongoDB per accedere ai dati grezzi
        dt_collection = db_service.db["digital_twins"]
        query = {"metadata.user_id": user_db_id}
        print(f"DEBUG DT_IDS: Query al database: {query}")
        
        user_dt_docs = list(dt_collection.find(query))
        print(f"DEBUG DT_IDS: Trovati {len(user_dt_docs)} Digital Twin")
        
        if not user_dt_docs:
            await update.message.reply_text("ℹ️ Non hai Digital Twin registrati. Creane uno con `/create_dt <nome>`.")
            return
        
        # Prepara il messaggio
        msg = "🔔 *ID Telegram associati ai tuoi Digital Twin:*\n\n"
        
        for dt_doc in user_dt_docs:
            dt_id = str(dt_doc["_id"])
            dt_name = dt_doc.get("name", "DT senza nome")
            
            metadata = dt_doc.get("metadata", {})
            # Estrai gli ID Telegram attivi (possono essere int o str)
            active_ids = metadata.get("active_telegram_ids", [])
            
            # Debug per verificare cosa contiene metadata
            print(f"DEBUG DT_IDS: DT {dt_id} metadata: {metadata}")
            print(f"DEBUG DT_IDS: DT {dt_id} active_ids (raw): {active_ids}")
            
            # Converti tutti gli ID a string per la visualizzazione
            active_ids_str = [str(id_val) for id_val in active_ids]
            print(f"DEBUG DT_IDS: DT {dt_id} active_ids (str): {active_ids_str}")
            
            msg += f"*{dt_name}* (ID: `{dt_id}`)\n"
            if active_ids:
                msg += f"  ID attivi: {', '.join(active_ids_str)}\n"
            else:
                msg += "  Nessun ID Telegram attivo\n"
            msg += "\n"
        
        # Aggiungi il tuo ID Telegram corrente
        your_id = update.effective_user.id
        msg += f"📱 *Il tuo ID Telegram attuale è:* `{your_id}`\n"
        msg += "\nSe il tuo ID non è presente nella lista, prova a disconnetterti e riconnetterti con `/logout` e `/login`."
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    except Exception as e:
        print(f"Errore in show_dt_telegram_ids_handler: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Errore durante il recupero degli ID: {e}")

async def delete_dt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina un Digital Twin dell'utente e tutti i servizi associati."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    # Verifica che l'ID del DT sia stato fornito
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❗ Uso: `/delete_smart_home <dt_id>`\n\n"
            "Esempio: `/delete_smart_home 64abcd12ef34`\n\n"
            "Usa `/list_smart_homes` per vedere i tuoi Digital Twin disponibili.",
            parse_mode="Markdown"
        )
        return

    dt_id = context.args[0]
    
    try:
        # Ottieni i servizi necessari
        dt_factory = context.application.bot_data.get('dt_factory')
        if not dt_factory:
            await update.message.reply_text("❌ Errore interno: DT Factory non disponibile.")
            return
        
        # Verifica che il DT esista e appartenga all'utente
        dt = dt_factory.get_dt(dt_id)
        if not dt:
            await update.message.reply_text("❌ Digital Twin non trovato. Controlla l'ID e riprova.")
            return
            
        if dt.get('metadata', {}).get('user_id') != user_db_id:
            await update.message.reply_text("❌ Non hai i permessi per eliminare questo Digital Twin.")
            return
        
        dt_name = dt.get('name', 'Digital Twin')
        
        # Ottieni l'istanza del DT per terminare i servizi attivi
        dt_instance = dt_factory.get_dt_instance(dt_id)
        if dt_instance:
            # Termina tutti i servizi attivi
            services = dt_instance.list_services()
            for service_name in services:
                try:
                    dt_instance.remove_service(service_name)
                except Exception as e:
                    print(f"Errore nella terminazione del servizio {service_name}: {e}")

        # Elimina il DT dal database
        dt_factory.delete_dt(dt_id)
        
        await update.message.reply_text(
            f"✅ Digital Twin '{dt_name}' (`{dt_id}`) eliminato con successo.\n\n"
            "Tutti i servizi associati sono stati terminati e i dati rimossi dal database.",
            parse_mode="Markdown"
        )
    
    except Exception as e:
        print(f"Errore in delete_dt_handler: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Errore durante l'eliminazione del Digital Twin: {str(e)}")
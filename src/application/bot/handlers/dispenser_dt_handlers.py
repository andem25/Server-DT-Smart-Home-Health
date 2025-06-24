from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from datetime import datetime
from flask import current_app


async def add_dispenser_to_dt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collega un dispenser di medicinali esistente a un Digital Twin."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "❗ **Uso Corretto:**\n`/add_dispenser_dt <dt_id> <dispenser_id>`\n\n"
            "**Esempio:**\n"
            "`/add_dispenser_dt 68584c95-ce9c-... 001-paracetamolo`\n\n"
            "📝 **Come trovare gli ID:**\n"
            "- Usa `/list_dt` per l'ID del Digital Twin (`dt_id`).\n"
            "- Usa `/my_medicines` per l'ID del dispenser (`dispenser_id`).",
            parse_mode="Markdown"
        )
        return

    dt_id, dispenser_id = context.args[0], context.args[1]
    
    try:
        dt_manager = context.application.bot_data.get('dt_manager')
        dt_factory = context.application.bot_data.get('dt_factory')
        db_service = context.application.bot_data.get('db_service')

        if not all([dt_manager, dt_factory, db_service]):
            await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
            return
        
        dt = dt_factory.get_dt(dt_id)
        if not dt or dt.get('metadata', {}).get('user_id') != user_db_id:
            await update.message.reply_text("❌ Digital Twin non trovato o non ti appartiene.")
            return

        dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
        if not dispenser or dispenser.get('user_db_id') != user_db_id:
            await update.message.reply_text("❌ Dispenser non trovato o non ti appartiene.")
            return

        dt_manager.register_device(dt_id, "dispenser_medicine", dispenser_id)
        
        dispenser_name = dispenser.get('data', {}).get('name', 'Sconosciuto')
        dt_name = dt.get('name', 'Sconosciuto')

        await update.message.reply_text(
            f"✅ Dispenser '{dispenser_name}' (`{dispenser_id}`) collegato con successo al Digital Twin '{dt_name}' (`{dt_id}`)."
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante il collegamento del dispenser: {str(e)}")

async def list_dt_devices_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elenca tutti i dispositivi collegati a un Digital Twin"""
    # Verifica che l'utente sia loggato
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return
    
    # Verifica i parametri
    if len(context.args) < 1:
        await update.message.reply_text(
            "❗ Uso: /dt_devices <dt_id>\n\n"
            "Esempio: `/dt_devices 64abcd12ef34`\n\n"
            "Usa `/list_dt` per vedere i tuoi Digital Twin disponibili.",
            parse_mode="Markdown"
        )
        return
        
    dt_id = context.args[0]
    
    try:
        # Ottieni il Digital Twin
        dt_factory = context.application.bot_data.get('dt_factory')
        if not dt_factory:
            await update.message.reply_text("❌ Errore interno: Servizio DT Factory non disponibile.")
            return
            
        # Ottieni il DT
        dt = dt_factory.get_dt(dt_id)
        if not dt:
            await update.message.reply_text("❌ Digital Twin non trovato. Controlla l'ID e riprova.")
            return
            
        if dt.get('metadata', {}).get('user_id') != user_db_id:
            await update.message.reply_text("❌ Non hai i permessi per visualizzare questo Digital Twin.")
            return
        
        # Ottieni i dispositivi collegati
        connected_devices = dt.get('connected_devices', [])
        
        if not connected_devices:
            await update.message.reply_text(
                f"📱 Il Digital Twin '{dt.get('name')}' non ha dispositivi collegati.\n\n"
                f"Usa `/add_dispenser_dt {dt_id} <nome_medicinale>` per collegare un dispenser.",
                parse_mode="Markdown"
            )
            return
            
        # Componi il messaggio con i dispositivi
        msg = f"📱 Dispositivi collegati al Digital Twin '{dt.get('name')}':\n\n"
        
        for idx, device in enumerate(connected_devices, 1):
            device_id = device.get('id', 'ID sconosciuto')
            device_type = device.get('type', 'Tipo sconosciuto')
            device_name = device.get('name', 'Nome sconosciuto')
            connected_at = device.get('connected_at', 'Data sconosciuta')
            
            # Ottieni dettagli aggiuntivi per i dispenser
            if device_type == 'dispenser_medicine':
                try:
                    dispenser = dt_factory.db_service.get_dr('dispenser_medicine', device_id)
                    if dispenser:
                        medicine_data = dispenser.get('data', {})
                        medicine_name = medicine_data.get('medicine_name', 'Nome sconosciuto')
                        dosage = medicine_data.get('dosage', 'Non specificato')
                        interval = medicine_data.get('interval', 'Non specificato')
                        
                        msg += f"*{idx}. {device_name}*\n"
                        msg += f"  - ID: `{device_id}`\n"
                        msg += f"  - Tipo: {device_type}\n"
                        msg += f"  - Medicinale: {medicine_name}\n"
                        msg += f"  - Dosaggio: {dosage}\n"
                        msg += f"  - Intervallo: {interval}\n"
                        msg += f"  - Collegato il: {connected_at}\n\n"
                    else:
                        msg += f"*{idx}. {device_name}*\n"
                        msg += f"  - ID: `{device_id}`\n"
                        msg += f"  - Tipo: {device_type}\n"
                        msg += f"  - ATTENZIONE: Dettagli non disponibili\n\n"
                except:
                    msg += f"*{idx}. {device_name}*\n"
                    msg += f"  - ID: `{device_id}`\n"
                    msg += f"  - Tipo: {device_type}\n"
                    msg += f"  - Errore nel caricamento dei dettagli\n\n"
            else:
                msg += f"*{idx}. {device_name}*\n"
                msg += f"  - ID: `{device_id}`\n"
                msg += f"  - Tipo: {device_type}\n"
                msg += f"  - Collegato il: {connected_at}\n\n"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante il recupero dei dispositivi: {str(e)}")
        print(f"Errore in list_dt_devices_handler: {e}")
        
        
        
async def check_irregularities_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Esegue il servizio di controllo irregolarità su TUTTI i DT dell'utente 
    e notifica i risultati.
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    dt_factory = context.application.bot_data['dt_factory']
    db_service = context.application.bot_data['db_service']

    try:
        # --- INIZIO MODIFICA CRUCIALE ---
        # Accediamo alla collezione dei DT direttamente, come fa /list_dt
        user_dt_docs = db_service.query_drs("digital_twins", {"metadata.user_id": user_db_id})
        if not user_dt_docs:
            await update.message.reply_text("ℹ️ Non hai Digital Twin registrati. Creane uno con `/create_dt <nome>`.")
            return
        # --- FINE MODIFICA CRUCIALE ---
        
        await update.message.reply_text(f"🔍 Eseguo il controllo delle irregolarità su {len(user_dt_docs)} Digital Twin...")

        all_alerts_messages = []

        for dt_doc in user_dt_docs:
            dt_id = str(dt_doc["_id"])
            dt_name = dt_doc.get("name", "DT senza nome")
            
            dt_instance = dt_factory.get_dt_instance(dt_id)
            if not dt_instance:
                all_alerts_messages.append(f"⚠️ Errore nel caricamento del DT '{dt_name}'.")
                continue

            alerts = dt_instance.execute_service("IrregularityAlertService")
            
            if alerts and any(alert_list for alert_list in alerts.values()):
                dt_alert_message = f"🚨 *Alert per DT '{dt_name}':*\n"
                door_alerts = alerts.get("door_alerts", [])
                if door_alerts:
                    dt_alert_message += "  🚪 *Porte aperte da troppo tempo:*\n"
                    for alert in door_alerts:
                        dt_alert_message += f"    - Dispenser: *{alert['dispenser_name']}* ({alert['minutes_open']} min)\n"
                
                all_alerts_messages.append(dt_alert_message)

        if not all_alerts_messages:
            await update.message.reply_text("✅ Nessuna irregolarità rilevata. Tutto in ordine!")
        else:
            final_message = "⚠️ Riepilogo irregolarità:\n\n" + "\n".join(all_alerts_messages)
            await update.message.reply_text(final_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        print(f"Errore in check_irregularities_handler: {e}")
        await update.message.reply_text("Si è verificato un errore critico durante il controllo.")

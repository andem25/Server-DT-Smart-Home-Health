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
            "❗ **Uso Corretto:**\n`/link_dispenser <dt_id> <dispenser_id>`\n\n"
            "**Esempio:**\n"
            "`/link_dispenser 68584c95-ce9c-... 001-paracetamolo`\n\n"
            "📝 **Come trovare gli ID:**\n"
            "- Usa `/list_smart_homes` per l'ID del Digital Twin (`dt_id`).\n"
            "- Usa `/my_dispensers` per l'ID del dispenser (`dispenser_id`).",
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
        
        # Verifica che il DT esista e appartenga all'utente
        dt = dt_factory.get_dt(dt_id)
        if not dt or dt.get('metadata', {}).get('user_id') != user_db_id:
            await update.message.reply_text("❌ Digital Twin non trovato o non ti appartiene.")
            return

        # Verifica che il dispenser esista e appartenga all'utente
        dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
        if not dispenser or dispenser.get('user_db_id') != user_db_id:
            await update.message.reply_text("❌ Dispenser non trovato o non ti appartiene.")
            return

        # Ottieni informazioni descrittive
        dispenser_name = dispenser.get('data', {}).get('name', 'Sconosciuto')
        dt_name = dt.get('name', 'Sconosciuto')

        # Verifica se il dispenser è già collegato ad altri Digital Twin
        collection = db_service.db["digital_twins"]
        query = {"digital_replicas": {"$elemMatch": {"id": dispenser_id, "type": "dispenser_medicine"}}}
        connected_dts = []
        
        for connected_dt in collection.find(query):
            connected_dt_id = str(connected_dt.get("_id"))
            # Non includere il DT di destinazione se già c'è
            if connected_dt_id != dt_id:
                connected_dts.append(connected_dt)
        
        # Se il dispenser è già collegato ad altri DT, rimuoverlo da quelli
        transfer_message = ""
        if connected_dts:
            for old_dt in connected_dts:
                old_dt_id = str(old_dt.get("_id"))
                old_dt_name = old_dt.get('name', 'Digital Twin')
                
                # Rimuovi la digital replica dal documento DT
                digital_replicas = old_dt.get('digital_replicas', [])
                updated_replicas = [dr for dr in digital_replicas if not (dr.get('id') == dispenser_id and dr.get('type') == "dispenser_medicine")]
                
                # Aggiorna il documento DT con le digital replicas filtrate
                collection.update_one(
                    {"_id": old_dt_id},
                    {"$set": {"digital_replicas": updated_replicas}}
                )
                
                transfer_message = f"⚠️ Il dispenser era collegato a '{old_dt_name}' ed è stato spostato."
                print(f"Dispenser {dispenser_id} rimosso dal Digital Twin {old_dt_id} e spostato a {dt_id}")
        
        # Ora registra il dispenser nel nuovo DT
        dt_manager.register_device(dt_id, "dispenser_medicine", dispenser_id)
        
        # Prepara il messaggio di risposta
        response_message = f"✅ Dispenser '{dispenser_name}' (`{dispenser_id}`) collegato con successo al Digital Twin '{dt_name}' (`{dt_id}`)."
        if transfer_message:
            response_message = f"{response_message}\n\n{transfer_message}"
        
        await update.message.reply_text(response_message, parse_mode="Markdown")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
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
        
        # CORREZIONE: Usa digital_replicas invece di connected_devices
        digital_replicas = dt.get('digital_replicas', [])
        
        if not digital_replicas:
            await update.message.reply_text(
                f"📱 Il Digital Twin '{dt.get('name')}' non ha dispositivi collegati.\n\n"
                f"Usa `/add_dispenser_dt {dt_id} <nome_medicinale>` per collegare un dispenser.",
                parse_mode="Markdown"
            )
            return
            
        # Componi il messaggio con i dispositivi
        msg = f"📱 Dispositivi collegati al Digital Twin '{dt.get('name')}':\n\n"
        
        for idx, device in enumerate(digital_replicas, 1):
            device_id = device.get('id', 'ID sconosciuto')
            device_type = device.get('type', 'Tipo sconosciuto')
            device_name = device.get('name', 'Nome sconosciuto')
            connected_at = device.get('connected_at', 'Data sconosciuta')
            
            # Sanitizza i valori per evitare problemi di formattazione Markdown
            device_name = device_name.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            device_id_safe = device_id.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            device_type_safe = device_type.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            
            # Ottieni dettagli aggiuntivi per i dispenser
            if device_type == 'dispenser_medicine':
                try:
                    dispenser = dt_factory.db_service.get_dr('dispenser_medicine', device_id)
                    if dispenser:
                        medicine_data = dispenser.get('data', {})
                        medicine_name = str(medicine_data.get('medicine_name', 'Nome sconosciuto')).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                        dosage = str(medicine_data.get('dosage', 'Non specificato')).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                        interval = str(medicine_data.get('interval', 'Non specificato')).replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
                        
                        msg += f"*{idx}. {device_name}*\n"
                        msg += f"  - ID: `{device_id_safe}`\n"
                        msg += f"  - Tipo: {device_type_safe}\n"
                        msg += f"  - Medicinale: {medicine_name}\n"
                        msg += f"  - Dosaggio: {dosage}\n"
                        msg += f"  - Intervallo: {interval}\n"
                        msg += f"  - Collegato il: {connected_at}\n\n"
                    else:
                        msg += f"*{idx}. {device_name}*\n"
                        msg += f"  - ID: `{device_id_safe}`\n"
                        msg += f"  - Tipo: {device_type_safe}\n"
                        msg += f"  - ATTENZIONE: Dettagli non disponibili\n\n"
                except Exception as detail_err:
                    print(f"Errore nel recupero dettagli dispenser {device_id}: {detail_err}")
                    msg += f"*{idx}. {device_name}*\n"
                    msg += f"  - ID: `{device_id_safe}`\n"
                    msg += f"  - Tipo: {device_type_safe}\n"
                    msg += f"  - Errore nel caricamento dei dettagli\n\n"
            else:
                msg += f"*{idx}. {device_name}*\n"
                msg += f"  - ID: `{device_id_safe}`\n"
                msg += f"  - Tipo: {device_type_safe}\n"
                msg += f"  - Collegato il: {connected_at}\n\n"
        
        # Se il messaggio è troppo lungo, tronca e aggiungi una nota
        if len(msg) > 4000:
            msg = msg[:3950] + "...\n\n(Troppi dispositivi da mostrare completamente)"
            
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Errore durante il recupero dei dispositivi: {str(e)}")
        print(f"Errore in list_dt_devices_handler: {e}")
        
        
        
async def check_irregularities_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Esegue il controllo delle irregolarità su TUTTI i DT dell'utente 
    e notifica i risultati - versione che mostra tutti gli alert salvati nel database
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    dt_factory = context.application.bot_data['dt_factory']
    db_service = context.application.bot_data['db_service']

    try:
        dt_collection = db_service.db["digital_twins"]
        user_dt_docs = list(dt_collection.find({
            "$or": [
                {"metadata.user_id": user_db_id},
                {"user_id": user_db_id},
                {"user_db_id": user_db_id},
                {"owner": user_db_id}
            ]
        }))

        if not user_dt_docs:
            await update.message.reply_text("ℹ️ Non hai Digital Twin registrati. Creane uno con `/create_smart_home <nome>`.", parse_mode="Markdown")
            return

        await update.message.reply_text(f"🔍 Eseguo il controllo delle irregolarità su {len(user_dt_docs)} Digital Twin...")

        all_alerts_messages = []

        for dt_doc in user_dt_docs:
            dt_id = str(dt_doc["_id"])
            dt_name = dt_doc.get("name", "DT senza nome")
            dt_alert_message = f"🚨 *Alert per DT '{dt_name}':*\n"

            # 1. Alert generali del DT
            dt_alerts = dt_doc.get("alerts", [])
            if dt_alerts:
                dt_alert_message += "  ⚠️ *Alert generali:*\n"
                for alert in dt_alerts:
                    dt_alert_message += f"    - {alert}\n"

            # 2. Alert nelle digital replicas (es. dispenser)
            digital_replicas = dt_doc.get("digital_replicas", [])
            for replica in digital_replicas:
                if replica.get("type") == "dispenser_medicine":
                    dispenser_id = replica.get("id")
                    dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
                    if dispenser:
                        # Alert specifici del dispenser
                        dispenser_alerts = dispenser.get("data", {}).get("alerts", [])
                        if dispenser_alerts:
                            dispenser_name = dispenser.get("data", {}).get("name", "Dispenser sconosciuto")
                            dt_alert_message += f"  💊 *Alert dispenser '{dispenser_name}':*\n"
                            for alert in dispenser_alerts:
                                dt_alert_message += f"    - {alert}\n"
                        # Alert emergenza attiva
                        if dispenser.get("data", {}).get("emergency_active", False):
                            dt_alert_message += f"  🚑 *Emergenza attiva su '{dispenser.get('data', {}).get('name', dispenser_id)}'*\n"

            # Solo se ci sono alert, aggiungi il messaggio
            if dt_alert_message.strip() != f"🚨 *Alert per DT '{dt_name}':*":
                all_alerts_messages.append(dt_alert_message)

        if not all_alerts_messages:
            await update.message.reply_text("✅ Nessuna irregolarità rilevata. Tutto in ordine!")
        else:
            final_message = "⚠️ Riepilogo irregolarità:\n\n" + "\n".join(all_alerts_messages)
            await update.message.reply_text(final_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        print(f"Errore in check_irregularities_handler: {e}")
        await update.message.reply_text("Si è verificato un errore critico durante il controllo.")
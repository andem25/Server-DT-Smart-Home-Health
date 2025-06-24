from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

async def add_dispenser_to_dt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea un dispenser di medicinali e lo collega a un Digital Twin esistente"""
    # Verifica che l'utente sia loggato
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    # Verifica i parametri
    if len(context.args) < 2:
        await update.message.reply_text(
            "❗ Uso: `/add_dispenser_dt <dt_id> <nome_medicinale> [dosaggio] [intervallo] [frequenza]`\n\n"
            "**Esempio (minimo):**\n"
            "`/add_dispenser_dt 6858433123e8f20d795d6ae6 Tachipirina`\n\n"
            "**Esempio (completo):**\n"
            "`/add_dispenser_dt 6858433123e8f20d795d6ae6 Paracetamolo 500mg 08-20 2`\n\n"
            "📝 **Parametri:**\n"
            "- `dt_id`: ID del Digital Twin (obbligatorio, usa `/list_dt` per vederli)\n"
            "- `nome_medicinale`: Nome del medicinale (obbligatorio)\n"
            "- `dosaggio`: (opzionale) Es. '500mg'\n"
            "- `intervallo`: (opzionale) Es. '08-20'\n"
            "- `frequenza`: (opzionale) Quante volte al giorno, es. 2",
            parse_mode="Markdown"
        )
        return

    # Estrai i parametri
    dt_id = context.args[0]
    medicine_name = context.args[1]
    
    # Parametri opzionali
    dosage = context.args[2] if len(context.args) > 2 else ""
    interval = context.args[3] if len(context.args) > 3 else "08-20"
    frequency = int(context.args[4]) if len(context.args) > 4 else 1
    
    try:
        # Ottieni il DT Manager
        dt_manager = context.application.bot_data.get('dt_manager')
        if not dt_manager:
            await update.message.reply_text("❌ Errore interno: Servizio DT Manager non disponibile.")
            return
        
        # Verifica che il DT specificato esista e appartenga all'utente
        dt_factory = context.application.bot_data.get('dt_factory')
        # CORREZIONE: Usa get_dt invece di get_dt_by_id
        dt = dt_factory.get_dt(dt_id)
        
        if not dt or dt.get('metadata', {}).get('user_id') != user_db_id:
            await update.message.reply_text(
                f"❌ Digital Twin non trovato o non ti appartiene. Controlla l'ID e riprova.\n"
                f"Usa `/list_dt` per vedere i tuoi Digital Twin.",
                parse_mode="Markdown"
            )
            return
        
        # Crea il dispenser, passando anche il dt_id che abbiamo ricevuto dal comando
        dispenser_id = dt_manager.create_dispenser(
            user_id=user_db_id,
            dt_id=dt_id,
            medicine_name=medicine_name,
            dosage=dosage,
            interval=interval,
            frequency=frequency
        )
        
        # Collega il dispenser al Digital Twin
        dt_manager.register_device(dt_id, "dispenser_medicine", dispenser_id)
        
        # Aggiungi anche una registrazione nel DT di questo dispenser
        dt_factory.update_dt(dt_id, {
            "$push": {
                "connected_devices": {
                    "id": dispenser_id,
                    "type": "dispenser_medicine",
                    "name": f"Dispenser - {medicine_name}",
                    "connected_at": datetime.now().isoformat()
                }
            }
        })
        
        await update.message.reply_text(
            f"✅ Dispenser per '{medicine_name}' creato con successo!\n\n"
            f"📋 Dettagli:\n"
            f"- ID: `{dispenser_id}`\n"
            f"- Medicinale: {medicine_name}\n"
            f"- Dosaggio: {dosage or 'Non specificato'}\n"
            f"- Intervallo: {interval}\n"
            f"- Frequenza: {frequency} volte al giorno\n\n"
            f"🔗 Collegato al Digital Twin: {dt.get('name', 'Sconosciuto')} (`{dt_id}`)\n\n"
            f"Usa `/my_medicines` per visualizzare tutti i tuoi dispenser.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante la creazione del dispenser: {str(e)}")
        print(f"Errore in add_dispenser_to_dt_handler: {e}")

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
                    dispenser = dt_factory.db_service.query_dr('dispenser_medicine', device_id)
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
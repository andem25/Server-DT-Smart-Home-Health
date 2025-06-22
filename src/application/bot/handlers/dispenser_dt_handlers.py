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
            "❗ Uso: /add_dispenser_dt <dt_id> <nome_medicinale> [dosaggio] [intervallo] [frequenza]\n\n"
            "Esempio: `/add_dispenser_dt 64abcd12ef34 Paracetamolo 500mg 08-20 2`\n\n"
            "📝 Parametri:\n"
            "- dt_id: ID del Digital Twin (usa /list_dt per vederli)\n"
            "- nome_medicinale: Nome del medicinale\n"
            "- dosaggio: (opzionale) Dosaggio, es. '500mg'\n"
            "- intervallo: (opzionale) Intervallo orario, es. '08-20'\n"
            "- frequenza: (opzionale) Quante volte al giorno, es. 2",
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
        
        # Crea il dispenser
        dispenser_id = dt_manager.create_dispenser(
            user_id=user_db_id,
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

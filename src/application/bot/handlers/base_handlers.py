from telegram import Update
from telegram.ext import ContextTypes
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command"""
    welcome_text = (
        "👋 *Benvenuto nello SMART DISPENSER BOT!* 🏠🤖\n\n"
        "Sono qui per aiutarti a gestire i tuoi dispensatori di medicinali e monitorare la salute nella tua casa intelligente.\n\n"
        "✅ Registra dispensatori\n"
        "✅ Monitora l'assunzione dei medicinali\n"
        "✅ Ricevi notifiche su temperatura e umidità\n"
        "✅ Controlla accessi e molto altro\n\n"
        "📚 Usa il comando `/help` per vedere tutte le funzionalità disponibili.\n\n"
        "Sono felice di aiutarti a prenderti cura della salute dei tuoi cari! 💊❤️"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler per il comando /help che fornisce una guida dettagliata di tutti i comandi"""
    
    # Ottieni lo stato di login dell'utente
    is_logged_in = 'username' in context.user_data and 'user_db_id' in context.user_data
    username = context.user_data.get('username', None)
    
    # Intestazione
    help_text = "*🤖 SMART DISPENSER BOT - GUIDA COMPLETA*\n\n"
    
    # Sezione comandi generali
    help_text += "*📋 COMANDI GENERALI*\n"
    help_text += "• `/start` - Avvia il bot\n"
    help_text += "• `/help` - Mostra questa guida dettagliata\n\n"
    
    # Sezione autenticazione
    help_text += "*🔐 GESTIONE ACCOUNT*\n"
    help_text += "• `/register <username> <password>` - Crea un nuovo account\n"
    help_text += "• `/login <username> <password>` - Accedi al tuo account\n"
    help_text += "• `/logout` - Esci dal tuo account\n"
    help_text += "• `/status` - Verifica il tuo stato di accesso\n\n"
    
    # Sezione gestione dispenser (solo per utenti loggati)
    help_text += "*💊 GESTIONE DISPENSER*\n"
    if is_logged_in:
        help_text += "• `/add_dispenser <id_univoco> <nome>` - Registra un nuovo dispenser\n"
        help_text += "• `/my_dispensers` - Mostra tutti i tuoi dispenser registrati\n"
        help_text += "• `/set_dispenser_time <id_dispenser> <inizio> <fine>` - Imposta orario preciso per assunzione (es: 19:30 20:00)\n"
        help_text += "• `/send_dispenser_message <id_dispenser> <messaggio>` - Invia un messaggio al dispenser\n"
        help_text += "• `/door_history <id_dispenser> [n|data_inizio data_fine]` - Mostra eventi porta con regolarità\n"
        help_text += "• `/environment_data <id_dispenser> [n|data_inizio data_fine]` - Mostra dati ambientali\n"
        help_text += "• `/set_environment_limits <id_dispenser> <tipo> <min> <max>` - Imposta limiti per temperatura o umidità\n\n"
        
        help_text += "\n*🤖 GESTIONE SMART HOME HEALTH*\n"
        help_text += "• `/create_smart_home <nome> [descrizione]` - Crea un nuovo Digital Twin completo\n"
        help_text += "• `/list_smart_homes` - Mostra tutti i tuoi Digital Twin\n"
        
        help_text += "\nIl Digital Twin creato includerà tutti i 9 servizi richiesti (FR-1 a FR-9):\n"
        help_text += "- FR-1: Promemoria Medicinali\n"
        help_text += "- FR-2: Rilevamento Apertura/Chiusura Porte\n"
        help_text += "- FR-3: Visualizzazione Messaggi Supervisore\n"
        help_text += "- FR-4: Registrazione Aderenza\n"
        help_text += "- FR-5: Avvisi Irregolarità\n"
        help_text += "- FR-6: Richiesta Aiuto Emergenza\n"
        help_text += "- FR-7: Monitoraggio Ambientale\n"
        help_text += "- FR-8: Registrazione Utenti e Supervisori\n"
        help_text += "- FR-9: Interazione Remota Supervisore\n\n"
        
        # --- RIGA CORRETTA ---
        help_text += "• `/link_dispenser <dt_id> <dispenser_id>` - Collega un dispenser esistente al DT\n"
        
        help_text += "• `/smart_home_devices <dt_id>` - Mostra dispositivi collegati a un DT\n\n"
    
    else:
        help_text += "⚠️ *Devi effettuare il login per accedere a questa sezione*\n\n"
    
    # Sezione notifiche MQTT
    help_text += "*🔔 SISTEMA DI NOTIFICHE*\n"
    help_text += "Il bot ti invierà automaticamente notifiche quando:\n"
    help_text += "• Il tuo dispenser registra un'assunzione\n"
    help_text += "• La porta viene aperta/chiusa fuori dall'orario configurato\n"
    help_text += "• La temperatura o l'umidità escono dai limiti configurati\n"
    help_text += "• La porta rimane aperta troppo a lungo\n"
    help_text += "• Si verifica un'emergenza\n\n"
    
    # Sezione esempi
    help_text += "*📝 ESEMPI DI UTILIZZO*\n"
    help_text += "*Inizia da qui:*\n"
    help_text += "1. Registrati: `/register mario123 password456`\n"
    help_text += "2. Effettua il login: `/login mario123 password456`\n"
    help_text += "3. Verifica stato: `/status`\n\n"
    
    help_text += "*Configurazione dispenser:*\n"
    help_text += "4. Registra dispenser: `/add_dispenser disp1 \"Aspirina Mattina\"`\n"
    help_text += "5. Verifica registrazione: `/my_dispensers`\n"
    help_text += "6. Imposta orario: `/set_dispenser_time disp1 08:00 08:30`\n"
    help_text += "7. Imposta limiti ambientali: `/set_environment_limits disp1 temp 18 28`\n\n"
    
    help_text += "*Creazione Digital Twin:*\n" 
    help_text += "8. Crea Digital Twin: `/create_smart_home CasaNonna \"DT casa nonna Maria\"`\n"
    help_text += "9. Elenca i tuoi DT: `/list_smart_homes`\n"
    help_text += "10. Collega dispenser: `/link_dispenser <dt_id> disp1`\n"
    help_text += "11. Verifica dispositivi: `/smart_home_devices <dt_id>`\n\n"
    
    help_text += "*Monitoraggio e controllo:*\n"
    help_text += "12. Visualizza dati ambientali: `/environment_data disp1`\n" 
    help_text += "13. Controlla eventi porta: `/door_history disp1`\n"
    help_text += "14. Invia messaggio: `/send_dispenser_message disp1 \"Ricorda di prendere la medicina\"`\n"
    help_text += "15. Controlla irregolarità: `/check_smart_home_alerts`\n"
    help_text += "16. Verifica aderenza settimanale: `/dispenser_adherence <dt_id>`\n\n"
    
    # Sezione risoluzione problemi
    help_text += "*🔧 RISOLUZIONE PROBLEMI*\n"
    help_text += "• Se non ricevi notifiche, verifica di aver effettuato il login\n"
    help_text += "• Se non vedi i tuoi dispenser, controlla con `/my_dispensers`\n"
    help_text += "• Per qualsiasi problema, contatta l'amministratore\n\n"
    
    # Stato attuale
    help_text += "*🟢 STATO ATTUALE*\n"
    if is_logged_in:
        help_text += f"Sei loggato come: *{username}*\n"
    else:
        help_text += "Non sei loggato. Usa `/login` o `/register` per iniziare.\n"
        
    await update.message.reply_text(help_text, parse_mode="Markdown")
async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo handler that replies with the same message received"""
    await update.message.reply_text(update.message.text)
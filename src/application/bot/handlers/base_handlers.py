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
    """Fornisce una guida dettagliata e accurata di tutti i comandi disponibili."""
    
    # Ottieni lo stato di login e il ruolo dell'utente
    is_logged_in = 'user_db_id' in context.user_data
    username = context.user_data.get('username')
    user_role = context.user_data.get('role')
    
    # Intestazione
    help_text = "🤖 *SMART HOME HEALTH BOT - GUIDA COMPLETA*\n\n"
    
    # --- Comandi disponibili per tutti ---
    help_text += "--- *COMANDI GENERALI* ---\n"
    help_text += "• `/start` - Mostra il messaggio di benvenuto.\n"
    help_text += "• `/help` - Mostra questa guida completa.\n\n"
    
    help_text += "--- *GESTIONE ACCOUNT* ---\n"
    help_text += "• `/register <username> <password>` - Crea un nuovo account supervisore.\n"
    help_text += "   _Esempio: /register mario.rossi sup3rPwd!_\n"
    help_text += "• `/login <username> <password>` - Accedi al tuo account.\n"
    help_text += "   _Esempio: /login mario.rossi sup3rPwd!_\n"
    help_text += "• `/logout` - Esci dal tuo account.\n"
    help_text += "• `/status` - Verifica se hai effettuato l'accesso.\n\n"
    
    # --- Comandi specifici per ruolo ---
    if is_logged_in:
        if user_role == "supervisor":
            # --- Comandi per Supervisori ---
            help_text += "--- *GESTIONE PAZIENTI (Supervisore)* ---\n"
            help_text += "• `/create_patient <username> <password> <dt_id>` - Crea un account per un paziente e lo associa a una casa smart.\n"
            help_text += "   _Esempio: /create_patient luigi.verdi pwdPaziente 65a1b2c3d4..._\n\n"
            
            help_text += "--- *GESTIONE DISPENSER (Supervisore)* ---\n"
            help_text += "• `/add_dispenser <id_univoco> <nome>` - Registra un nuovo dispenser fisico.\n"
            help_text += "   _Esempio: /add_dispenser 001-paracetamolo Dispenser Salotto_\n"
            help_text += "• `/my_dispensers` - Elenca tutti i dispenser che hai registrato.\n"
            help_text += "• `/set_dispenser_time <id_dispenser> <inizio> <fine>` - Imposta la fascia oraria per l'assunzione del farmaco.\n"
            help_text += "   _Esempio: /set_dispenser_time 001-paracetamolo 08:30 09:00_\n"
            help_text += "• `/delete_dispenser <id_dispenser>` - Rimuove un dispenser dal sistema.\n"
            help_text += "   _Esempio: /delete_dispenser 001-paracetamolo_\n"
            help_text += "• `/send_dispenser_message <id_dispenser> <messaggio>` - Invia un messaggio testuale al display del dispenser.\n"
            help_text += "   _Esempio: /send_dispenser_message 001-paracetamolo Ricorda acqua!_\n\n"
            
            help_text += "--- *GESTIONE SMART HOME (Supervisore)* ---\n"
            help_text += "• `/create_smart_home <nome>` - Crea una nuova casa smart (Digital Twin).\n"
            help_text += "   _Esempio: /create_smart_home Casa Nonna Maria_\n"
            help_text += "• `/list_smart_homes` - Mostra tutte le tue case smart.\n"
            help_text += "• `/link_dispenser <dt_id> <dispenser_id>` - Collega un dispenser a una casa smart.\n"
            help_text += "   _Esempio: /link_dispenser 65a1b2c3d4... 001-paracetamolo_\n"
            help_text += "• `/smart_home_devices <dt_id>` - Mostra i dispositivi collegati a una casa smart.\n"
            help_text += "   _Esempio: /smart_home_devices 65a1b2c3d4..._\n"
            help_text += "• `/delete_smart_home <dt_id>` - Elimina una casa smart.\n"
            help_text += "   _Esempio: /delete_smart_home 65a1b2c3d4..._\n"
            help_text += "• `/smart_home_telegrams` - Mostra gli ID Telegram associati alle tue case smart.\n\n"
            
            help_text += "--- *MONITORAGGIO E ALERT (Supervisore)* ---\n"
            help_text += "• `/check_smart_home_alerts` - Controlla e notifica tutte le irregolarità attive per le tue case smart.\n"
            help_text += "• `/dispenser_adherence <dt_id>` - Mostra l'aderenza terapeutica settimanale per i dispenser di una casa smart.\n"
            help_text += "   _Esempio: /dispenser_adherence 65a1b2c3d4..._\n"
            help_text += "• `/door_history <id_dispenser> [n|inizio fine]` - Mostra la cronologia di apertura/chiusura della porta di un dispenser.\n"
            help_text += "   _Esempi: /door_history 001-paracetamolo 50_ | _/door_history 001-paracetamolo 2024-01-01 2024-01-31_\n"
            help_text += "• `/environment_data <id_dispenser> [n|inizio fine]` - Mostra i dati ambientali (temperatura, umidità) di un dispenser.\n"
        
            help_text += "   _Esempi: /environment_data 001-paracetamolo 50_ | _/environment_data 001-paracetamolo 2024-01-01 2024-01-31_\n"
            help_text += "• `/set_environment_limits <id_dispenser> <tipo> <min> <max>` - Imposta i limiti per gli alert ambientali.\n"
            help_text += "   _Esempio: /set_environment_limits 001-paracetamolo temp 18 26_\n\n"
            
        elif user_role == "patient":
            # --- Comandi per Pazienti ---
            help_text += "--- *COMANDI DISPONIBILI (Paziente)* ---\n"
            help_text += "Come paziente, hai accesso a funzionalità limitate. Puoi usare:\n"
            help_text += "• `/start` - Messaggio di benvenuto.\n"
            help_text += "• `/help` - Questa guida.\n"
            help_text += "• `/logout` - Esci dal tuo account.\n"
            help_text += "• `/status` - Controlla il tuo stato di accesso.\n\n"
            help_text += "Per qualsiasi necessità, contatta il tuo supervisore.\n\n"
    else:
        # --- Utente non loggato ---
        help_text += "Per accedere a tutte le funzionalità, esegui il login o registrati.\n\n"
        
    # --- Stato attuale ---
    help_text += "--- *STATO ATTUALE* ---\n"
    if is_logged_in:
        role_display = "Supervisore" if user_role == "supervisor" else "Paziente"
        help_text += f"✅ Sei loggato come: *{username}*\n"
        help_text += f"👤 Ruolo: *{role_display}*\n"
        help_text += f"🆔 Il tuo ID Telegram: `{update.effective_user.id}`"
    else:
        help_text += "❌ Non hai effettuato l'accesso."
        
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo handler that replies with the same message received"""
    await update.message.reply_text(update.message.text)
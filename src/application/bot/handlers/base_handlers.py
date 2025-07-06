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
    user_role = context.user_data.get('role', None)
    
    # Intestazione
    help_text = "*🤖 SMART DISPENSER BOT - GUIDA COMPLETA*\n\n"
    
    # Sezione comandi generali (disponibili per tutti)
    help_text += "*📋 COMANDI GENERALI*\n"
    help_text += "• `/start` - Avvia il bot e mostra il messaggio di benvenuto\n"
    help_text += "• `/help` - Mostra questa guida dettagliata\n\n"
    
    # Sezione autenticazione (disponibile per tutti)
    help_text += "*🔐 GESTIONE ACCOUNT*\n"
    help_text += "• `/register <username> <password>` - Crea un nuovo account\n"
    help_text += "   _Esempio:_ `/register mario123 password456`\n"
    help_text += "• `/login <username> <password>` - Accedi al tuo account\n"
    help_text += "   _Esempio:_ `/login mario123 password456`\n"
    help_text += "• `/logout` - Esci dal tuo account\n"
    help_text += "• `/status` - Verifica il tuo stato di accesso\n\n"
    
    # Se l'utente è loggato, mostra i comandi disponibili in base al ruolo
    if is_logged_in:
        # Se l'utente è un supervisore, mostra tutti i comandi
        if user_role != "patient":
            # Comandi per gestire i pazienti
            help_text += "*👨‍⚕️ GESTIONE PAZIENTI*\n"
            help_text += "• `/create_patient <username> <password> <id_dt>` - Crea un account paziente\n"
            help_text += "   _Esempio:_ `/create_patient paziente1 pwd123 sid293023k0291aqq`\n\n"
            
            # Sezione gestione dispenser
            help_text += "*💊 GESTIONE DISPENSER*\n"
            help_text += "• `/add_dispenser <id_univoco> <nome>` - Registra un nuovo dispenser\n"
            help_text += "   _Esempio:_ `/add_dispenser disp123 \"Dispenser Aspirina\"`\n"
            help_text += "• `/my_dispensers` - Mostra tutti i tuoi dispenser registrati\n"
            help_text += "• `/set_dispenser_time <id_dispenser> <inizio> <fine>` - Imposta orario per l'assunzione\n"
            help_text += "   _Esempio:_ `/set_dispenser_time disp123 08:30 09:00`\n"
            help_text += "• `/dispenser_adherence <id_dispenser>` - Mostra l'aderenza settimanale\n"
            help_text += "   _Esempio:_ `/dispenser_adherence disp123`\n"
            help_text += "• `/delete_dispenser <id_dispenser>` - Elimina un dispenser registrato\n"
            help_text += "   _Esempio:_ `/delete_dispenser disp123`\n"
            help_text += "• `/send_dispenser_message <id_dispenser> <messaggio>` - Invia un messaggio al dispenser\n"
            help_text += "   _Esempio:_ `/send_dispenser_message disp123 \"Ricorda di prendere la medicina\"`\n\n"
            
            # Sezione monitoraggio ambientale e porta
            help_text += "*📊 MONITORAGGIO*\n"
            help_text += "• `/door_history <id_dispenser> [n|data_inizio data_fine]` - Mostra eventi porta\n"
            help_text += "   _Esempi:_\n"
            help_text += "   - `/door_history disp123` - Mostra gli ultimi eventi\n"
            help_text += "   - `/door_history disp123 50` - Mostra un numero specifico di eventi\n"
            help_text += "   - `/door_history disp123 2023-06-01 2023-06-30` - Eventi in un periodo specifico\n"
            help_text += "• `/environment_data <id_dispenser> [n|data_inizio data_fine]` - Mostra dati ambientali\n"
            help_text += "   _Esempi:_\n"
            help_text += "   - `/environment_data disp123` - Ultimi valori registrati\n"
            help_text += "   - `/environment_data disp123 50` - Numero specifico di valori\n"
            help_text += "   - `/environment_data disp123 2023-06-01 2023-06-30` - Periodo specifico\n"
            help_text += "• `/set_environment_limits <id_dispenser> <tipo> <min> <max>` - Imposta limiti ambientali\n"
            help_text += "   _Esempi:_\n"
            help_text += "   - `/set_environment_limits disp123 temp 18 28` - Limiti temperatura\n"
            help_text += "   - `/set_environment_limits disp123 humidity 30 60` - Limiti umidità\n\n"
            
            # Sezione gestione Smart Home (Digital Twin)
            help_text += "*🏠 GESTIONE SMART HOME*\n"
            help_text += "• `/create_smart_home <nome> [descrizione]` - Crea un nuovo Digital Twin\n"
            help_text += "   _Esempio:_ `/create_smart_home CasaNonna \"Casa della nonna Maria\"`\n"
            help_text += "• `/list_smart_homes` - Mostra tutti i tuoi Digital Twin\n"
            help_text += "• `/link_dispenser <dt_id> <dispenser_id>` - Collega dispenser al Digital Twin\n"
            help_text += "   _Esempio:_ `/link_dispenser 64abc123def disp123`\n"
            help_text += "• `/smart_home_devices <dt_id>` - Mostra dispositivi collegati a un Digital Twin\n"
            help_text += "   _Esempio:_ `/smart_home_devices 64abc123def`\n"
            help_text += "• `/check_smart_home_alerts` - Controlla irregolarità in tutti i Digital Twin\n"
            help_text += "• `/smart_home_telegrams` - Mostra gli ID Telegram associati ai tuoi Digital Twin\n"
            help_text += "• `/delete_smart_home <dt_id>` - Elimina un Digital Twin\n"
            help_text += "   _Esempio:_ `/delete_smart_home 64abc123def`\n\n"
            
        else:
            # Per i pazienti, mostra solo i comandi consentiti
            help_text += "*📝 COMANDI DISPONIBILI PER PAZIENTI*\n"
            help_text += "Come paziente, hai accesso limitato ai seguenti comandi:\n"
            help_text += "• `/start` - Mostra il messaggio di benvenuto\n"
            help_text += "• `/help` - Mostra questa guida\n"
            help_text += "• `/login <username> <password>` - Accedi al tuo account\n"
            help_text += "• `/logout` - Esci dal tuo account\n"
            help_text += "• `/status` - Verifica lo stato del tuo accesso\n\n"
            
            help_text += "Per richiedere assistenza, contatta il tuo supervisore.\n\n"
    
    # Stato attuale dell'utente
    help_text += "*🟢 STATO ATTUALE*\n"
    if is_logged_in:
        help_text += f"• Sei loggato come: *{username}*\n"
        help_text += f"• Ruolo: *{user_role if user_role else 'Supervisore'}*\n"
        help_text += f"• ID Telegram: *{update.effective_user.id}*\n"
    else:
        help_text += "Non sei loggato. Usa `/login` o `/register` per iniziare.\n"
        
    await update.message.reply_text(help_text, parse_mode="Markdown")
async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo handler that replies with the same message received"""
    await update.message.reply_text(update.message.text)
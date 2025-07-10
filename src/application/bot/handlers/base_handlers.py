from telegram import Update
from telegram.ext import ContextTypes

import telegram

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
    
    # --- Intestazione e comandi base (per tutti) ---
    help_text = "🤖 *SMART HOME HEALTH BOT - GUIDA COMPLETA*\n\n"
    
    help_text += "--- *COMANDI GENERALI* ---\n"
    help_text += "• `/start` – Avvia l'interazione col bot.\n"
    help_text += "• `/help` – Mostra questa guida.\n\n"
    
    help_text += "--- *GESTIONE ACCOUNT* ---\n"
    help_text += "• `/register <username> <password>` – Crea un nuovo account supervisore.\n"
    help_text += "  _Esempio:_ `/register mario.rossi sup3rPwd!`\n"
    help_text += "• `/login <username> <password>` – Esegue l'accesso.\n"
    help_text += "  _Esempio:_ `/login mario.rossi sup3rPwd!`\n"
    help_text += "• `/logout` – Chiude la sessione corrente.\n"
    help_text += "• `/status` – Verifica il tuo stato di login.\n\n"
    
    # --- Sezioni specifiche per ruolo ---
    if is_logged_in:
        if user_role == "supervisor":
            help_text += "🏡 *GESTIONE SMART HOME E PAZIENTI (Supervisore)*\n"
            help_text += "• `/create_smart_home <nome>` – Crea una nuova casa smart (Digital Twin).\n"
            help_text += "  _Esempio:_ `/create_smart_home Casa Nonna Maria`\n"
            help_text += "• `/list_smart_homes` – Elenca tutte le tue case smart.\n"
            help_text += "• `/create_patient <username> <password> <dt_id>` – Crea un account paziente e lo collega a una casa smart.\n"
            help_text += "  _Esempio:_ `/create_patient luigiverdi pwdPaziente 65a1b2...`\n"
            help_text += "• `/link_dispenser <dt_id> <dispenser_id>` – Collega un dispenser a una casa smart.\n"
            help_text += "  _Esempio:_ `/link_dispenser 65a1b2... 001-paracetamolo`\n"
            help_text += "• `/smart_home_devices <dt_id>` – Mostra i dispositivi di una casa smart.\n"
            help_text += "• `/delete_smart_home <dt_id>` – Elimina una casa smart.\n"
            help_text += "• `/smart_home_telegrams` – Mostra gli ID Telegram associati.\n\n"

            help_text += "💊 *GESTIONE DISPENSER E TERAPIA (Supervisore)*\n"
            help_text += "• `/add_dispenser <id_univoco> <nome>` – Registra un nuovo dispenser fisico.\n"
            help_text += "  _Esempio:_ `/add_dispenser 001-paracetamolo Dispenser Salotto`\n"
            help_text += "• `/my_dispensers` – Elenca i tuoi dispenser registrati.\n"
            help_text += "• `/set_dispenser_time <id> <inizio> <fine>` – Imposta la fascia oraria per l'assunzione.\n"
            help_text += "  _Esempio:_ `/set_dispenser_time 001-paracetamolo 08:30 09:00`\n"
            help_text += "• `/delete_dispenser <id_dispenser>` – Rimuove un dispenser.\n\n"

            help_text += "🔬 *MONITORAGGIO E CONTROLLO (Supervisore)*\n"
            help_text += "• `/send_dispenser_message <id> <msg>` – Invia un messaggio al display del dispenser.\n"
            help_text += "  _Esempio:_ `/send_dispenser_message 001-paracetamolo Ricorda acqua!`\n"
            help_text += "• `/dispenser_adherence <dt_id>` – Mostra l'aderenza terapeutica settimanale.\n"
            help_text += "• `/door_history <id> [n|inizio fine]` – Cronologia eventi dello sportello.\n"
            help_text += "  _Esempio:_ `/door_history 001-paracetamolo 50`\n"
            help_text += "• `/environment_data <id> [n|inizio fine]` – Mostra dati ambientali (temp/umidità).\n"
            help_text += "• `/set_environment_limits <id> <tipo> <min> <max>` – Imposta soglie per allarmi ambientali (temp/humidity).\n"
            help_text += "  _Esempio:_ `/set_environment_limits 001-paracetamolo temp 18 26`\n" # Corretto il refuso qui
            help_text += "• `/check_smart_home_alerts` – Controlla e notifica tutte le irregolarità attive.\n\n"

        elif user_role == "patient":
            help_text += "--- *COMANDI DISPONIBILI (Paziente)* ---\n"
            help_text += "Come paziente, puoi usare i comandi `/logout` e `/status`.\n"
            help_text += "Per qualsiasi necessità, contatta il tuo supervisore.\n\n"
    else:
        # Utente non loggato
        help_text += "Per accedere ai comandi specifici per ruolo, esegui il login o registrati come supervisore.\n\n"

    # --- Stato attuale ---
    help_text += "--- *STATO ATTUALE* ---\n"
    if is_logged_in:
        role_display = "Supervisore" if user_role == "supervisor" else "Paziente"
        help_text += f"✅ Sei connesso come: *{username}*\n"
        help_text += f"👤 Ruolo: *{role_display}*\n"
        help_text += f"🆔 Il tuo ID Telegram: `{update.effective_user.id}`"
    else:
        help_text += "❌ Non hai effettuato l'accesso."
        
    # Invia il messaggio completo
    try:
        await update.message.reply_text(help_text, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    except telegram.error.BadRequest as e:
        print(f"Errore durante l'invio del messaggio di aiuto: {e}")
        # Invia una versione semplificata senza formattazione come fallback
        await update.message.reply_text(help_text)


async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo handler that replies with the same message received"""
    await update.message.reply_text(update.message.text)
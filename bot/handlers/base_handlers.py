from telegram import Update
from telegram.ext import ContextTypes
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command"""
    await update.message.reply_text(
        "Hello! I'm your Telegram bot. How can I help you today?"
    )
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
    help_text += "• `/help` - Mostra un breve riepilogo dei comandi\n"
    help_text += "• `/help` - Mostra questa guida dettagliata\n"
    help_text += "• `/calc` - Calcolatrice semplice (es. `/calc 2 + 3`)\n\n"
    
    # Sezione autenticazione
    help_text += "*🔐 GESTIONE ACCOUNT*\n"
    help_text += "• `/register <username> <password>` - Crea un nuovo account\n"
    help_text += "• `/login <username> <password>` - Accedi al tuo account\n"
    help_text += "• `/logout` - Esci dal tuo account\n"
    help_text += "• `/status` - Verifica il tuo stato di accesso\n\n"
    
    # Sezione gestione dispenser (solo per utenti loggati)
    help_text += "*💊 GESTIONE DISPENSER*\n"
    if is_logged_in:
        help_text += "• `/add_medicine <id_univoco> <nome>` - Registra un nuovo dispenser\n"
        help_text += "• `/my_medicines` - Mostra tutti i tuoi dispenser registrati\n"
        help_text += "• `/set_interval <id_dispenser> <intervallo>` - Imposta l'intervallo di assunzione (es. 08-20)\n"
        help_text += "• `/regularity <id_dispenser>` - Mostra lo storico assunzioni per un dispenser\n\n"
    else:
        help_text += "⚠️ *Devi effettuare il login per accedere a questa sezione*\n\n"
    
    # Sezione notifiche MQTT
    help_text += "*🔔 SISTEMA DI NOTIFICHE*\n"
    help_text += "Il bot ti invierà automaticamente notifiche quando il tuo dispenser registra un'assunzione "
    help_text += "o ti invia avvisi. Non è necessario alcun comando aggiuntivo per ricevere le notifiche.\n\n"
    
    # Sezione esempi
    help_text += "*📝 ESEMPI DI UTILIZZO*\n"
    help_text += "1. Registrazione: `/register mario123 password456`\n"
    help_text += "2. Login: `/login mario123 password456`\n"
    help_text += "3. Registra dispenser: `/add_medicine disp1 Dispenser Aspirina`\n"
    help_text += "4. Imposta intervallo: `/set_interval disp1 08-20`\n\n"
    
    # Sezione risoluzione problemi
    help_text += "*🔧 RISOLUZIONE PROBLEMI*\n"
    help_text += "• Se non ricevi notifiche, verifica di aver effettuato il login\n"
    help_text += "• Se non vedi i tuoi dispenser, controlla con `/my_medicines`\n"
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
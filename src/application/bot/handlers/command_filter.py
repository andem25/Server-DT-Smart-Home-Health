from telegram import Update
from telegram.ext import ContextTypes
import functools

# Lista dei comandi disponibili per i pazienti
PATIENT_ALLOWED_COMMANDS = ["start", "help", "login", "logout", "status"]

def restrict_patient_commands(handler_func):
    """Decorator per limitare i comandi disponibili per i pazienti"""
    @functools.wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Controlla se l'utente è un paziente
        if context.user_data.get('role') == "patient":
            # Estrai il comando dal testo (senza il /)
            command = update.message.text.split()[0][1:]
            if command not in PATIENT_ALLOWED_COMMANDS:
                await update.message.reply_text(
                    "❌ Come paziente, hai accesso limitato ai comandi.\n\n"
                    "Puoi utilizzare solo:\n"
                    "/start - Mostra il messaggio di benvenuto\n"
                    "/help - Mostra i comandi disponibili\n"
                    "/logout - Esci dall'account\n"
                    "/status - Mostra lo stato del login"
                )
                return
        
        # Se l'utente non è un paziente o il comando è consentito, esegui la funzione originale
        return await handler_func(update, context)
    
    return wrapper
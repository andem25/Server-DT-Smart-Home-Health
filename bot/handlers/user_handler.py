import bcrypt
from telegram import Update
from telegram.ext import ContextTypes
from src.services.user_service import UserService
from typing import Dict, Set

# --- Handler Registrazione ---
async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❗ Usa: /register <username> <password>")
        return

    username, password = context.args[0], context.args[1]
    try:
        user_svc: UserService = context.application.bot_data['user_service']
    except KeyError:
        await update.message.reply_text("❌ Errore interno: Servizio utenti non disponibile.")
        print("Errore critico: 'user_service' non trovato in application.bot_data")
        return

    try:
        if user_svc.get_user_by_username(username):
            raise ValueError(f"Username '{username}' già in uso.")

        user_id = user_svc.create_user(username, password)
        await update.message.reply_text(f"✅ Utente '{username}' registrato con successo (ID: {user_id}).")
        context.user_data['user_db_id'] = user_id
        context.user_data['username'] = username
        await update.message.reply_text(f"ℹ️ Login effettuato automaticamente come {username}.")

    except ValueError as e:
        await update.message.reply_text(f"⚠️ Errore registrazione: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Si è verificato un errore imprevisto durante la registrazione: {e}")
        print(f"Errore in register_handler: {e}")

# --- Handler Login ---
async def login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❗ Usa: /login <username> <password>")
        context.user_data.pop('user_db_id', None)
        context.user_data.pop('username', None)
        return

    username, password = context.args[0], context.args[1]
    try:
        user_svc: UserService = context.application.bot_data['user_service']
    except KeyError:
        await update.message.reply_text("❌ Errore interno: Servizio utenti non disponibile.")
        print("Errore critico: 'user_service' non trovato in application.bot_data")
        return

    chat_id = update.effective_chat.id
    try:
        user_dr = user_svc.verify_user(username, password)
        if user_dr and '_id' in user_dr:
            user_db_id = user_dr['_id']
            context.user_data['user_db_id'] = user_db_id
            context.user_data['username'] = username
            await update.message.reply_text(f"✅ Login effettuato come {username}. Benvenuto!")

        else:
            context.user_data.pop('user_db_id', None)
            context.user_data.pop('username', None)
            await update.message.reply_text("❌ Credenziali errate.")

    except Exception as e:
        context.user_data.pop('user_db_id', None)
        context.user_data.pop('username', None)
        await update.message.reply_text(f"❌ Si è verificato un errore durante il login: {e}")
        print(f"Errore in login_handler: {e}")

# --- Handler Logout ---
async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    username = context.user_data.get('username')
    if username:
        context.user_data.pop('user_db_id', None)
        context.user_data.pop('username', None)
        await update.message.reply_text(f"✅ Logout effettuato per {username}.")
    else:
        await update.message.reply_text("ℹ️ Non risulti loggato.")

# --- Handler per verificare lo stato del login ---
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra lo stato del login dell'utente."""
    user_db_id = context.user_data.get('user_db_id')
    username = context.user_data.get('username')
    if user_db_id and username:
        await update.message.reply_text(f"✅ Sei loggato come '{username}' (ID: {user_db_id}).")
    else:
        await update.message.reply_text("❌ Non sei loggato. Usa /login <username> <password> o /register <username> <password>.")
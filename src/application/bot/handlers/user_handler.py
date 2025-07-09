import bcrypt
from telegram import Update
from telegram.ext import ContextTypes
from src.application.user_service import UserService
from typing import Dict, Set

from telegram.constants import ParseMode

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

        user_id = user_svc.create_user(username, password, role="supervisor")
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
    """Effettua il login dell'utente con username e password."""
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /login <username> <password>")
        return

    username = context.args[0]
    password = context.args[1]

    user_service = context.application.bot_data.get('user_service')
    if not user_service:
        await update.message.reply_text("❌ Errore interno: Servizio utente non disponibile.")
        return

    # Verifica le credenziali
    user_id = user_service.verify_credentials(username, password)
    if user_id:
        # Memorizza l'ID utente nei dati della sessione
        context.user_data['user_db_id'] = user_id
        context.user_data['username'] = username
        
        # Ottieni l'utente completo per verificare il ruolo
        db_service = context.application.bot_data.get('db_service')
        if not db_service:
            await update.message.reply_text("❌ Errore interno: Database non disponibile.")
            return
            
        user = db_service.get_dr("user", user_id)
        user_role = user.get('data', {}).get('role', "supervisor")
        context.user_data['role'] = user_role
        
        # Ottieni l'ID Telegram
        telegram_id = int(update.effective_user.id)
        
        try:
            # Per i pazienti, aggiungi l'ID Telegram solo al loro DT associato
            if user_role == "patient":
                user = db_service.get_dr("user", user_id)
                dt_id = user.get('data', {}).get('dt_id')
                if dt_id:
                    # Aggiorna con debug logging
                    print(f"DEBUG: Aggiungendo ID Telegram {telegram_id} al DT {dt_id}")
                    dt_collection = db_service.db["digital_twins"]
                    result = dt_collection.update_one(
                        {"_id": dt_id},
                        {"$addToSet": {"metadata.active_telegram_ids": telegram_id}}
                    )
                    print(f"DEBUG: Update risultato: {result.modified_count} documenti modificati")
                    
                    # Ottieni il nome del DT per il messaggio di benvenuto
                    dt = dt_collection.find_one({"_id": dt_id})
                    dt_name = dt.get("name", "Casa Smart") if dt else "Casa Smart"
                    
                    # Messaggio di benvenuto per paziente con comandi limitati
                    await update.message.reply_text(
                        f"✅ Login effettuato come paziente *{username}*.\n\n"
                        f"Sei collegato alla casa smart: *{dt_name}*\n\n"
                        "Comandi disponibili:\n"
                        "/start - Mostra il messaggio di benvenuto\n"
                        "/help - Mostra i comandi disponibili\n"
                        "/logout - Esci dall'account\n"
                        "/status - Mostra lo stato del login",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ Login effettuato come paziente *{username}*, ma non hai un Digital Twin associato.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                # Per i supervisori, usa il comportamento esistente
                dt_collection = db_service.db["digital_twins"]
                query = {"metadata.user_id": user_id}
                user_dt_docs = list(dt_collection.find(query))
                print(f"DEBUG: Trovati {len(user_dt_docs)} DT per l'utente {user_id}")
                
                for dt_doc in user_dt_docs:
                    dt_id = dt_doc.get("_id")
                    print(f"DEBUG: Aggiungendo ID Telegram {telegram_id} al DT {dt_id}")
                    result = dt_collection.update_one(
                        {"_id": dt_id},
                        {"$addToSet": {"metadata.active_telegram_ids": telegram_id}}
                    )
                    print(f"DEBUG: Update risultato: {result.modified_count} documenti modificati")
                
                await update.message.reply_text(
                    f"✅ Login effettuato con successo come supervisore *{username}*.",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            print(f"ERRORE nell'aggiornamento degli ID Telegram: {e}")
            import traceback
            traceback.print_exc()
            # Continua comunque il login
            await update.message.reply_text(
                f"✅ Login effettuato con successo come *{username}*.",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        context.user_data.pop('user_db_id', None)
        context.user_data.pop('username', None)
        await update.message.reply_text("❌ Credenziali errate.")

# --- Handler Logout ---
async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Effettua il logout dell'utente."""
    if 'user_db_id' in context.user_data:
        user_id = context.user_data['user_db_id']
        user_role = context.user_data.get('role', "supervisor")
        
        try:
            # Rimuovi l'ID Telegram dai Digital Twin dell'utente
            dt_factory = context.application.bot_data.get('dt_factory')
            db_service = context.application.bot_data.get('db_service')
            if dt_factory and db_service:
                telegram_id = int(update.effective_user.id)  # Converti esplicitamente a int
                print(f"DEBUG: Rimuovo ID Telegram {telegram_id} dai DT al logout")
                
                # Per i pazienti, rimuovi solo dall'unico DT associato
                if user_role == "patient":
                    # Recupera l'ID del DT associato al paziente
                    user = db_service.get_dr("user", user_id)
                    if user:
                        dt_id = user.get('data', {}).get('dt_id')
                        if dt_id:
                            # Rimuovi l'ID Telegram solo da questo DT
                            dt_collection = db_service.db["digital_twins"]
                            dt_collection.update_one(
                                {"_id": dt_id},
                                {"$pull": {"metadata.active_telegram_ids": telegram_id}}
                            )
                else:
                    # Per i supervisori, usa il comportamento esistente
                    dt_collection = db_service.db["digital_twins"]
                    query = {"metadata.user_id": user_id}
                    user_dt_docs = list(dt_collection.find(query))
                    
                    for dt_doc in user_dt_docs:
                        dt_id = str(dt_doc["_id"])
                        dt_collection.update_one(
                            {"_id": dt_id},
                            {"$pull": {"metadata.active_telegram_ids": telegram_id}}
                        )
        except Exception as e:
            print(f"Errore nella rimozione degli ID Telegram: {e}")
            import traceback
            traceback.print_exc()
        
        # Rimuovi i dati utente in ogni caso
        context.user_data.clear()
        await update.message.reply_text("✅ Logout effettuato con successo.")
    else:
        await update.message.reply_text("❌ Non hai effettuato il login.")

# --- Handler per verificare lo stato del login ---
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra lo stato del login dell'utente."""
    user_db_id = context.user_data.get('user_db_id')
    username = context.user_data.get('username')
    if user_db_id and username:
        await update.message.reply_text(f"✅ Sei loggato come '{username}' (ID: {user_db_id}).")
    else:
        await update.message.reply_text("❌ Non sei loggato. Usa /login <username> <password> o /register <username> <password>.")

# --- Handler per creare un paziente ---
async def create_patient_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Crea un nuovo utente paziente associato a un Digital Twin.
    Solo i supervisori possono usare questo comando.
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    # Verifica che l'utente corrente sia un supervisore
    db_service = context.application.bot_data.get('db_service')
    if not db_service:
        await update.message.reply_text("❌ Errore interno: Servizio database non disponibile.")
        return
        
    current_user = db_service.get_dr("user", user_db_id)
    if not current_user or current_user.get('data', {}).get('role') != "supervisor":
        await update.message.reply_text("❌ Solo i supervisori possono creare pazienti.")
        return
    
    # Controlla se sono stati forniti i parametri corretti
    if len(context.args) < 3:
        await update.message.reply_text(
            "❗ Uso: `/create_patient <username> <password> <dt_id>`\n\n"
            "Esempio: `/create_patient paziente1 password123 64abcd12ef34`\n\n"
            "Usa `/list_smart_homes` per vedere i tuoi Digital Twin disponibili.",
            parse_mode="Markdown"
        )
        return
        
    username = context.args[0]
    password = context.args[1]
    dt_id = context.args[2]
    
    # Verifica che il Digital Twin esista e appartenga al supervisore
    dt_factory = context.application.bot_data.get('dt_factory')
    if not dt_factory:
        await update.message.reply_text("❌ Errore interno: DT Factory non disponibile.")
        return
        
    dt = dt_factory.get_dt(dt_id)
    if not dt:
        await update.message.reply_text("❌ Digital Twin non trovato.")
        return
        
    if dt.get('metadata', {}).get('user_id') != user_db_id:
        await update.message.reply_text("❌ Puoi associare il paziente solo a un tuo Digital Twin.")
        return
    
    # Crea il nuovo utente paziente
    try:
        user_service = context.application.bot_data.get('user_service')
        if not user_service:
            await update.message.reply_text("❌ Errore interno: Servizio utente non disponibile.")
            return
            
        patient_id = user_service.create_user(
            username=username,
            password=password,
            role="patient",
            dt_id=dt_id
        )
        
        await update.message.reply_text(
            f"✅ Paziente creato con successo!\n\n"
            f"Username: `{username}`\n"
            f"Digital Twin associato: `{dt_id}`\n\n"
            f"Il paziente può ora effettuare il login con:\n"
            f"`/login {username} {password}`",
            parse_mode="Markdown"
        )
        
    except ValueError as e:
        await update.message.reply_text(f"❌ Errore: {str(e)}")
    except Exception as e:
        print(f"Errore nella creazione del paziente: {e}")
        await update.message.reply_text("❌ Si è verificato un errore durante la creazione del paziente.")
import bcrypt
from telegram import Update
from telegram.ext import ContextTypes
from src.services.user_service import UserService
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
    """Effettua il login dell'utente con username e password."""
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
            user_id = user_dr['_id']
            context.user_data['user_db_id'] = user_id
            context.user_data['username'] = username
            
            # Se il login ha successo, aggiungi l'ID Telegram ai Digital Twin dell'utente
            try:
                # Ottieni tutti i Digital Twin dell'utente
                dt_factory = context.application.bot_data.get('dt_factory')
                db_service = context.application.bot_data.get('db_service')
                if dt_factory and db_service:
                    telegram_id = int(update.effective_user.id)
                    
                    # Log esplicito per debug
                    print(f"DEBUG LOGIN: ID utente DB: {user_id}")
                    print(f"DEBUG LOGIN: ID Telegram: {telegram_id}")
                    
                    # Usa il db_service direttamente per la query
                    dt_collection = db_service.db["digital_twins"]
                    query = {"metadata.user_id": user_id}
                    user_dt_docs = list(dt_collection.find(query))
                    
                    print(f"DEBUG LOGIN: Trovati {len(user_dt_docs)} Digital Twin per l'utente")
                    
                    for dt_doc in user_dt_docs:
                        dt_id = str(dt_doc["_id"])
                        dt_name = dt_doc.get("name", "DT senza nome")
                        print(f"DEBUG LOGIN: Aggiornamento DT {dt_name} (ID: {dt_id})")
                        
                        # Usa direttamente l'operatore $addToSet per aggiungere l'ID in modo atomico 
                        # senza dover prima leggere e poi scrivere
                        update_result = dt_collection.update_one(
                            {"_id": dt_id},
                            {"$addToSet": {"metadata.active_telegram_ids": telegram_id}}
                        )
                        
                        print(f"DEBUG LOGIN: Risultato aggiornamento: modificati={update_result.modified_count}")
                        
                        # Rileggi il documento per verificare
                        dt_updated = dt_collection.find_one({"_id": dt_id})
                        print(f"DEBUG LOGIN: Nuovo stato DT {dt_id}: {dt_updated.get('metadata', {}).get('active_telegram_ids', [])}")
            except Exception as e:
                print(f"ERRORE nell'aggiornamento degli ID Telegram: {e}")
                import traceback
                traceback.print_exc()
                
            # Invia il messaggio di conferma login
            await update.message.reply_text(
                f"✅ Login effettuato con successo come *{username}*.", 
                parse_mode=ParseMode.MARKDOWN
            )
            
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
    """Effettua il logout dell'utente."""
    if 'user_db_id' in context.user_data:
        user_id = context.user_data['user_db_id']
        
        try:
            # Rimuovi l'ID Telegram dai Digital Twin dell'utente
            dt_factory = context.application.bot_data.get('dt_factory')
            db_service = context.application.bot_data.get('db_service')
            if dt_factory and db_service:
                telegram_id = int(update.effective_user.id)
                
                # Log esplicito per debug
                print(f"DEBUG LOGOUT: ID utente DB: {user_id}")
                print(f"DEBUG LOGOUT: ID Telegram da rimuovere: {telegram_id}")
                
                # Usa il db_service direttamente per la query
                dt_collection = db_service.db["digital_twins"]
                query = {"metadata.user_id": user_id}
                user_dt_docs = list(dt_collection.find(query))
                
                print(f"DEBUG LOGOUT: Trovati {len(user_dt_docs)} Digital Twin per l'utente")
                
                for dt_doc in user_dt_docs:
                    dt_id = str(dt_doc["_id"])
                    # Usa direttamente l'operatore $pull per rimuovere l'ID in modo atomico
                    update_result = dt_collection.update_one(
                        {"_id": dt_id},
                        {"$pull": {"metadata.active_telegram_ids": telegram_id}}
                    )
                    print(f"DEBUG LOGOUT: Risultato rimozione: modificati={update_result.modified_count}")
        except Exception as e:
            print(f"Errore nella rimozione degli ID Telegram: {e}")
            import traceback
            traceback.print_exc()
        
        # Rimuovi i dati utente in ogni caso
        context.user_data.clear()
        await update.message.reply_text("✅ Logout effettuato con successo.")
    else:
        await update.message.reply_text("⚠️ Non hai effettuato l'accesso.")

# --- Handler per verificare lo stato del login ---
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra lo stato del login dell'utente."""
    user_db_id = context.user_data.get('user_db_id')
    username = context.user_data.get('username')
    if user_db_id and username:
        await update.message.reply_text(f"✅ Sei loggato come '{username}' (ID: {user_db_id}).")
    else:
        await update.message.reply_text("❌ Non sei loggato. Usa /login <username> <password> o /register <username> <password>.")
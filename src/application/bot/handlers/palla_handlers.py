# filepath: bot/handlers/palla_handlers.py
from telegram import Update
from telegram.ext import ContextTypes
from flask import current_app
from src.virtualization.digital_replica.dr_factory import DRFactory
# from lib.auth_utils import is_authenticated, get_logged_user
from pydantic import ValidationError
from src.services.mqtt.mqtt_service import send_mqtt_message  # Assicurati di avere questa funzione definita


async def create_palla_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = update.effective_user.id
        # if not is_authenticated(telegram_id):
        #     await update.message.reply_text("❌ Devi eseguire prima il login con /login <username> <password>.")
        #     return

        if len(context.args) < 1:
            await update.message.reply_text("Uso: /create_palla <nome> <diametro_opzionale>")
            return

        nome = str(context.args[0]) if context.args else "base"
        diametro = float(context.args[1]) if context.args else 10.0

        db = current_app.config['DB_SERVICE']
        dr_factory = DRFactory("C:\\Users\\andre\\Downloads\\InternetOfThings_Architecture_Database_lecture-main (1)\\InternetOfThings_Architecture_Database_lecture-main\\the_proj\\src\\virtualization\\templates\\palla.yaml")

        # Generiamo un _id a piacere (o ipotizziamo che l’utente lo fornisca)
        palla_id = f"palla_{nome}_{telegram_id}"

        # Se esiste già la palla con questo ID, non la ricreiamo
        if db.get_dr("palla", palla_id):
            await update.message.reply_text("⚠️ Questa palla esiste già.")
            return

        new_palla = dr_factory.create_dr("palla", {
            "profile": {
                # se serve qualche campo custom
                "owner_id": str(telegram_id)
            },
            "data": {
                "name": nome,
                "diameter": diametro
            },
            "metadata": {}
        })

        # Impostiamo l’_id e salviamo
        new_palla["_id"] = palla_id

        db.save_dr("palla", new_palla)

        await update.message.reply_text(f"✅ Palla salvata con diametro {diametro} cm.")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {str(e)}")
        
        

async def list_my_balls_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra tutte le palle associate all'ID Telegram dell'utente."""
    try:
        telegram_id = update.effective_user.id
        db = current_app.config['DB_SERVICE']

        # Costruisci la query per trovare le palle dell'utente
        # Assumendo che owner_id sia salvato come stringa nel profilo
        query = {"profile.owner_id": str(telegram_id)}

        # Esegui la query sulla collezione 'balls' (o come definita nello schema)
        # Usiamo 'palla' come dr_type per ottenere il nome corretto della collezione
        my_balls = db.query_drs("palla", query)

        if not my_balls:
            await update.message.reply_text("Non hai nessuna palla registrata.")
            return

        # Formatta il messaggio di risposta
        response_message = "Ecco le tue palle registrate:\n\n"
        for ball in my_balls:
            ball_id = ball.get('_id', 'N/A')
            ball_name = ball.get('data', {}).get('name', 'N/A')
            ball_diameter = ball.get('data', {}).get('diameter', 'N/A')
            response_message += f"- ID: `{ball_id}`\n"
            response_message += f"  Nome: {ball_name}\n"
            response_message += f"  Diametro: {ball_diameter} cm\n\n"

        await update.message.reply_text(response_message, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante il recupero delle palle: {str(e)}")
        
        
        

async def update_diameter_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aggiorna il diametro di una palla esistente specificata per nome."""
    try:
        telegram_id = update.effective_user.id

        # 1. Parsing degli argomenti
        if len(context.args) != 2:
            await update.message.reply_text(
                "Uso: /update_diameter <nome_palla> <nuovo_diametro>"
            )
            return

        nome_palla = context.args[0]
        new_diameter_str = context.args[1]

        # 2. Ottieni servizi e costruisci ID
        db = current_app.config['DB_SERVICE']
        # Assicurati che il percorso sia corretto
        dr_factory = DRFactory("C:\\Users\\andre\\Downloads\\InternetOfThings_Architecture_Database_lecture-main (1)\\InternetOfThings_Architecture_Database_lecture-main\\the_proj\\src\\virtualization\\templates\\palla.yaml")
        palla_id = f"palla_{nome_palla}_{telegram_id}"

        # 3. Verifica se la palla esiste
        existing_ball = db.get_dr("palla", palla_id)
        if not existing_ball:
            await update.message.reply_text(f"⚠️ Palla con nome '{nome_palla}' non trovata.")
            return

        # 4. Converti e valida il nuovo diametro (tipo)
        try:
            new_diameter_float = float(new_diameter_str)
        except ValueError:
            await update.message.reply_text(f"❌ Valore '{new_diameter_str}' non è un numero valido per il diametro.")
            return

        # 5. Prepara i dati per la validazione e l'aggiornamento
        update_payload = {"data": {"diameter": new_diameter_float}}

        # 6. Validazione tramite DRFactory (per vincoli min/max)
        try:
            # Usiamo update_dr per validare. Passiamo la palla esistente e la modifica.
            # Questo valida l'intero stato aggiornato.
            validated_data = dr_factory.update_dr(existing_ball, update_payload)
            # Prendiamo solo la parte 'data' aggiornata per il $set
            update_for_db = {"data": validated_data.get("data", {})}

        except ValidationError as e:
            # Estrai e mostra l'errore di validazione specifico (es. diametro < 0)
            error_details = e.errors()
            error_msg = "Errore di validazione:\n"
            for err in error_details:
                # Cerca specificamente l'errore sul diametro
                if err['loc'] == ('data', 'diameter'):
                     error_msg += f"- Diametro: {err['msg']}\n"
                else: # Mostra altri eventuali errori nel data model
                     field = ".".join(map(str, err['loc']))
                     msg = err['msg']
                     error_msg += f"- Campo '{field}': {msg}\n"

            await update.message.reply_text(f"❌ {error_msg}")
            return

        # 7. Esegui l'aggiornamento sul database usando $set
        # Passiamo solo il campo da modificare dentro 'data'
        db.update_dr("palla", palla_id, {"$set": {"data.diameter": new_diameter_float}})

        await update.message.reply_text(
            f"✅ Diametro della palla '{nome_palla}' (ID: `{palla_id}`) aggiornato a {new_diameter_float} cm." ,
            parse_mode="Markdown"
        )

    except Exception as e:
        # Considera di loggare l'errore completo per il debug
        # logger.error(f"Errore in update_diameter_handler: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Errore durante l'aggiornamento del diametro: {str(e)}")



async def delete_ball_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina una palla esistente specificata per nome."""
    try:
        telegram_id = update.effective_user.id

        # 1. Parsing degli argomenti
        if len(context.args) != 1:
            await update.message.reply_text(
                "Uso: /delete_ball <nome_palla>"
            )
            return

        nome_palla = context.args[0]

        # 2. Ottieni servizio DB e costruisci ID
        db = current_app.config['DB_SERVICE']
        palla_id = f"palla_{nome_palla}_{telegram_id}"

        # 3. Tenta di eliminare la palla
        try:
            db.delete_dr("palla", palla_id)
            await update.message.reply_text(
                f"✅ Palla '{nome_palla}' (ID: `{palla_id}`) eliminata con successo.",
                parse_mode="Markdown"
            )
        except ValueError as e:
            # Gestisce l'errore specifico se la palla non viene trovata
            if "not found" in str(e):
                await update.message.reply_text(f"⚠️ Palla con nome '{nome_palla}' non trovata.")
            else:
                # Rilancia altri errori ValueError non previsti
                raise e

    except Exception as e:
        # Considera di loggare l'errore completo per il debug
        # logger.error(f"Errore in delete_ball_handler: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Errore durante l'eliminazione della palla: {str(e)}")


async def send_mqtt_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Invia un messaggio MQTT."""
    try:
        # 1. Parsing degli argomenti
        if len(context.args) < 1:
            await update.message.reply_text("Uso: /send_mqtt_message <messaggio>")
            return

        message = context.args[0]

        # 2. Invia il messaggio MQTT
        send_mqtt_message(message)

        await update.message.reply_text(f"✅ Messaggio MQTT inviato: {message}")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante l'invio del messaggio MQTT: {str(e)}")

# Rimuovi 'import uuid' se non lo usi più altrove
from telegram import Update
from telegram.ext import ContextTypes
from src.virtualization.digital_replica.dr_factory import DRFactory
# Rimuovi 'from flask import current_app' se non serve più
from flask import current_app
import asyncio
from datetime import datetime
import ssl
import re
from src.services.database_service import DatabaseService # Importa per type hinting (opzionale ma buono)
# from src.services.mqtt.mqtt_service import mqtt  # Importiamo il client mqtt
import paho.mqtt.client as mqtt
import ssl
# --- Crea un nuovo dispenser di medicine con ID fornito dall'utente ---
async def create_medicine_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea un nuovo dispenser associato all'utente loggato, usando un ID fornito dall'utente."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    # Ora ci aspettiamo ID e Nome
    if len(context.args) < 2:
        await update.message.reply_text("❗ Usa: /create_medicine <id_dispenser_univoco> <nome_per_il_tuo_dispenser>")
        return

    dispenser_id = context.args[0].strip() # ID fornito dall'utente
    nome = " ".join(context.args[1:]).strip() # Nome (può contenere spazi)

    if not dispenser_id:
        await update.message.reply_text("❗ L'ID del dispenser non può essere vuoto.")
        return
    if not nome:
        await update.message.reply_text("❗ Il nome del dispenser non può essere vuoto.")
        return

    try:
        db: DatabaseService = context.application.bot_data['db_service']
    except KeyError:
        await update.message.reply_text("❌ Errore interno: Servizio database non disponibile.")
        print("Errore critico: 'db_service' non trovato in application.bot_data")
        return

    # --- Controllo Unicità Globale dell'ID ---
    existing_dispenser = db.get_dr("dispenser_medicine", dispenser_id)
    if existing_dispenser:
        # ID già in uso, non importa da chi
        await update.message.reply_text(f"❌ L'ID dispenser '{dispenser_id}' è già in uso. Scegline un altro.")
        return
    # -----------------------------------------

    # --- Creazione associazione condizionale via MQTT ---
    await update.message.reply_text(f"⏳ In attesa di conferma dal dispenser '{dispenser_id}'...\nPremi il pulsante sul dispenser entro 30 secondi.")
    
    # Crea un oggetto Event per la sincronizzazione
    mqtt_response_received = asyncio.Event()
    mqtt_message_value = None
    
    # Callback per gestire i messaggi MQTT in arrivo
    def on_mqtt_message(client, userdata, msg):
        nonlocal mqtt_message_value
        if msg.topic == f"{dispenser_id}/assoc":
            try:
                payload = msg.payload.decode('utf-8').strip()
                print(f"MQTT: Ricevuto '{payload}' sul topic '{msg.topic}'")
                mqtt_message_value = payload
                mqtt_response_received.set()  # Segnala che il messaggio è arrivato
            except Exception as e:
                print(f"Errore nella gestione del messaggio MQTT: {e}")
    
    # Configura il client MQTT temporaneo per questa operazione
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.username_pw_set("test0", "Prova12345")
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_message = on_mqtt_message
    
    try:
        # Connetti e sottoscrivi
        client.connect("f1d601b5c9184556910bdc2b4e6dfe17.s1.eu.hivemq.cloud", 8883, 60)
        client.subscribe(f"{dispenser_id}/assoc")
        client.loop_start()
        
        # Aspetta il messaggio MQTT per 30 secondi
        try:
            await asyncio.wait_for(mqtt_response_received.wait(), timeout=30.0)
            
            # Verifica se il messaggio ricevuto è "1"
            if mqtt_message_value != "1":
                await update.message.reply_text(f"❌ Ricevuta risposta non valida dal dispenser. Operazione annullata.")
                return
                
        except asyncio.TimeoutError:
            await update.message.reply_text(f"⏱️ Timeout: nessuna conferma ricevuta dal dispenser entro 30 secondi. Operazione annullata.")
            return
    finally:
        # Pulisci le risorse MQTT
        client.loop_stop()
        client.disconnect()
    
    # Se siamo qui, significa che abbiamo ricevuto "1" dal topic
    await update.message.reply_text(f"✅ Confermato! Associazione con il dispenser riuscita.")
    
    # --- Prosegui con la creazione del dispenser nel DB ---
    dr_factory = DRFactory(".\\src\\virtualization\\templates\\dispenser_medicine.yaml")
    try:
        new_dispenser = dr_factory.create_dr("dispenser_medicine", {
            "data": {"name": nome},
        })
        # Imposta l'ID fornito dall'utente e l'ID utente del creatore
        new_dispenser["_id"] = dispenser_id
        new_dispenser["user_db_id"] = user_db_id

        db.save_dr("dispenser_medicine", new_dispenser)
        await update.message.reply_text(f"✅ Dispenser '{nome}' creato con successo con ID: `{dispenser_id}`.", parse_mode="Markdown")

    except ValueError as e: # Errori di validazione schema o DB
        await update.message.reply_text(f"❌ Errore dati dispenser: {e}")
    except Exception as e: # Altri errori
         await update.message.reply_text(f"❌ Errore imprevisto durante la creazione: {e}")
         print(f"Errore in create_medicine_handler: {e}")


# --- Lista i dispenser dell’utente ---
async def list_my_medicines_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista tutti i dispenser associati all'utente loggato, mostrando l'ID."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    try:
        db: DatabaseService = context.application.bot_data['db_service']
    except KeyError:
        await update.message.reply_text("❌ Errore interno: Servizio database non disponibile.")
        print("Errore critico: 'db_service' non trovato in application.bot_data")
        return

    try:
        my_dispensers = db.query_drs("dispenser_medicine", {"user_db_id": user_db_id})

        if not my_dispensers:
            await update.message.reply_text("ℹ️ Non hai dispenser registrati.")
            return

        msg = "I tuoi dispenser:\n"
        for d in my_dispensers:
            name = d.get('data', {}).get('name', 'Nome mancante')
            disp_id = d.get('_id', 'ID mancante') # Questo è l'ID (ora fornito dall'utente)
            interval = d.get('data', {}).get('interval', 'Non impostato')
            msg += f"- Nome: '{name}'\n  ID: `{disp_id}`\n  Intervallo: {interval}\n\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante il recupero dei dispenser: {e}")
        print(f"Errore in list_my_medicines_handler: {e}")


# --- Imposta l'intervallo per un dispenser (usando l'ID) ---
async def set_interval_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Imposta l'intervallo di assunzione usando l'ID univoco del dispenser."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❗ Usa: /set_interval <dispenser_id> <intervallo>\n(Trovi il <dispenser_id> con /list_my_medicines)")
        return

    dispenser_id = context.args[0]
    intervallo = context.args[1]

    if not re.match(r"^[0-2]?[0-9]-[0-2]?[0-9]$", intervallo):
         await update.message.reply_text("❌ Formato intervallo non valido. Usa HH-HH (es: 08-20).")
         return

    # --- CORREZIONE ACCESSO DB ---
    try:
        db: DatabaseService = context.application.bot_data['db_service']
    except KeyError:
        await update.message.reply_text("❌ Errore interno: Servizio database non disponibile.")
        print("Errore critico: 'db_service' non trovato in application.bot_data")
        return
    # --- FINE CORREZIONE ---

    try:
        dispenser = db.get_dr("dispenser_medicine", dispenser_id)

        if not dispenser:
            await update.message.reply_text(f"❌ Dispenser con ID `{dispenser_id}` non trovato.")
            return

        if dispenser.get("user_db_id") != user_db_id:
            await update.message.reply_text("❌ Non sei autorizzato a modificare questo dispenser.")
            return

        db.update_dr("dispenser_medicine", dispenser_id, {"$set": {"data.interval": intervallo}})
        dispenser_name = dispenser.get("data", {}).get("name", dispenser_id)
        await update.message.reply_text(f"✅ Intervallo '{intervallo}' impostato per '{dispenser_name}' (ID: `{dispenser_id}`).")

    except ValueError as e:
        await update.message.reply_text(f"❌ Errore dati durante l'aggiornamento: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore imprevisto durante l'impostazione dell'intervallo: {e}")
        print(f"Errore in set_interval_handler: {e}")


# --- Mostra la regolarità di un dispenser (usando l'ID) ---
async def show_regularity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra lo storico delle assunzioni usando l'ID univoco del dispenser."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("❗ Usa: /show_regularity <dispenser_id>\n(Trovi il <dispenser_id> con /list_my_medicines)")
        return

    dispenser_id = context.args[0]

    # --- CORREZIONE ACCESSO DB ---
    try:
        db: DatabaseService = context.application.bot_data['db_service']
    except KeyError:
        await update.message.reply_text("❌ Errore interno: Servizio database non disponibile.")
        print("Errore critico: 'db_service' non trovato in application.bot_data")
        return
    # --- FINE CORREZIONE ---

    try:
        dispenser = db.get_dr("dispenser_medicine", dispenser_id)

        if not dispenser:
            await update.message.reply_text(f"❌ Dispenser con ID `{dispenser_id}` non trovato.")
            return

        if dispenser.get("user_db_id") != user_db_id:
            await update.message.reply_text("❌ Non sei autorizzato a visualizzare questo dispenser.")
            return

        regularity_data = dispenser.get("data", {}).get("regularity", [])
        dispenser_name = dispenser.get("data", {}).get("name", dispenser_id)

        if not regularity_data:
            await update.message.reply_text(f"ℹ️ Nessuna registrazione di assunzione trovata per '{dispenser_name}' (ID: `{dispenser_id}`).")
            return

        msg = f"Storico assunzioni per '{dispenser_name}' (ID: `{dispenser_id}`):\n"
        for entry in sorted(regularity_data, key=lambda x: x.get("date", ""), reverse=True):
            date_str = entry.get("date", "Data sconosciuta")
            times_list = entry.get("times", [])
            times_str = ", ".join(sorted(times_list)) if times_list else "Nessuna assunzione registrata"
            msg += f"- {date_str}: {times_str}\n"

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante il recupero della regolarità: {e}")
        print(f"Errore in show_regolarity_handler: {e}")
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from src.virtualization.digital_replica.dr_factory import DRFactory
from flask import current_app
import asyncio
from datetime import datetime, timedelta
import ssl
import re
from src.services.database_service import DatabaseService
import paho.mqtt.client as mqtt
import ssl
from config.settings import MQTT_TOPIC_ASSOC




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
        try:
            payload = msg.payload.decode('utf-8').strip()
            print(f"MQTT: Ricevuto messaggio '{payload}' sul topic '{msg.topic}'")
            
            # Aggiorna il valore del messaggio
            mqtt_message_value = payload
            
            # Importante: imposta l'evento SOLO se il messaggio è "1"
            # Questo sblocca immediatamente l'attesa senza aspettare altri messaggi
            if payload == "1":
                mqtt_response_received.set()
                print(f"MQTT: Confermata associazione per {dispenser_id}")
            else:
                print(f"MQTT: Messaggio '{payload}' non valido per associazione, continuo ad attendere...")
        except Exception as e:
            print(f"MQTT: Errore nell'elaborazione del messaggio: {e}")
    
    # Configura il client MQTT temporaneo per questa operazione
    mqtt_subscriber = current_app.config.get('MQTT_SUBSCRIBER')
    
    try:
        # Verifica che il client MQTT interno sia inizializzato
        if not mqtt_subscriber.client:
            await update.message.reply_text("❌ Client MQTT non inizializzato. Impossibile procedere.")
            return
            
        # Associa la callback per la gestione dei messaggi
        mqtt_subscriber.client.on_message = on_mqtt_message
        
        # Sottoscrivi al topic corretto
        mqtt_subscriber.client.subscribe(f"{dispenser_id}/{MQTT_TOPIC_ASSOC}")
        
        # Il loop è già avviato nel MqttSubscriber, non serve chiamare loop_start
        
        # Aspetta il messaggio MQTT per 30 secondi
        try:
            # Invece di aspettare il timeout completo anche quando riceviamo il messaggio
            # controlliamo periodicamente se l'evento è stato impostato
            start_time = asyncio.get_event_loop().time()
            max_wait = 30.0  # Timeout massimo in secondi
            check_interval = 0.5  # Controlla ogni mezzo secondo
            
            while not mqtt_response_received.is_set():
                # Aspetta un breve intervallo
                await asyncio.sleep(check_interval)
                
                # Controlla se abbiamo superato il timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > max_wait:
                    await update.message.reply_text(f"⏱️ Timeout: nessuna conferma ricevuta dal dispenser entro 30 secondi. Operazione annullata.")
                    return
            
            # Se siamo usciti dal ciclo, l'evento è stato impostato
            # Verifica se il messaggio ricevuto è "1"
            if mqtt_message_value != "1":
                await update.message.reply_text(f"❌ Ricevuta risposta non valida dal dispenser. Operazione annullata.")
                return
                
        except Exception as e:
            await update.message.reply_text(f"❌ Errore durante l'attesa della conferma: {e}")
            return
    finally:
        # Ripristina la gestione messaggi originale e annulla la sottoscrizione
        if mqtt_subscriber and mqtt_subscriber.client:
            # Ripristina l'handler originale
            mqtt_subscriber.client.on_message = mqtt_subscriber.on_message
            
            # Annulla la sottoscrizione
            mqtt_subscriber.client.unsubscribe(f"{dispenser_id}/{MQTT_TOPIC_ASSOC}")
            # Non fermiamo il loop perché è gestito dalla classe MqttSubscriber
    
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
            
            msg += f"- Nome: '{name}'\n  ID: `{disp_id}`\n\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante il recupero dei dispenser: {e}")
        print(f"Errore in list_my_medicines_handler: {e}")




# --- Mostra la regolarità di un dispenser (usando l'ID) ---
async def show_regularity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra lo storico delle assunzioni usando l'ID univoco del dispenser."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("❗ Usa: /show_regolarity <dispenser_id>\n(Trovi il <dispenser_id> con /list_my_medicines)")
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


# --- Mostra l'aderenza settimanale con tick e X per ogni dispenser ---
async def show_weekly_adherence_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra l'aderenza settimanale ai medicinali per i dispensatori collegati a un Digital Twin specifico."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return
    
    # Verifica che l'ID DT sia fornito
    if len(context.args) < 1:
        await update.message.reply_text(
            "❗ Uso: /dispenser_adherence <dt_id>\n\n"
            "Esempio: `/dispenser_adherence abc123def456`\n\n"
            "Usa `/list_smart_homes` per vedere i tuoi Digital Twin disponibili.", 
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    dt_id = context.args[0]
    
    try:
        # Ottieni i servizi necessari in modo coerente con il resto del codice
        try:
            dt_factory = context.application.bot_data.get('dt_factory')
            db_service = context.application.bot_data.get('db_service')
            
            if not dt_factory or not db_service:
                await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
                return
        except KeyError:
            await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
            print("Errore critico: servizi non trovati in application.bot_data")
            return
        
        # Verifica che il DT esista e appartenga all'utente
        dt = dt_factory.get_dt(dt_id)
        if not dt:
            await update.message.reply_text("❌ Digital Twin non trovato.")
            return
            
        if dt.get('metadata', {}).get('user_id') != user_db_id:
            await update.message.reply_text("❌ Non sei autorizzato ad accedere a questo Digital Twin.")
            return
        
        # Usa digital_replicas invece di connected_devices
        digital_replicas = dt.get('digital_replicas', [])
        
        # Estrai gli ID dai digital_replicas
        dispenser_ids = [device['id'] for device in digital_replicas 
                         if device.get('type') == 'dispenser_medicine']
        
        if not dispenser_ids:
            await update.message.reply_text(
                f"ℹ️ Il Digital Twin '{dt.get('name', '')}' non ha dispensatori collegati.\n\n"
                f"Usa `/link_dispenser {dt_id} <dispenser_id>` per collegare un dispensatore.", 
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Ottieni i dispenser collegati al DT
        dispensers = []
        for dispenser_id in dispenser_ids:
            dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
            if dispenser:
                dispensers.append(dispenser)
        
        if not dispensers:
            await update.message.reply_text("ℹ️ Non ci sono dispensatori validi collegati a questo Digital Twin.")
            return
        
        # Calcola le date degli ultimi 7 giorni
        today = datetime.now().date()
        days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        days.reverse()  # Dal più vecchio al più recente
        
        # Formattazione giorni per intestazione
        short_days = [(datetime.strptime(day, "%Y-%m-%d").strftime("%d/%m")) for day in days]
        
        dt_name = dt.get('name', 'Digital Twin')
        msg = f"📊 *Aderenza settimanale ai medicinali - {dt_name}*\n\n"
        msg += "```\n"  # Formatting Markdown monospace
        
        # Miglioramento della formattazione della tabella con larghezze fisse
        medicine_col_width = 15
        day_col_width = 6
        
        # Intestazione migliorata
        msg += "Medicinale".ljust(medicine_col_width) + " | "
        msg += " | ".join(day.center(day_col_width) for day in short_days) + "\n"
        
        # Linea separatrice migliorata
        separator = "-" * medicine_col_width + "-|-" + "-|-".join("-" * day_col_width for _ in short_days) + "\n"
        msg += separator
        
        for dispenser in dispensers:
            # Accesso al nome del dispenser
            dispenser_name = dispenser.get("data", {}).get("name", "???")
            # Tronca il nome se troppo lungo
            if len(dispenser_name) > medicine_col_width:
                name_display = dispenser_name[:medicine_col_width-3] + "..."
            else:
                name_display = dispenser_name.ljust(medicine_col_width)
            
            # Ottieni i dati necessari
            door_events = dispenser.get("data", {}).get("door_events", [])
            medicine_time = dispenser.get("data", {}).get("medicine_time", {})
            start_time = medicine_time.get("start", "08:00")
            end_time = medicine_time.get("end", "20:00")
            
            # Controlla l'aderenza per ogni giorno
            day_status = []
            for day in days:
                # Filtra gli eventi della porta per questo giorno
                day_events = [e for e in door_events if e.get("timestamp", "").startswith(day)]
                
                if not day_events:
                    # Nessun dato disponibile per questo giorno
                    day_status.append("⌛")
                else:
                    # Controlla se c'è stata almeno una coppia apertura-chiusura nell'intervallo
                    open_events = False
                    close_events = False
                    
                    for event in day_events:
                        # Ottieni l'orario dall'evento con gestione degli errori
                        try:
                            timestamp = event.get("timestamp", "")
                            if "T" in timestamp:
                                event_time = timestamp.split("T")[1][:5]  # Estrae HH:MM
                            else:
                                continue  # Salta eventi con formato timestamp errato
                                
                            # Verifica se l'evento è nell'intervallo configurato
                            if start_time <= event_time <= end_time:
                                # Controlla lo stato dell'evento (usa "state" invece di "status")
                                event_state = event.get("state", "")
                                if event_state == "open":
                                    open_events = True
                                elif event_state == "closed":
                                    close_events = True
                        except Exception as e:
                            print(f"Errore nell'elaborazione dell'evento porta: {e}")
                    
                    # Se abbiamo sia apertura che chiusura nell'intervallo, è un'assunzione corretta
                    if open_events and close_events:
                        day_status.append("✅")
                    else:
                        day_status.append("❌")
            
            # Aggiungi la riga per questo dispenser
            msg += name_display + " | "
            msg += " | ".join(status.center(day_col_width) for status in day_status) + "\n"
        
        msg += "```\n"
        msg += "\n✅ = Assunzione corretta, ❌ = Non assunto, ⌛ = Dati non disponibili"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        print(f"Errore in show_weekly_adherence_handler: {e}")
        await update.message.reply_text(f"❌ Si è verificato un errore durante il recupero dei dati di aderenza: {e}", parse_mode=ParseMode.MARKDOWN)

# --- Imposta un intervallo orario personalizzato per l'assunzione dei medicinali ---
async def set_medicine_time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Imposta un intervallo orario personalizzato per l'assunzione dei medicinali.
    
    Uso:
        /set_med_time <dispenser_id> <inizio> <fine> - Imposta l'intervallo orario per l'assunzione
        
    Esempio:
        /set_med_time disp123 19:50 20:10 - Imposta assunzione tra le 19:50 e le 20:10
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return
        
    # Verifica che siano forniti tutti i parametri necessari
    if len(context.args) < 3:
        await update.message.reply_text(
            "❗ Uso: \n"
            "- `/set_med_time <dispenser_id> <inizio> <fine>` - per impostare orario di assunzione\n\n"
            "Esempi:\n"
            "- `/set_med_time disp123 19:50 20:10` - imposta assunzione tra le 19:50 e le 20:10\n",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    dispenser_id = context.args[0]
    start_time = context.args[1]
    end_time = context.args[2]
    
    # Verifica che gli orari siano nel formato corretto (HH:MM)
    time_pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
    if not time_pattern.match(start_time) or not time_pattern.match(end_time):
        await update.message.reply_text("❌ Formato orario non valido. Usa HH:MM (es. 19:50).")
        return
        
    # Converti in oggetti datetime per confronto
    now = datetime.now()
    start_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {end_time}", "%Y-%m-%d %H:%M")
    
    # Controlla che l'orario di inizio sia prima dell'orario di fine
    if start_dt >= end_dt:
        await update.message.reply_text("❌ L'orario di inizio deve essere anteriore all'orario di fine.")
        return
    
    # Ottieni i servizi necessari
    try:
        db_service = context.application.bot_data.get('db_service')
        if not db_service:
            await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
            return
            
        # Ottieni il dispenser
        dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
        if not dispenser:
            await update.message.reply_text(f"❌ Dispenser con ID `{dispenser_id}` non trovato.")
            return
            
        if dispenser.get("user_db_id") != user_db_id:
            await update.message.reply_text("❌ Non sei autorizzato a modificare questo dispenser.")
            return
            
        # Prepara l'aggiornamento
        update_operation = {
            "$set": {
                "data.medicine_time": {
                    "start": start_time,
                    "end": end_time
                }
            }
        }
        
        # Aggiorna il database
        db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
        
        # Aggiorna anche i Digital Twin collegati
        dt_factory = context.application.bot_data.get('dt_factory')
        if dt_factory:
            try:
                # CORREZIONE: usa list_dts() invece di get_all_dts()
                for dt in dt_factory.list_dts():
                    digital_replicas = dt.get('digital_replicas', [])
                    for dr in digital_replicas:
                        if dr.get('type') == 'dispenser_medicine' and dr.get('id') == dispenser_id:
                            # Ottieni l'istanza DT se esiste un servizio di promemoria
                            dt_instance = dt_factory.get_dt_instance(dt.get('_id'))
                            if dt_instance:
                                reminder_service = dt_instance.get_service("MedicationReminderService")
                                if reminder_service:
                                    reminder_service.update_medicine_times(dispenser_id, start_time, end_time)
            except Exception as e:
                print(f"Errore nell'aggiornamento dei servizi DT: {e}")
                # Non interrompiamo il flusso principale se questo fallisce
    
        # Ottieni il nome del dispenser
        dispenser_name = dispenser.get("data", {}).get("name", dispenser_id)
        
        # Rispondi all'utente
        await update.message.reply_text(
            f"✅ Orario di assunzione per '{dispenser_name}' impostato a:\n"
            f"- Inizio: {start_time}\n"
            f"- Fine: {end_time}\n\n"
            f"Riceverai una notifica a metà dell'intervallo orario."
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante l'impostazione dell'intervallo orario: {e}")
        print(f"Errore in set_medicine_time_handler: {e}")

# --- Elimina un dispenser ---
async def delete_dispenser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina un dispenser dell'utente e lo dissocia da tutti i Digital Twin."""
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return

    # Verifica che l'ID del dispenser sia stato fornito
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❗ Uso: `/delete_dispenser <dispenser_id>`\n\n"
            "Esempio: `/delete_dispenser disp1`\n\n"
            "Usa `/my_dispensers` per vedere i tuoi dispenser disponibili.",
            parse_mode="Markdown"
        )
        return

    dispenser_id = context.args[0]
    
    try:
        # Ottieni i servizi necessari
        dt_factory = context.application.bot_data.get('dt_factory')
        db_service = context.application.bot_data.get('db_service')
        
        if not dt_factory or not db_service:
            await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
            return
        
        # Verifica che il dispenser esista e appartenga all'utente
        dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
        if not dispenser:
            await update.message.reply_text("❌ Dispenser non trovato. Controlla l'ID e riprova.")
            return
            
        if dispenser.get('user_db_id') != user_db_id:
            await update.message.reply_text("❌ Non hai i permessi per eliminare questo dispenser.")
            return
        
        dispenser_name = dispenser.get('data', {}).get('name', 'Dispenser')
        
        # Trova tutti i Digital Twin a cui è collegato il dispenser
        # Usa la stessa logica di MqttSubscriber._find_dts_with_dr
        collection = db_service.db["digital_twins"]
        query = {"digital_replicas": {"$elemMatch": {"id": dispenser_id, "type": "dispenser_medicine"}}}
        connected_dts = []
        
        for dt in collection.find(query):
            connected_dts.append(str(dt.get("_id")))
        
        # Rimuovi il dispenser da tutti i Digital Twin trovati
        for dt_id in connected_dts:
            try:
                dt_doc = dt_factory.get_dt(dt_id)
                dt_name = dt_doc.get('name', 'Digital Twin')
                
                # Rimuovi la digital replica dal documento DT
                digital_replicas = dt_doc.get('digital_replicas', [])
                updated_replicas = [dr for dr in digital_replicas if not (dr.get('id') == dispenser_id and dr.get('type') == 'dispenser_medicine')]
                
                # Aggiorna il documento DT con le digital replicas filtrate
                collection.update_one(
                    {"_id": dt_id},
                    {"$set": {"digital_replicas": updated_replicas}}
                )
                
                print(f"Dispenser {dispenser_id} rimosso dal Digital Twin {dt_id}")
            except Exception as e:
                print(f"Errore nella rimozione del dispenser {dispenser_id} dal Digital Twin {dt_id}: {e}")
        
        # Elimina il dispenser dal database
        db_service.delete_dr("dispenser_medicine", dispenser_id)
        
        # Prepara il messaggio di conferma
        if connected_dts:
            dt_message = f"Dissociato da {len(connected_dts)} Digital Twin."
        else:
            dt_message = "Non era collegato a nessun Digital Twin."
            
        await update.message.reply_text(
            f"✅ Dispenser '{dispenser_name}' (`{dispenser_id}`) eliminato con successo.\n\n"
            f"{dt_message}",
            parse_mode="Markdown"
        )
    
    except Exception as e:
        print(f"Errore in delete_dispenser_handler: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Errore durante l'eliminazione del dispenser: {str(e)}")
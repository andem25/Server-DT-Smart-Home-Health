from flask import current_app
import logging

# Configura un logger di base per vedere i messaggi
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def send_alert_to_user(telegram_id: int, plant_name: str, humidity: float):
    try:
        bot = current_app.config["TELEGRAM_BOT"]
        message = (
            f"⚠ Allarme Umidità Bassa!\n\n"
            f"La tua pianta {plant_name} ha raggiunto solo {humidity:.1f}% di umidità.\n"
            f"Controlla se ha bisogno di essere innaffiata 💧"
        )
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")  # ✅ await obbligatorio
        print(f"✅ Notifica Telegram inviata a {telegram_id} per {plant_name}")
    except Exception as e:
        print(f"❌ Errore durante invio notifica Telegram: {e}")

async def send_emergency_alert(telegram_id: int, device_id: str, dt_name: str):
    """
    Invia una notifica di emergenza al supervisore
    
    Args:
        telegram_id: ID Telegram dell'utente supervisore
        device_id: ID del dispositivo che ha richiesto aiuto
        dt_name: Nome del Digital Twin a cui appartiene il dispositivo
    """
    try:
        bot = current_app.config["TELEGRAM_BOT"]
        message = (
            f"🚨 *ALLARME EMERGENZA*!\n\n"
            f"⚠️ *RICHIESTA DI AIUTO* dal dispositivo `{device_id}`\n"
            f"📍 Appartiene alla casa: *{dt_name}*\n\n"
            f"*Intervento richiesto immediatamente.*"
        )
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")
        print(f"✅ Notifica di emergenza inviata a {telegram_id} per dispositivo {device_id}")
    except Exception as e:
        print(f"❌ Errore durante invio notifica di emergenza: {e}")

def send_notification_to_dt_users(dt_factory, dt_id, message, fallback_id=157933243):
    """Invia notifiche a tutti gli ID Telegram attivi di un Digital Twin"""
    try:
        # Ottieni il Digital Twin
        dt = None
        if dt_factory:
            dt = dt_factory.get_dt(dt_id)
            print(f"DEBUG: Recuperato DT: {dt_id} - {'trovato' if dt else 'non trovato'}")
        
        # Ottieni gli ID Telegram attivi
        telegram_ids = []
        if dt and "metadata" in dt and "active_telegram_ids" in dt["metadata"]:
            active_ids = dt["metadata"]["active_telegram_ids"]
            print(f"DEBUG: ID Telegram trovati (raw): {active_ids}")
            
            # Normalizza gli ID come interi quando possibile
            for id_val in active_ids:
                try:
                    if id_val:  # Verifica che non sia None o vuoto
                        # Converti sempre a int per uniformità
                        telegram_ids.append(int(id_val))
                except (ValueError, TypeError):
                    print(f"AVVISO: Impossibile convertire ID Telegram '{id_val}' a intero")
            
            print(f"DEBUG: ID Telegram normalizzati: {telegram_ids}")
        
        # Se non ci sono ID, usa il fallback
        if not telegram_ids:
            telegram_ids = [fallback_id]
            print(f"ATTENZIONE: Nessun ID Telegram valido trovato per {dt_id}, uso fallback {fallback_id}")
    
        # Ottieni il token del bot dalle variabili d'ambiente
        from os import environ
        token = environ.get('TELEGRAM_TOKEN')
    
        if not token:
            print("ERRORE: Token Telegram non trovato per notifica")
            return 0
    
        # Invia il messaggio a tutti gli ID Telegram attivi
        import requests
        successful_sends = 0
        for telegram_id in telegram_ids:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": telegram_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=data)
            if response.status_code == 200:
                print(f"✅ Notifica inviata all'ID Telegram: {telegram_id}")
                successful_sends += 1
            else:
                print(f"❌ Errore nell'invio notifica a {telegram_id}: {response.status_code} - {response.text}")
    
        return successful_sends
            
    except Exception as e:
        print(f"Errore nell'invio della notifica: {e}")
        import traceback
        traceback.print_exc()
        return 0

# Aggiungi la nuova funzione
def send_generic_emergency_alert(db_service, device_id):
    """Invia un avviso di emergenza generico quando non c'è un DT associato"""
    try:
        # Ottieni il dispenser dal database
        dispenser = db_service.get_dr("dispenser_medicine", device_id)
        if not dispenser:
            return 0
            
        # Identifica l'utente proprietario
        user_db_id = dispenser.get("user_db_id")
        if not user_db_id:
            return 0
        
        # Recupera tutti i DT dell'utente per ottenere gli ID Telegram
        dt_collection = db_service.db["digital_twins"]
        query = {"metadata.user_id": user_db_id}
        user_dt_docs = list(dt_collection.find(query))
        
        # Raccogli tutti gli ID Telegram da tutti i DT dell'utente
        all_telegram_ids = set()
        for dt_doc in user_dt_docs:
            metadata = dt_doc.get("metadata", {})
            active_ids = metadata.get("active_telegram_ids", [])
            print(f"DEBUG: ID Telegram trovati in DT {dt_doc.get('_id')}: {active_ids}")
            
            for id_val in active_ids:
                try:
                    if id_val:  # Verifica che non sia None o vuoto
                        all_telegram_ids.add(int(id_val))
                except (ValueError, TypeError):
                    print(f"AVVISO: Impossibile convertire ID Telegram '{id_val}' a intero")
        
        print(f"DEBUG: Tutti gli ID Telegram raccolti: {all_telegram_ids}")
        
        # Se non ci sono ID, usa l'ID di fallback
        if not all_telegram_ids:
            all_telegram_ids = {157933243}
            print(f"ATTENZIONE: Nessun ID Telegram trovato per l'utente {user_db_id}, uso ID di fallback")
    
        # Prepara il messaggio
        dispenser_name = dispenser.get("data", {}).get("name", "Dispenser")
        message = (
            f"🚨 *ALLARME EMERGENZA*!\n\n"
            f"⚠️ *RICHIESTA DI AIUTO* dal dispositivo *{dispenser_name}* (`{device_id}`)\n\n"
            f"*Intervento richiesto immediatamente.*"
        )
        
        # Ottieni il token del bot dalle variabili d'ambiente
        from os import environ
        token = environ.get('TELEGRAM_TOKEN')
        
        if not token:
            print("ERRORE: Token Telegram non trovato")
            return 0
        
        # Invia a tutti gli ID recuperati
        import requests
        successful_sends = 0
        for telegram_id in all_telegram_ids:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": telegram_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=data)
            if response.status_code == 200:
                print(f"Notifica di emergenza generica inviata all'ID Telegram: {telegram_id}")
                successful_sends += 1
            else:
                print(f"Errore nell'invio notifica generica: {response.status_code}")
        
        return successful_sends
    except Exception as e:
        print(f"Errore nell'invio dell'avviso di emergenza generico: {e}")
        import traceback
        traceback.print_exc()
        return 0

def send_environmental_alert(db_service, dt_factory, device_id, measure_type, value, unit, min_value, max_value):
    """Invia una notifica di allarme ambientale all'utente."""
    try:
        print(f"DEBUG - send_environmental_alert - Parametri: device_id={device_id}, measure={measure_type}, value={value}")

        dispenser = db_service.get_dr("dispenser_medicine", device_id)
        if not dispenser:
            print(f"ERRORE: Dispenser {device_id} non trovato nel database")
            return 0

        dispenser_name = dispenser.get("data", {}).get("name", "Dispenser")

        # Trova i DT a cui il dispenser è associato
        dts_with_dispenser = []
        if dt_factory:
            all_dts = db_service.query_drs("digital_twins", {})
            for dt in all_dts:
                dt_id = str(dt.get("_id"))
                dt_instance = dt_factory.get_dt_instance(dt_id)
                if dt_instance and dt_instance.contains_dr("dispenser_medicine", device_id):
                    dts_with_dispenser.append(dt_id)

        print(f"DEBUG - send_environmental_alert - DT trovati per {device_id}: {dts_with_dispenser}")

        dt_name = "Casa"
        if dts_with_dispenser:
            dt_id = dts_with_dispenser[0]
            dt = dt_factory.get_dt(dt_id)
            if dt:
                dt_name = dt.get("name", "Casa")

        # Costruisci il messaggio di allarme
        status = "basso" if value < min_value else "alto"
        message = (
            f"⚠️ *ALLARME AMBIENTALE*\n\n"
            f"🌡️ Rilevato valore di {measure_type} {status}!\n"
            f"📊 Valore: *{value}{unit}*\n"
            f"🔍 Intervallo sicuro: {min_value}-{max_value}{unit}\n"
            f"📱 Dispositivo: *{dispenser_name}*\n"
            f"🏠 Posizione: {dt_name}\n\n"
            f"👉 Si consiglia di verificare le condizioni ambientali."
        )

        # Invia la notifica a tutti gli utenti attivi del DT
        if dts_with_dispenser:
            dt_id = dts_with_dispenser[0]
            return send_notification_to_dt_users(dt_factory, dt_id, message)
        else:
            # Fallback: se non c'è un DT, invia la notifica al proprietario del dispenser
            user_db_id = dispenser.get("user_db_id")
            if not user_db_id:
                print(f"ERRORE: ID utente non trovato per il dispenser {device_id}")
                return 0

            dt_collection = db_service.db["digital_twins"]
            query = {"metadata.user_id": user_db_id}
            user_dt_docs = list(dt_collection.find(query))

            all_telegram_ids = set()
            for dt_doc in user_dt_docs:
                metadata = dt_doc.get("metadata", {})
                active_ids = metadata.get("active_telegram_ids", [])
                for id_val in active_ids:
                    if id_val:
                        all_telegram_ids.add(int(id_val))

            if not all_telegram_ids:
                all_telegram_ids = {157933243} # Fallback ID

            from os import environ
            token = environ.get('TELEGRAM_TOKEN')
            if not token:
                print("ERRORE: Token Telegram non trovato")
                return 0

            import requests
            successful_sends = 0
            for telegram_id in all_telegram_ids:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = {"chat_id": telegram_id, "text": message, "parse_mode": "Markdown"}
                response = requests.post(url, json=data)
                if response.status_code == 200:
                    print(f"Notifica ambientale inviata all'ID Telegram: {telegram_id}")
                    successful_sends += 1
                else:
                    print(f"Errore nell'invio notifica: {response.status_code}")
            return successful_sends

    except Exception as e:
        print(f"Errore nell'invio dell'allarme ambientale: {e}")
        import traceback
        traceback.print_exc()
        return 0


def send_door_irregularity_alert(db_service, dt_factory, device_id, state, timestamp, event_details):
    """Invia una notifica all'utente quando si verifica un'apertura/chiusura porta irregolare"""
    try:
        # Ottieni il dispenser dal database
        dispenser = db_service.get_dr("dispenser_medicine", device_id)
        if not dispenser:
            return 0
            
        # Ottieni i dettagli del dispenser
        dispenser_name = dispenser.get("data", {}).get("name", "Dispenser")
        
        # Trova il Digital Twin associato al dispositivo
        dts_with_dispenser = []
        all_dts = db_service.query_drs("digital_twins", {})
        for dt in all_dts:
            dt_id = str(dt.get("_id"))
            dt_instance = dt_factory.get_dt_instance(dt_id)
            if dt_instance and dt_instance.contains_dr("dispenser_medicine", device_id):
                dts_with_dispenser.append(dt_id)
                
        dt_name = "Casa"  # Default
        
        if dts_with_dispenser:
            dt_id = dts_with_dispenser[0]  # Prendiamo il primo DT associato
            dt = dt_factory.get_dt(dt_id)
            if dt:
                dt_name = dt.get("name", "Casa")
    
        # Costruisci il messaggio di notifica
        time_str = timestamp.strftime("%H:%M:%S")
        date_str = timestamp.strftime("%d/%m/%Y")
        action = "aperta" if state == "open" else "chiusa"
        
        reason = event_details.get("reason", "fuori orario")
        if reason == "outside_schedule":
            reason = "fuori dall'orario di assunzione"
        elif reason == "multiple_openings":
            reason = "aperture multiple ravvicinate"
    
        message = (
            f"🚪 *APERTURA PORTA IRREGOLARE*\n\n"
            f"⚠️ La porta del dispenser *{dispenser_name}* è stata {action} *in modo irregolare*!\n"
            f"⏰ Orario: {time_str} del {date_str}\n"
            f"📍 Posizione: {dt_name}\n"
            f"❓ Motivo: {reason}\n\n"
            f"👉 Si consiglia di verificare la situazione."
        )
        
        # Invia la notifica a tutti gli utenti attivi del DT
        if dts_with_dispenser:
            dt_id = dts_with_dispenser[0]
            return send_notification_to_dt_users(dt_factory, dt_id, message)
        else:
            # Se non c'è un DT associato, cerca gli ID Telegram dell'utente proprietario
            user_db_id = dispenser.get("user_db_id")
            if not user_db_id:
                return 0
                
            # Recupera tutti i DT dell'utente per ottenere gli ID Telegram
            dt_collection = db_service.db["digital_twins"]
            query = {"metadata.user_id": user_db_id}
            user_dt_docs = list(dt_collection.find(query))
            
            # Raccogli tutti gli ID Telegram da tutti i DT dell'utente
            all_telegram_ids = set()
            for dt_doc in user_dt_docs:
                metadata = dt_doc.get("metadata", {})
                active_ids = metadata.get("active_telegram_ids", [])
                print(f"DEBUG: ID Telegram trovati in DT {dt_doc.get('_id')}: {active_ids}")
        
                for id_val in active_ids:
                    try:
                        all_telegram_ids.add(int(id_val))  # Converti a int
                    except (ValueError, TypeError):
                        if id_val:  # Aggiungi solo se non è vuoto
                            all_telegram_ids.add(id_val)
    
            print(f"DEBUG: Tutti gli ID Telegram raccolti: {all_telegram_ids}")
            
            # Se non ci sono ID, usa l'ID di fallback
            if not all_telegram_ids:
                all_telegram_ids = {157933243}
                print(f"ATTENZIONE: Nessun ID Telegram trovato per l'utente {user_db_id}, uso ID di fallback")
            
            # Invia il messaggio a tutti gli ID raccolti
            from os import environ
            token = environ.get('TELEGRAM_TOKEN')
            
            if not token:
                print("ERRORE: Token Telegram non trovato")
                return 0
            
            import requests
            successful_sends = 0
            for telegram_id in all_telegram_ids:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = {
                    "chat_id": telegram_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                
                response = requests.post(url, json=data)
                if response.status_code == 200:
                    print(f"Notifica di irregolarità porta inviata all'ID Telegram: {telegram_id}")
                    successful_sends += 1
                else:
                    print(f"Errore nell'invio notifica: {response.status_code}")
                    
            return successful_sends

    except Exception as e:
        print(f"Errore nell'invio dell'allarme porta irregolare: {e}")
        import traceback
        traceback.print_exc()
        return 0

def send_adherence_notification(db_service, dt_factory, device_id, message_type, details):
    """Invia una notifica all'utente relativa all'aderenza alle terapie"""
    try:
        # Ottieni il dispenser dal database
        dispenser = db_service.get_dr("dispenser_medicine", device_id)
        if not dispenser:
            return 0
            
        dispenser_name = dispenser.get("data", {}).get("name", "Dispenser")
        medicine_name = dispenser.get("data", {}).get("medicine_name", "Medicinale")
        
        # Trova i Digital Twin associati al dispositivo
        dts_with_dispenser = []
        all_dts = db_service.query_drs("digital_twins", {})
        for dt in all_dts:
            dt_id = str(dt.get("_id"))
            dt_instance = dt_factory.get_dt_instance(dt_id)
            if dt_instance and dt_instance.contains_dr("dispenser_medicine", device_id):
                dts_with_dispenser.append(dt_id)

        # Ottieni l'ID utente dal dispenser
        user_db_id = dispenser.get("user_db_id")

        # Costruisci il messaggio di notifica in base al tipo
        if message_type == "missed_dose":
            message = (
                f"💊 *DOSE MANCATA*\n\n"
                f"⚠️ Non è stata registrata l'assunzione di *{medicine_name}* dal dispenser *{dispenser_name}*\n"
                f"⏰ Era prevista alle: {details.get('scheduled_time', 'orario non specificato')}\n\n"
                f"👉 Ricorda di assumere il medicinale il prima possibile."
            )
        elif message_type == "low_adherence":
            message = (
                f"📊 *BASSA ADERENZA RILEVATA*\n\n"
                f"⚠️ L'aderenza alla terapia con *{medicine_name}* è sotto il {details.get('adherence_rate', 0)}%\n"
                f"📱 Dispenser: *{dispenser_name}*\n\n"
                f"👉 Ricorda l'importanza di seguire regolarmente la terapia prescritta."
            )
        else:
            message = (
                f"ℹ️ *NOTIFICA ADERENZA*\n\n"
                f"{details.get('custom_message', 'Messaggio relativo all\'aderenza alla terapia')}\n"
                f"📱 Dispenser: *{dispenser_name}*"
            )
    
        # Raccogli tutti gli ID Telegram da tutti i DT dell'utente
        all_telegram_ids = set()
        
        # Recupera tutti i DT dell'utente per ottenere gli ID Telegram
        if user_db_id:
            dt_collection = db_service.db["digital_twins"]
            query = {"metadata.user_id": user_db_id}
            user_dt_docs = list(dt_collection.find(query))
            
            for dt_doc in user_dt_docs:
                metadata = dt_doc.get("metadata", {})
                active_ids = metadata.get("active_telegram_ids", [])
                print(f"DEBUG: ID Telegram trovati in DT {dt_doc.get('_id')}: {active_ids}")
                
                for id_val in active_ids:
                    try:
                        if id_val:  # Verifica che non sia None o vuoto
                            all_telegram_ids.add(int(id_val))
                    except (ValueError, TypeError):
                        print(f"AVVISO: Impossibile convertire ID Telegram '{id_val}' a intero")
            
            print(f"DEBUG: Tutti gli ID Telegram raccolti: {all_telegram_ids}")
        
        # Se non ci sono ID, usa l'ID di fallback
        if not all_telegram_ids:
            all_telegram_ids = {157933243}
            print(f"ATTENZIONE: Nessun ID Telegram trovato per l'utente {user_db_id}, uso ID di fallback")
        
        # Invia il messaggio a tutti gli ID raccolti
        from os import environ
        token = environ.get('TELEGRAM_TOKEN')
        
        if not token:
            print("ERRORE: Token Telegram non trovato")
            return 0
        
        import requests
        successful_sends = 0
        for telegram_id in all_telegram_ids:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": telegram_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=data)
            if response.status_code == 200:
                print(f"Notifica di aderenza inviata all'ID Telegram: {telegram_id}")
                successful_sends += 1
            else:
                print(f"Errore nell'invio notifica: {response.status_code}")
                
        return successful_sends
            
    except Exception as e:
        print(f"Errore nell'invio della notifica di aderenza: {e}")
        import traceback
        traceback.print_exc()
        return 0

def send_door_open_alert(db_service, dt_factory, device_id, minutes_open):
    """
    Invia una notifica a tutti gli utenti associati quando la porta di un dispenser
    rimane aperta per troppo tempo.
    """
    try:
        logging.info(f"Avvio allerta porta aperta per il dispositivo {device_id} (aperta da {minutes_open} min).")
        dt_collection = db_service.db["digital_twins"]

        # 1. Trova il Digital Twin che contiene la replica del dispositivo specificato.
        query = {"digital_replicas": {"$elemMatch": {"id": device_id, "type": "dispenser_medicine"}}}
        dt_doc = dt_collection.find_one(query)

        if not dt_doc:
            logging.error(f"Nessun Digital Twin trovato per il dispenser con ID {device_id}.")
            return

        dt_id = str(dt_doc["_id"])
        logging.info(f"Trovato Digital Twin con ID {dt_id} per il dispositivo {device_id}.")

        # 2. Prepara il messaggio
        message = f"⚠️ Allarme! La porta del dispenser è aperta da {minutes_open} minuti."
        
        # 3. Invia la notifica usando la funzione esistente
        send_notification_to_dt_users(dt_factory, dt_id, message)

    except Exception as e:
        logging.critical(f"Errore critico non gestito in send_door_open_alert: {e}", exc_info=True)
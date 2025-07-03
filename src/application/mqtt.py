import paho.mqtt.client as mqtt
import ssl
import threading
import time
import json
from datetime import datetime, timedelta
from asyncio import run_coroutine_threadsafe
from flask import current_app
from src.application.bot.notifications import send_alert_to_user
import json
from datetime import timedelta
from config.settings import (
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    MQTT_TOPIC_TAKEN, MQTT_TOPIC_DOOR, MQTT_TOPIC_EMERGENCY,
    MQTT_TOPIC_ENVIRONMENTAL, MQTT_TOPIC_ASSOC, MQTT_TOPIC_NOTIFICATION,
    MQTT_TOPIC_LED_STATES
)

BROKER_URL = MQTT_BROKER
BROKER_PORT = MQTT_PORT
MQTT_USERNAME = MQTT_USERNAME
MQTT_PASSWORD = MQTT_PASSWORD



# --- Funzione di utilità per inviare messaggi MQTT ---
def send_mqtt_message(message: str, topic: str = MQTT_TOPIC_LED_STATES, qos: int = 2):
    """
    Funzione helper per inviare un singolo messaggio MQTT.
    
    Args:
        message: Messaggio da inviare
        topic: Topic su cui pubblicare
        qos: Quality of Service (0, 1 o 2), default 2 (exactly once)
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    connection_successful = False
    try:
        print(f"MQTT Sender: Tentativo di connessione a {BROKER_URL}:{BROKER_PORT} per invio...")
        client.connect(BROKER_URL, BROKER_PORT, 60)
        connection_successful = True
        client.loop_start()

        try:
            payload = int(message)
        except ValueError:
            payload = message

        print(f"MQTT Sender: Tentativo invio '{payload}' su topic '{topic}' con QoS {qos}...")
        result = client.publish(topic, payload, qos=qos)
        print(f"MQTT Sender: Messaggio messo in coda per l'invio (mid={result.mid}). In attesa di conferma...")
        result.wait_for_publish(timeout=10)

        if result.is_published():
            print(f"MQTT Sender: Messaggio (mid={result.mid}) pubblicato con successo.")
        else:
            print(f"MQTT Sender: Invio messaggio (mid={result.mid}) fallito o timeout.")

    except ConnectionRefusedError:
        print(f"MQTT Sender: Errore - Connessione rifiutata. Controlla indirizzo, porta e credenziali.")
    except ssl.SSLError as e:
        print(f"MQTT Sender: Errore SSL - {repr(e)}. Controlla la configurazione TLS/SSL.")
    except OSError as e:
        print(f"MQTT Sender: Errore di rete - {repr(e)}. Controlla la connessione e l'indirizzo del broker.")
    except Exception as e:
        print(f"MQTT Sender: Errore imprevisto durante l'invio: {repr(e)}")
    finally:
        if connection_successful:
            client.loop_stop()
            client.disconnect()
            print("MQTT Sender: Disconnesso.")



class MqttSubscriber:
    def __init__(self, broker_url=BROKER_URL, broker_port=BROKER_PORT, 
                 username=MQTT_USERNAME, password=MQTT_PASSWORD, db_service=None, app=None):
        self.broker_url = broker_url
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.db_service = db_service
        self.client = None
        self.is_running = False
        self.thread = None
        self.app = app  # Memorizza il riferimento all'app Flask
        
    def set_dt_factory(self, dt_factory):
        """Imposta il DTFactory per accedere ai Digital Twin"""
        self.dt_factory = dt_factory
        print("MQTT Subscriber: DTFactory collegato con successo")

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to the MQTT broker"""
        if rc == 0:
            print(f"MQTT Subscriber: Connesso al broker {self.broker_url}")
            
            # Sottoscrizioni principali usando QoS 2
            client.subscribe(f"+/{MQTT_TOPIC_TAKEN}", qos=2)
            print(f"MQTT Subscriber: Sottoscritto ai topic */{MQTT_TOPIC_TAKEN} con QoS 2")
            
            client.subscribe(f"+/{MQTT_TOPIC_DOOR}", qos=2)
            print(f"MQTT Subscriber: Sottoscritto ai topic */{MQTT_TOPIC_DOOR} con QoS 2")
            
            client.subscribe(f"+/{MQTT_TOPIC_EMERGENCY}", qos=2)
            print(f"MQTT Subscriber: Sottoscritto ai topic */{MQTT_TOPIC_EMERGENCY} con QoS 2")
            
            client.subscribe(f"+/{MQTT_TOPIC_ENVIRONMENTAL}", qos=2)
            print(f"MQTT Subscriber: Sottoscritto ai topic */{MQTT_TOPIC_ENVIRONMENTAL} con QoS 2")
            
            client.subscribe(f"+/{MQTT_TOPIC_ASSOC}", qos=2)
            print(f"MQTT Subscriber: Sottoscritto ai topic */{MQTT_TOPIC_ASSOC} con QoS 2")
            
        else:
            print(f"MQTT Subscriber: Fallita connessione al broker, codice {rc}")

    def on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8').strip()
            
            # Estrai l'ID del dispositivo dal topic
            device_id = topic.split('/')[0]
            topic_suffix = "/".join(topic.split('/')[1:])

            print(f"MQTT: Ricevuto '{payload}' sul topic '{topic}', ID dispositivo: {device_id}")

            # Gestione dei topic usando le variabili
            if topic_suffix == MQTT_TOPIC_TAKEN and payload == "1":
                self._update_regularity(device_id)
            
            # NUOVO: Gestisce il nuovo formato eventi porta
            elif topic_suffix == MQTT_TOPIC_DOOR:
                self._update_door_status(device_id, payload)
            
            elif topic_suffix == MQTT_TOPIC_EMERGENCY:
                if payload == "1":
                    print(f"🚨 EMERGENZA rilevata dal dispositivo: {device_id}")
                    self._handle_emergency_request(device_id)
                else:
                    print(f"MQTT Subscriber: Payload non valido per emergenza: '{payload}'")
        
            elif topic_suffix == MQTT_TOPIC_ENVIRONMENTAL:
                try:
                    env_data = json.loads(payload)
                    self._handle_environmental_data(device_id, env_data)
                except json.JSONDecodeError:
                    print(f"MQTT Subscriber: Payload dati ambientali non valido (non è JSON): '{payload}'")
        except Exception as e:
            print(f"MQTT Subscriber: Errore nella gestione dei dati ambientali: {e}")

    def _process_message(self, client, userdata, msg):
        """Elabora i messaggi MQTT ricevuti."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            # Gestione eventi porta
            if topic.startswith("dispenser/") and topic.endswith("/door"):
                try:
                    dispenser_id = topic.split("/")[1]
                    state = payload.get("state", "unknown")
                    
                    if state in ["open", "closed"]:
                        timestamp = datetime.now()
                        
                        # Aggiorna il documento nel database
                        update_operation = {
                            "$set": {
                                "data.door_status": state,
                                "data.last_door_event": timestamp.isoformat()
                            }
                        }
                        self.db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
                        
                        # Notifica i Digital Twin collegati
                        if hasattr(self, 'dt_factory'):
                            dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", dispenser_id)
                            for dt_id in dts_with_dispenser:
                                dt = self.dt_factory.get_dt_instance(dt_id)
                                if dt:
                                    door_service = dt.get_service("DoorEventService")
                                    if door_service:
                                        door_service.door_state_changed(dispenser_id, state, timestamp)
                        
                        print(f"Dispenser {dispenser_id}: porta {state} alle {timestamp.strftime('%H:%M:%S')}")
                except Exception as e:
                    print(f"Errore nella gestione evento porta: {e}")
            
            # Gestione topic di notifica (se il dispositivo risponde)
            elif topic.startswith("dispenser/") and topic.endswith("/notification/ack"):
                dispenser_id = topic.split("/")[1]
                status = payload.get("status")
                
                if status == "received":
                    print(f"Dispositivo {dispenser_id} ha ricevuto la notifica")
                    
                    # Qui potresti aggiornare lo stato nel database
                    # self.db_service.update_dr("dispenser_medicine", dispenser_id, 
                    #    {"$set": {"data.last_notification_ack": datetime.now().isoformat()}}
            
        except json.JSONDecodeError as e:
            print(f"Errore nella decodifica del payload JSON: {e}")
            print(f"Payload non valido: {msg.payload}")
        except Exception as e:
            print(f"Errore nella gestione del messaggio MQTT: {e}")

    def _update_door_status(self, dispenser_id, payload):
        """Aggiorna lo stato della porta del dispenser nel formato {"door":0,"time":"10:18:27"}"""
        try:
            # Parsing del payload
            try:
                data = json.loads(payload)
                door_value = data.get("door")
                time_str = data.get("time")
                
                # Converti il valore numerico in stato testuale
                if door_value == 1:
                    state = "open"
                elif door_value == 0:
                    state = "closed"
                else:
                    print(f"MQTT Subscriber: Valore porta non valido: {door_value}")
                    return
                
                # Crea timestamp completo
                if time_str:
                    # Crea un timestamp completo usando la data di oggi e l'ora ricevuta
                    today = datetime.now().strftime("%Y-%m-%d")
                    timestamp = datetime.fromisoformat(f"{today}T{time_str}")
                else:
                    timestamp = datetime.now()
                    time_str = timestamp.strftime("%H:%M:%S")
                
            except json.JSONDecodeError:
                print(f"MQTT Subscriber: Formato payload non valido per evento porta: '{payload}'")
                return
            except ValueError as e:
                print(f"MQTT Subscriber: Errore nel parsing dell'orario: {e}")
                timestamp = datetime.now()
                time_str = timestamp.strftime("%H:%M:%S")
        
            # Genera timestamp ISO
            timestamp_iso = timestamp.isoformat()
            
            # Ottieni il dispenser per verificare gli orari di medicina configurati
            dispenser = self.db_service.get_dr("dispenser_medicine", dispenser_id)
            if not dispenser:
                print(f"Dispenser {dispenser_id} non trovato nel database")
                return
            
            # Verifica se l'evento è regolare in base all'orario di assunzione configurato
            is_regular = False
            event_regularity = "irregular"
            reason = "outside_schedule"
            
            # Ottieni l'orario di assunzione configurato
            medicine_time = dispenser.get("data", {}).get("medicine_time", {})
            if medicine_time:
                start_time = medicine_time.get("start")
                end_time = medicine_time.get("end")
                
                if start_time and end_time:
                    # Converti orari in oggetti datetime per confronto
                    try:
                        today_str = timestamp.strftime("%Y-%m-%d")
                        start_dt = datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M")
                        end_dt = datetime.strptime(f"{today_str} {end_time}", "%Y-%m-%d %H:%M")
                        
                        # Verifica se l'evento è all'interno dell'intervallo configurato
                        if start_dt <= timestamp <= end_dt:
                            is_regular = True
                            event_regularity = "regular"
                            reason = "within_schedule"
                    except ValueError as e:
                        print(f"Errore nel parsing degli orari di medicina: {e}")
        
            # Prepara il nuovo evento porta con informazioni sulla regolarità
            new_door_event = {
                "state": state,
                "timestamp": timestamp_iso,
                "regularity": event_regularity,
                "reason": reason
            }
            
            # Ottieni gli eventi esistenti
            door_events = dispenser.get("data", {}).get("door_events", [])
            if not door_events:
                door_events = []
                
            # Aggiungi il nuovo evento mantenendo una lista FIFO
            door_events.append(new_door_event)
            
            # Limita il numero massimo di eventi memorizzati (conserva gli ultimi 1000)
            MAX_DOOR_EVENTS = 1000
            while len(door_events) > MAX_DOOR_EVENTS:
                door_events.pop(0)
        
            # Aggiorna il documento nel database
            update_operation = {
                "$set": {
                    "data.door_status": state,
                    "data.last_door_event": timestamp_iso,
                    "data.door_events": door_events
                }
            }
            self.db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
            
            # Log con informazioni sulla regolarità
            regularity_str = "REGOLARE" if is_regular else "IRREGOLARE"
            print(f"Dispenser {dispenser_id}: porta {state} alle {timestamp.strftime('%H:%M:%S')} - {regularity_str}")
            
            # NUOVO: Invia notifica all'utente se l'evento è irregolare
            if not is_regular:
                event_details = {
                    "timestamp": timestamp,
                    "state": state,
                    "regularity": event_regularity,
                    "reason": reason
                }
                self._send_door_irregularity_alert(dispenser_id, state, timestamp, event_details)
        
            # Notifica i Digital Twin collegati
            if hasattr(self, 'dt_factory'):
                # Trova tutti i DT che contengono questa DR
                dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", dispenser_id)
                
                for dt_id in dts_with_dispenser:
                    try:
                        dt = self.dt_factory.get_dt_instance(dt_id)
                        if dt:
                            # Ottieni e notifica il servizio DoorEventService se esiste
                            door_service = dt.get_service("DoorEventService")
                            if door_service:
                                door_service.door_state_changed(dispenser_id, state, timestamp, is_regular)
                    except Exception as e:
                        print(f"Errore nell'aggiornamento dello stato porta per DT {dt_id}: {e}")
            
        except Exception as e:
            print(f"Errore nell'aggiornamento dello stato porta per dispenser {dispenser_id}: {e}")
            import traceback
            traceback.print_exc()

    def _update_regularity(self, device_id):
        """Aggiorna la regolarità per il dispositivo specificato"""
        if not self.db_service:
            print("MQTT Subscriber: Servizio database non disponibile")
            return
            
        try:
            # Ottieni il dispenser dal database
            dispenser = self.db_service.get_dr("dispenser_medicine", device_id)
            if not dispenser:
                print(f"MQTT Subscriber: Dispenser con ID {device_id} non trovato nel database")
                return
                
            # Prepara data e ora correnti
            now = datetime.now()
            current_date = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M:%S")
            
            # Ottieni la lista di regolarità esistente
            regularity = dispenser.get("data", {}).get("regularity", [])
            
            # Cerca se esiste già un elemento per la data odierna
            date_entry = next((item for item in regularity if item.get("date") == current_date), None)
            
            if date_entry:
                # Se esiste già un'entry per oggi, aggiungi l'orario attuale
                if "times" not in date_entry:
                    date_entry["times"] = []
                date_entry["times"].append(current_time)
            else:
                # Altrimenti, crea un nuovo entry per oggi
                regularity.append({
                    "date": current_date,
                    "times": [current_time]
                })
            
            # Aggiorna il documento nel database
            self.db_service.update_dr(
                "dispenser_medicine", 
                device_id, 
                {"$set": {"data.regolarity": regularity}}
            )
            
            print(f"MQTT Subscriber: Aggiornata regolarità per {device_id}: {current_date} {current_time}")
        except Exception as e:
            print(f"MQTT Subscriber: Errore nell'aggiornamento della regolarità: {e}")

    def _update_medicine_taken(self, dispenser_id, payload):
        """Aggiorna lo stato del dispenser quando viene rilevata un'assunzione"""
        try:
            # Parsing del payload (potrebbe contenere dettagli sull'assunzione)
            data = json.loads(payload)
            taken_time = data.get("time", datetime.now().strftime("%H:%M"))

            # Ottieni il dispenser attuale per accedere ai dati esistenti
            dispenser = self.db_service.get_dr("dispenser_medicine", dispenser_id)
            if not dispenser:
                print(f"Dispenser {dispenser_id} non trovato")
                return

            # Aggiorna la Digital Replica del dispenser (unica entità)
            today = datetime.now().strftime("%Y-%m-%d")

            # Verifica se esiste già un'entry per oggi
            regularity = dispenser.get("data", {}).get("regularity", [])
            today_entry = next((r for r in regularity if r["date"] == today), None)

            update_operation = {}

            if today_entry:
                # Trova l'indice dell'entry di oggi
                today_index = next((i for i, r in enumerate(regularity) if r["date"] == today), None)
                if today_index is not None:
                    # Aggiorna l'entry esistente aggiungendo l'orario attuale
                    update_operation = {
                        "$push": {f"data.regularity.{today_index}.times": taken_time},
                        "$set": {"data.next_scheduled": (datetime.now() + timedelta(hours=8)).isoformat()}
                    }
            else:
                # Crea una nuova entry per oggi
                new_entry = {
                    "date": today,
                    "times": [taken_time],
                    "completed": False
                }
                update_operation = {
                    "$push": {"data.regularity": new_entry},
                    "$set": {"data.next_scheduled": (datetime.now() + timedelta(hours=8)).isoformat()}
                }

            # Effettua l'aggiornamento
            self.db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)

            print(f"Dispenser {dispenser_id}: registrata assunzione alle {taken_time}")

            # Notifica i Digital Twin associati per aggiornare i vari servizi
            # (es. AdherenceLoggingService)
            if hasattr(self, 'dt_factory'):
                # Trova tutti i DT che contengono questa DR
                dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", dispenser_id)

                # Esegui i servizi rilevanti su ogni DT
                for dt_id in dts_with_dispenser:
                    try:
                        dt = self.dt_factory.get_dt(dt_id)
                        # Trova i servizi AdherenceLoggingService e attivali
                        for service in dt.get("services", []):
                            if service.get("name") == "AdherenceLoggingService":
                                # Qui dovresti avere un modo per eseguire un servizio specifico
                                # Dipende dall'implementazione esatta del tuo sistema
                                pass
                    except Exception as e:
                        print(f"Errore nell'aggiornamento dei servizi DT: {e}")
        
        except json.JSONDecodeError:
            print(f"Payload non valido: {payload}")
        except Exception as e:
            print(f"Errore nell'aggiornamento dell'assunzione del medicinale: {e}")


    def start(self):
        """Avvia il subscriber in un thread separato"""
        if self.is_running:
            print("MQTT Subscriber: già in esecuzione")
            return
            
        def run_subscriber():
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            self.client.username_pw_set(self.username, self.password)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            
            # Configura TLS
            self.client.tls_set(cert_reqs=ssl.CERT_NONE)
            self.client.tls_insecure_set(True)
            
            try:
                print(f"MQTT Subscriber: Tentativo di connessione a {self.broker_url}:{self.broker_port}...")
                self.client.connect(self.broker_url, self.broker_port, 60)
                self.client.loop_start()
                self.is_running = True
                
                # Mantieni attivo il thread
                while self.is_running:
                    time.sleep(1)
                    
            except Exception as e:
                print(f"MQTT Subscriber: Errore durante l'esecuzione: {e}")
            finally:
                if self.client:
                    self.client.loop_stop()
                    self.client.disconnect()
                    print("MQTT Subscriber: Disconnesso")
                    
        self.thread = threading.Thread(target=run_subscriber)
        self.thread.daemon = True
        self.thread.start()
        print("MQTT Subscriber: Thread avviato")

    def stop(self):
        """Ferma il subscriber"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
            
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            print("MQTT Subscriber: Fermato e disconnesso")

    def connect(self):
        """Connect to the MQTT broker"""
        try:
            # Configura il client MQTT
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            self.client.username_pw_set(self.username, self.password)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            
            # Configura TLS
            self.client.tls_set(cert_reqs=ssl.CERT_NONE)
            self.client.tls_insecure_set(True)
            
            # Effettua la connessione al broker
            self.client.connect(self.broker_url, self.broker_port, 60)
            
            # Sottoscrivi ai topic necessari usando le variabili di configurazione
            self.client.subscribe([
                (f"+/{MQTT_TOPIC_TAKEN}", 0),             # Monitoraggio assunzione medicinali
                (f"+/{MQTT_TOPIC_DOOR}", 0),               # Stato della porta del dispenser
                (f"+/{MQTT_TOPIC_EMERGENCY}", 0),         # Topic per richieste di emergenza
                (f"+/{MQTT_TOPIC_ENVIRONMENTAL}", 0),     # Topic per dati ambientali combinati
                (f"+/{MQTT_TOPIC_ASSOC}", 0),             # Topic per associazione dispositivi
            ])
            
            print("MQTT Subscriber: Connessione effettuata e sottoscrizioni configurate")
            return True
            
        except Exception as e:
            print(f"MQTT Subscriber: Errore nella connessione al broker: {e}")
            return False

    def _handle_environmental_data(self, device_id, env_data):
        """
        Gestisce i dati ambientali combinati ricevuti via MQTT
        
        Args:
            device_id (str): ID univoco del dispositivo
            env_data (dict): Dizionario con temperatura, umidità e timestamp
        """
        try:
            # Estrai i dati dal payload
            temperature = env_data.get("avg_temperature")
            humidity = env_data.get("avg_humidity")
            time_str = env_data.get("time")
            
            if temperature is None or humidity is None:
                print(f"MQTT Subscriber: Dati ambientali incompleti per {device_id}")
                return
            
            # Valori soglia predefiniti
            MIN_TEMP = 18.0
            MAX_TEMP = 30.0
            MIN_HUMIDITY = 30.0
            MAX_HUMIDITY = 70.0
            MAX_MEASUREMENTS = 1000
            
            # Ottieni il dispenser dal database
            dispenser = self.db_service.get_dr("dispenser_medicine", device_id)
            if not dispenser:
                print(f"Dispositivo {device_id} non trovato nel database")
                return
            
            # Ottieni i limiti personalizzati, se disponibili
            custom_temp_limits = dispenser.get("data", {}).get("temperature_limits")
            if custom_temp_limits and len(custom_temp_limits) == 2:
                MIN_TEMP, MAX_TEMP = custom_temp_limits
                
            custom_humidity_limits = dispenser.get("data", {}).get("humidity_limits")
            if custom_humidity_limits and len(custom_humidity_limits) == 2:
                MIN_HUMIDITY, MAX_HUMIDITY = custom_humidity_limits
            
            # Controlla se i valori sono fuori range
            temp_out_of_range = temperature < MIN_TEMP or temperature > MAX_TEMP
            humidity_out_of_range = humidity < MIN_HUMIDITY or humidity > MAX_HUMIDITY
            
            # Crea timestamp ISO
            if time_str:
                # Crea un timestamp completo usando la data di oggi e l'ora ricevuta
                today = datetime.now().strftime("%Y-%m-%d")
                timestamp = datetime.fromisoformat(f"{today}T{time_str}")
            else:
                timestamp = datetime.now()
                
            timestamp_iso = timestamp.isoformat()
            
            # Prepara i nuovi dati ambientali
            new_temp_measurement = {
                "type": "temperature",
                "value": temperature,
                "timestamp": timestamp_iso,
                "unit": "°C"
            }
            
            new_humidity_measurement = {
                "type": "humidity",
                "value": humidity,
                "timestamp": timestamp_iso,
                "unit": "%"
            }
            
            # Gestisci l'array delle misurazioni in formato FIFO
            measurements = dispenser.get("data", {}).get("environmental_data", [])
            if not measurements:
                measurements = []
                
            # Aggiungi le nuove misurazioni
            measurements.append(new_temp_measurement)
            measurements.append(new_humidity_measurement)
            
            # Se abbiamo raggiunto il massimo, rimuovi le più vecchie
            while len(measurements) > MAX_MEASUREMENTS:
                measurements.pop(0)  # Rimuove il primo elemento (FIFO)
                
            # Aggiorna il documento nel database
            update_operation = {
                "$set": {
                    "data.environmental_data": measurements,
                    "data.last_environmental_update": timestamp_iso
                }
            }
            self.db_service.update_dr("dispenser_medicine", device_id, update_operation)
            
            print(f"Dati ambientali aggiornati per {device_id}: Temperatura: {temperature}°C, Umidità: {humidity}%")
            
            # Invia notifiche se necessario
            if temp_out_of_range:
                self._send_environmental_alert(device_id, "temperatura", temperature, "°C", MIN_TEMP, MAX_TEMP)
                
            if humidity_out_of_range:
                self._send_environmental_alert(device_id, "umidità", humidity, "%", MIN_HUMIDITY, MAX_HUMIDITY)
                
            # Notifica eventuali Digital Twin associati
            # Aggiorniamo per entrambe le misure
            self._update_dt_environmental_services(device_id, new_temp_measurement)
            self._update_dt_environmental_services(device_id, new_humidity_measurement)
                
        except Exception as e:
            print(f"Errore nella gestione dei dati ambientali: {e}")
            import traceback
            traceback.print_exc()


    def _handle_emergency_request(self, device_id):
        """Gestisce una richiesta di aiuto di emergenza"""
        try:
            # Verifica se esiste il dispositivo
            dispenser = self.db_service.get_dr("dispenser_medicine", device_id)
            if not dispenser:
                print(f"Dispositivo {device_id} non trovato")
                return
                
            # Trova tutti i DT collegati a questo dispositivo
            dt_ids = self._find_dts_with_dr("dispenser_medicine", device_id)
            
            if not dt_ids:
                print(f"Nessun Digital Twin associato al dispositivo {device_id}")
                # Invia comunque una notifica generica se possibile
                self._send_generic_emergency_alert(device_id)
                return
                
            for dt_id in dt_ids:
                try:
                    # Ottieni i dettagli del DT
                    dt = self.dt_factory.get_dt(dt_id)
                    dt_name = dt.get("name", "Digital Twin")
                    
                    # Attiva il servizio di emergenza
                    dt_instance = self.dt_factory.get_dt_instance(dt_id)
                    if dt_instance:
                        emergency_service = dt_instance.get_service("EmergencyRequestService")
                        if emergency_service:
                            emergency_service.emergency_requested(device_id, dt_id, dt_name)
                        else:
                            print(f"EmergencyRequestService non trovato nel DT {dt_id}")
                    else:
                        print(f"Istanza DT non trovata per {dt_id}")
                        
                except Exception as e:
                    print(f"Errore nella gestione dell'emergenza per DT {dt_id}: {e}")
        except Exception as e:
            print(f"Errore nella gestione dell'emergenza: {e}")

    def _find_dts_with_dr(self, dr_type, dr_id):
        """Trova tutti i Digital Twin che contengono una certa Digital Replica"""
        try:
            # Ottieni tutti i Digital Twin dal database
            all_dts = self.db_service.query_drs("digital_twins", {})
            matching_dts = []
            
            for dt in all_dts:
                dt_id = str(dt.get("_id"))
                dt_instance = self.dt_factory.get_dt_instance(dt_id)
                
                if dt_instance and dt_instance.contains_dr(dr_type, dr_id):
                    matching_dts.append(dt_id)
                    
            return matching_dts
        except Exception as e:
            print(f"Errore nella ricerca dei DT con DR {dr_id}: {e}")
            return []
            
    def _send_generic_emergency_alert(self, device_id):
        """Invia un avviso di emergenza generico quando non c'è un DT associato"""
        try:
            # Ottieni il dispenser dal database
            dispenser = self.db_service.get_dr("dispenser_medicine", device_id)
            if not dispenser:
                return
                
            # Identifica l'utente proprietario
            user_db_id = dispenser.get("user_db_id")
            if not user_db_id:
                return
            
            # Recupera tutti i DT dell'utente per ottenere gli ID Telegram
            dt_collection = self.db_service.db["digital_twins"]
            query = {"metadata.user_id": user_db_id}
            user_dt_docs = list(dt_collection.find(query))
            
            # Raccogli tutti gli ID Telegram da tutti i DT dell'utente
            all_telegram_ids = set()
            for dt_doc in user_dt_docs:
                metadata = dt_doc.get("metadata", {})
                active_ids = metadata.get("active_telegram_ids", [])
                for id_val in active_ids:
                    try:
                        all_telegram_ids.add(int(id_val))
                    except (ValueError, TypeError):
                        pass
            
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
            
            if token:
                # Invia a tutti gli ID recuperati
                import requests
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
                    else:
                        print(f"Errore nell'invio notifica generica: {response.status_code}")
                
        except Exception as e:
            print(f"Errore nell'invio dell'avviso di emergenza generico: {e}")
    
    
    def _send_environmental_alert(self, device_id, measure_type, value, unit, min_value, max_value):
        """
        Invia una notifica di allarme ambientale all'utente
        """
        try:
            dispenser = self.db_service.get_dr("dispenser_medicine", device_id)
            if not dispenser:
                return
                
            user_db_id = dispenser.get("user_db_id")
            if not user_db_id:
                return
                
            dispenser_name = dispenser.get("data", {}).get("name", "Dispenser")
            
            # Ottieni il Digital Twin associato al dispositivo
            dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", device_id)
            dt_name = "Casa"  # Default
            
            if dts_with_dispenser:
                dt_id = dts_with_dispenser[0]  # Prendiamo il primo DT associato
                dt = self.dt_factory.get_dt(dt_id)
                if dt:
                    dt_name = dt.get("name", "Casa")
            
            # Costruisci il messaggio di allarme
            if value < min_value:
                status = "basso"
            else:
                status = "alto"
                
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
                self._send_notification_to_dt_users(dt_id, message)
            else:
                # Se non c'è un DT associato, usa la funzione di fallback
                self._send_generic_emergency_alert(device_id)
                
        except Exception as e:
            print(f"Errore nell'invio dell'allarme ambientale: {e}")
    
    def _update_dt_environmental_services(self, device_id, measurement):
        """
        Aggiorna i servizi ambientali nei Digital Twin associati
        
        Args:
            device_id (str): ID del dispositivo
            measurement (dict): Dati della misurazione
        """
        try:
            if not hasattr(self, 'dt_factory'):
                return
                
            # Trova tutti i DT collegati a questo dispositivo
            dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", device_id)
            
            for dt_id in dts_with_dispenser:
                try:
                    dt_instance = self.dt_factory.get_dt_instance(dt_id)
                    if dt_instance:
                        # Controlla se il DT ha il servizio di monitoraggio ambientale
                        env_service = dt_instance.get_service("EnvironmentalMonitoringService")
                        if env_service:
                            # Passa la misurazione al servizio
                            env_service.process_measurement(device_id, measurement)
                        
                        # Verifica anche il servizio di irregolarità che potrebbe usare i dati ambientali
                        irreg_service = dt_instance.get_service("IrregularityAlertService")
                        if irreg_service:
                            # Eseguiamo una verifica delle irregolarità
                            dt_data = dt_instance.get_dt_data()
                            alerts = irreg_service.execute(dt_data)
                            
                            # Se ci sono alert ambientali, potremmo volerli gestire qui
                            if alerts.get("environmental_alerts"):
                                print(f"Rilevate irregolarità ambientali per DT {dt_id}")
                                
                except Exception as e:
                    print(f"Errore nell'aggiornamento dei servizi del DT {dt_id}: {e}")
                
        except Exception as e:
            print(f"Errore generale nell'aggiornamento dei servizi DT: {e}")
    
    def _send_door_irregularity_alert(self, device_id, state, timestamp, event_details):
        """
        Invia una notifica all'utente quando si verifica un'apertura/chiusura porta irregolare
        """
        try:
            # Ottieni il dispenser dal database
            dispenser = self.db_service.get_dr("dispenser_medicine", device_id)
            if not dispenser:
                return
                
            # Ottieni i dettagli del dispenser
            dispenser_name = dispenser.get("data", {}).get("name", "Dispenser")
            
            # Trova il Digital Twin associato al dispositivo
            dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", device_id)
            dt_name = "Casa"  # Default
            
            if dts_with_dispenser:
                dt_id = dts_with_dispenser[0]  # Prendiamo il primo DT associato
                dt = self.dt_factory.get_dt(dt_id)
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
                self._send_notification_to_dt_users(dt_id, message)
            else:
                # MODIFICA QUI: invece di inviare un'emergenza, invia direttamente la notifica
                # agli ID Telegram dell'utente proprietario del dispositivo
                user_db_id = dispenser.get("user_db_id")
                if user_db_id:
                    # Recupera tutti i DT dell'utente per ottenere gli ID Telegram
                    dt_collection = self.db_service.db["digital_twins"]
                    query = {"metadata.user_id": user_db_id}
                    user_dt_docs = list(dt_collection.find(query))
                    
                    # Raccogli tutti gli ID Telegram da tutti i DT dell'utente
                    all_telegram_ids = set()
                    for dt_doc in user_dt_docs:
                        metadata = dt_doc.get("metadata", {})
                        active_ids = metadata.get("active_telegram_ids", [])
                        for id_val in active_ids:
                            try:
                                all_telegram_ids.add(int(id_val))
                            except (ValueError, TypeError):
                                pass
                    
                    # Se non ci sono ID, usa l'ID di fallback
                    if not all_telegram_ids:
                        all_telegram_ids = {157933243}
                    
                    # Invia il messaggio di irregolarità (non di emergenza)
                    from os import environ
                    token = environ.get('TELEGRAM_TOKEN')
                    if token:
                        import requests
                        for telegram_id in all_telegram_ids:
                            url = f"https://api.telegram.org/bot{token}/sendMessage"
                            data = {
                                "chat_id": telegram_id,
                                "text": message,
                                "parse_mode": "Markdown"
                            }
                            requests.post(url, json=data)
    
        except Exception as e:
            print(f"Errore nell'invio dell'allarme porta irregolare: {e}")
            import traceback
            traceback.print_exc()
    
    def _send_adherence_notification(self, device_id, message_type, details):
        """
        Invia una notifica all'utente relativa all'aderenza alle terapie
        """
        try:
            # Ottieni il dispenser dal database
            dispenser = self.db_service.get_dr("dispenser_medicine", device_id)
            if not dispenser:
                return
                
            dispenser_name = dispenser.get("data", {}).get("name", "Dispenser")
            medicine_name = dispenser.get("data", {}).get("medicine_name", "Medicinale")
            
            # Trova il Digital Twin associato al dispositivo
            dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", device_id)
            
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
        
            # Invia la notifica a tutti gli utenti attivi del DT
            if dts_with_dispenser:
                dt_id = dts_with_dispenser[0]
                self._send_notification_to_dt_users(dt_id, message)
            else:
                # Se non c'è un DT associato, usa la funzione di fallback
                from os import environ
                token = environ.get('TELEGRAM_TOKEN')
                
                if token:
                    # ID di fallback
                    telegram_id = 157933243
                    
                    import requests
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    data = {
                        "chat_id": telegram_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }
                    
                    response = requests.post(url, json=data)
                    if response.status_code == 200:
                        print(f"Notifica aderenza inviata all'utente {telegram_id} (fallback)")
                    else:
                        print(f"Errore nell'invio della notifica: {response.status_code}")
                
        except Exception as e:
            print(f"Errore nell'invio della notifica di aderenza: {e}")
    
    def _send_notification_to_dt_users(self, dt_id, message, fallback_id=157933243):
        """
        Funzione helper per inviare notifiche a tutti gli ID Telegram attivi di un DT
        
        Args:
            dt_id (str): ID del Digital Twin
            message (str): Messaggio da inviare
            fallback_id (int): ID di fallback se non ci sono ID attivi
        """
        try:
            # Ottieni il Digital Twin per accedere agli ID Telegram attivi
            dt = None
            if hasattr(self, 'dt_factory') and self.dt_factory:
                dt = self.dt_factory.get_dt(dt_id)
        
            # Ottieni gli ID Telegram attivi dal DT
            telegram_ids = []
            if dt and "metadata" in dt and "active_telegram_ids" in dt["metadata"]:
                # Converti esplicitamente tutti gli ID a int
                try:
                    # Gestisci sia liste di stringhe che di interi
                    telegram_ids = [int(id_val) for id_val in dt["metadata"]["active_telegram_ids"]]
                    print(f"DEBUG: IDs Telegram trovati per notifica: {telegram_ids}")
                except (ValueError, TypeError) as e:
                    print(f"ERRORE nella conversione degli ID Telegram: {e}")
        
        # Se non ci sono ID attivi, usa l'ID di fallback
            if not telegram_ids:
                telegram_ids = [fallback_id]
                print(f"ATTENZIONE: Nessun ID Telegram trovato, uso ID di fallback {fallback_id}")
        
            # Ottieni il token del bot dalle variabili d'ambiente
            from os import environ
            token = environ.get('TELEGRAM_TOKEN')
        
            if not token:
                print("ERRORE: Token Telegram non trovato per notifica")
                return
        
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
                    print(f"Notifica inviata all'ID Telegram: {telegram_id}")
                    successful_sends += 1
                else:
                    print(f"Errore nell'invio notifica a {telegram_id}: {response.status_code} - {response.text}")
        
            return successful_sends
                
        except Exception as e:
            print(f"Errore nell'invio della notifica: {e}")
            import traceback
            traceback.print_exc()
            return 0
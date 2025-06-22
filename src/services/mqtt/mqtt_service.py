import paho.mqtt.client as mqtt
import ssl
import threading
import time
from datetime import datetime
from asyncio import run_coroutine_threadsafe
from flask import current_app
from src.application.bot.notifications import send_alert_to_user

BROKER_URL = "f1d601b5c9184556910bdc2b4e6dfe17.s1.eu.hivemq.cloud"
BROKER_PORT = 8883
MQTT_USERNAME = "test0"
MQTT_PASSWORD = "Prova12345"



# --- Funzione di utilità per inviare messaggi MQTT ---
def send_mqtt_message(message: str, topic: str = "all_devices/led_states"):
    """Funzione helper per inviare un singolo messaggio MQTT."""
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

        print(f"MQTT Sender: Tentativo invio '{payload}' su topic '{topic}'...")
        result = client.publish(topic, payload)
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
        
    def on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8').strip()
            
            # Estrai l'ID del dispositivo dal topic (formato: id_dispositivo/taken)
            device_id = topic.split('/')[0]
            print(f"MQTT: Ricevuto '{payload}' sul topic '{topic}', ID dispositivo: {device_id}")
            
            # Accedi al contesto dell'app solo se disponibile
            if self.app and payload == "1":
                with self.app.app_context():
                    # Accedi a current_app solo all'interno del contesto
                    if "TELEGRAM_LOOP" in current_app.config:
                        loop = current_app.config["TELEGRAM_LOOP"]
                        if loop and loop.is_running():
                            # Decommentare se necessario inviare l'alerta
                            run_coroutine_threadsafe(
                                send_alert_to_user(157933243, "poba", 666.0),
                                loop)
                    
                    # Aggiorna la regolarità all'interno del contesto dell'app
                    self._update_regularity(device_id)
            elif payload == "1":
                # Caso in cui non è disponibile l'app ma dobbiamo comunque aggiornare la regolarità
                self._update_regularity(device_id)
                
        except Exception as e:
            print(f"MQTT Subscriber: Errore nell'elaborazione del messaggio: {e}")

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to the MQTT broker"""
        if rc == 0:
            print(f"MQTT Subscriber: Connesso al broker {self.broker_url}")
            # Sottoscrivi a tutti i topic che terminano con /taken
            client.subscribe("+/taken")
            print("MQTT Subscriber: Sottoscritto ai topic */taken")
        else:
            print(f"MQTT Subscriber: Fallita connessione al broker, codice {rc}")


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
                # Se esiste già un entry per oggi, aggiungi l'orario attuale
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
                {"$set": {"data.regularity": regularity}}
            )
            
            print(f"MQTT Subscriber: Aggiornata regolarità per {device_id}: {current_date} {current_time}")
        except Exception as e:
            print(f"MQTT Subscriber: Errore nell'aggiornamento della regolarità: {e}")

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
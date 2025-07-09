import paho.mqtt.client as mqtt
import ssl
import threading
import time
import json
from datetime import datetime
import json
from config.settings import (
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    MQTT_TOPIC_TAKEN, MQTT_TOPIC_DOOR, MQTT_TOPIC_EMERGENCY,
    MQTT_TOPIC_ENVIRONMENTAL, MQTT_TOPIC_ASSOC
)

BROKER_URL = MQTT_BROKER
BROKER_PORT = MQTT_PORT
MQTT_USERNAME = MQTT_USERNAME
MQTT_PASSWORD = MQTT_PASSWORD



# --- Funzione di utilità per inviare messaggi MQTT ---
def send_mqtt_message(message: str, topic: str, qos: int = 2):
    """
    Funzione helper per inviare un singolo messaggio MQTT.
    
    Args:
        message: Messaggio da inviare
        topic: Topic su cui pubblicare
        qos: Quality of Service (0, 1 o 2), default 2 (exactly once)
    
    Returns:
        bool: True se l'invio è avvenuto con successo, False altrimenti
    """
    import paho.mqtt.client as mqtt
    import ssl
    from config.settings import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    
    try:
        print(f"MQTT: Connessione a {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        print(f"MQTT: Invio messaggio '{message}' su '{topic}'")
        result = client.publish(topic, message, qos=qos)
        result.wait_for_publish(timeout=5)
        
        success = result.is_published()
        if success:
            print(f"MQTT: Messaggio inviato con successo")
        else:
            print(f"MQTT: Invio fallito o timeout")
        
        return success
    except Exception as e:
        print(f"MQTT: Errore di connessione/invio: {repr(e)}")
        return False
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except:
            pass



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

            
            # Gestione eventi porta con delega al servizio
            if topic_suffix == MQTT_TOPIC_DOOR:
                # Trova i DT collegati a questo dispositivo
                dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", device_id)
                
                # Cerca un DT che abbia il servizio porta
                door_service = None
                for dt_id in dts_with_dispenser:
                    dt_instance = self.dt_factory.get_dt_instance(dt_id)
                    if dt_instance:
                        door_service = dt_instance.get_service("DoorEventService")
                        if door_service:
                            break
                            
                # Se abbiamo trovato un servizio, lo utilizziamo
                if door_service:
                    door_service.handle_door_status_update(
                        self.db_service,
                        self.dt_factory,
                        device_id,
                        payload
                    )
            
            elif topic_suffix == MQTT_TOPIC_EMERGENCY:
                if payload == "1":
                    print(f"🚨 EMERGENZA rilevata dal dispositivo: {device_id}")
                    self._handle_emergency_request(device_id)
                else:
                    print(f"MQTT Subscriber: Payload non valido per emergenza: '{payload}'")
    
            elif topic_suffix == MQTT_TOPIC_ENVIRONMENTAL:
                try:
                    env_data = json.loads(payload)

                    # Trova tutti i DT collegati a questo dispositivo
                    dts_with_dispenser = self._find_dts_with_dr("dispenser_medicine", device_id)

                    # Cerca un DT che abbia il servizio ambientale
                    env_service = None
                    for dt_id in dts_with_dispenser:
                        dt_instance = self.dt_factory.get_dt_instance(dt_id)
                        if dt_instance:
                            env_service = dt_instance.get_service("EnvironmentalMonitoringService")
                            if env_service:
                                break
                                
                    # Se abbiamo trovato un servizio, lo utilizziamo
                    if env_service:
                        env_service.handle_environmental_data(
                            self.db_service, 
                            self.dt_factory, 
                            device_id, 
                            env_data
                        )
                    else:
                        print(f"MQTT: Nessun servizio ambientale trovato per il dispositivo {device_id}")
                except json.JSONDecodeError:
                    print(f"MQTT Subscriber: Payload dati ambientali non valido (non è JSON): '{payload}'")
        except Exception as e:
            print(f"MQTT Subscriber: Errore nella gestione del messaggio: {e}")


    

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
                            # Passa sia db_service che dt_factory
                            emergency_service.db_service = self.db_service
                            emergency_service.dt_factory = self.dt_factory  # Aggiungi questa riga
                            emergency_service.execute(device_id, dt_id, dt_name)
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
            # Query diretta più semplice con il campo corretto
            collection = self.db_service.db["digital_twins"]
            query = {"digital_replicas": {"$elemMatch": {"id": dr_id, "type": dr_type}}}
            matching_dts = []
            
            for dt in collection.find(query):
                matching_dts.append(str(dt.get("_id")))
            
            print(f"DEBUG: Trovati {len(matching_dts)} DT con {dr_type}={dr_id}: {matching_dts}")
            return matching_dts
            
        except Exception as e:
            print(f"Errore nella ricerca dei DT con DR {dr_id}: {e}")
            import traceback
            traceback.print_exc()
            return []
            
    
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
                        
                        # Verifica irregolarità direttamente dal servizio ambientale
                        env_service = dt_instance.get_service("EnvironmentalMonitoringService")
                        if env_service:
                            # Verifica delle irregolarità ambientali
                            dt_data = dt_instance.get_dt_data()
                            env_alerts = env_service.check_environmental_irregularities(
                                dt_data, temp_range=(env_service.temperature_range[0], env_service.temperature_range[1])
                            )
                            
                            # Se ci sono alert ambientali, gestiamoli qui
                            if env_alerts:
                                print(f"Rilevate {len(env_alerts)} irregolarità ambientali per DT {dt_id}")
                
                except Exception as e:
                    print(f"Errore nell'aggiornamento dei servizi del DT {dt_id}: {e}")
                
        except Exception as e:
            print(f"Errore generale nell'aggiornamento dei servizi DT: {e}")
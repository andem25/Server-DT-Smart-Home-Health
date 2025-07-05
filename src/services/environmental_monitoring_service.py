from src.services.base import BaseService
from datetime import datetime, timedelta

class EnvironmentalMonitoringService(BaseService):
    """
    Servizio per il monitoraggio ambientale (FR-7)
    """
    
    def __init__(self):
        self.name = "EnvironmentalMonitoringService"
        self.alerts = []
        
    def configure(self, config):
        """Configurazione del servizio"""
        self.temperature_range = config.get("temperature_range", [18, 30])
        self.humidity_range = config.get("humidity_range", [30, 70])
        self.air_quality_threshold = config.get("air_quality_threshold", 50)
        self.db_service = None
        return self
        
    def execute(self, dt_data, **kwargs):
        """
        Verifica condizioni ambientali per tutti i dispositivi collegati
        """
        if 'db_service' in kwargs:
            self.db_service = kwargs['db_service']
            
        results = {
            "temperature_alerts": [],
            "humidity_alerts": [],
            "air_quality_alerts": []
        }
        
        # Ottieni tutti i dispositivi dal Digital Twin
        dispensers = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "dispenser_medicine"]
        
        for dispenser in dispensers:
            dispenser_id = dispenser.get("id")
            
            # Ottieni il dispositivo dal database per accedere ai dati ambientali
            if self.db_service:
                dr = self.db_service.get_dr("dispenser_medicine", dispenser_id)
                if dr:
                    # Verifica se ci sono dati ambientali
                    env_data = dr.get("data", {}).get("environmental_data", [])
                    
                    # Analizza i dati più recenti
                    self._analyze_environmental_data(dr, env_data, results)
                    
        return results
    
    def process_measurement(self, device_id, measurement):
        """
        Elabora una nuova misura e verifica se è necessario attivare un allarme
        
        Args:
            device_id (str): ID del dispositivo
            measurement (dict): Dati della misurazione
        """
        measure_type = measurement.get("type")
        value = measurement.get("value")
        
        if measure_type == "temperature":
            min_temp, max_temp = self.temperature_range
            if value < min_temp or value > max_temp:
                return {
                    "type": "temperature_alert",
                    "device_id": device_id,
                    "value": value,
                    "min": min_temp,
                    "max": max_temp,
                    "timestamp": datetime.now()
                }
                
        elif measure_type == "humidity":
            min_hum, max_hum = self.humidity_range
            if value < min_hum or value > max_hum:
                return {
                    "type": "humidity_alert",
                    "device_id": device_id,
                    "value": value,
                    "min": min_hum,
                    "max": max_hum,
                    "timestamp": datetime.now()
                }
                
        return None
    
    def _analyze_environmental_data(self, dispenser, env_data, results):
        """
        Analizza i dati ambientali di un dispenser
        
        Args:
            dispenser (dict): Dati del dispenser
            env_data (list): Lista di misurazioni ambientali
            results (dict): Dizionario dei risultati da aggiornare
        """
        dispenser_id = dispenser.get("_id")
        dispenser_name = dispenser.get("data", {}).get("name", "Dispenser sconosciuto")
        
        # Ottieni i limiti personalizzati, se disponibili
        custom_temp_limits = dispenser.get("data", {}).get("temperature_limits")
        custom_humidity_limits = dispenser.get("data", {}).get("humidity_limits")
        
        # Usa i limiti personalizzati o quelli predefiniti
        min_temp, max_temp = custom_temp_limits if custom_temp_limits else self.temperature_range
        min_hum, max_hum = custom_humidity_limits if custom_humidity_limits else self.humidity_range
        
        # Ottieni le misure più recenti di ogni tipo
        latest_temp = None
        latest_humidity = None
        
        for measure in reversed(env_data):
            if measure.get("type") == "temperature" and latest_temp is None:
                latest_temp = measure
            elif measure.get("type") == "humidity" and latest_humidity is None:
                latest_humidity = measure
                
            if latest_temp and latest_humidity:
                break
                
        # Verifica temperatura
        if latest_temp:
            temp_value = latest_temp.get("value")
            
            if temp_value < min_temp:
                results["temperature_alerts"].append({
                    "type": "low_temperature",
                    "dispenser_id": dispenser_id,
                    "dispenser_name": dispenser_name,
                    "value": temp_value,
                    "unit": latest_temp.get("unit", "°C"),
                    "min": min_temp,
                    "max": max_temp,
                    "timestamp": latest_temp.get("timestamp")
                })
            elif temp_value > max_temp:
                results["temperature_alerts"].append({
                    "type": "high_temperature",
                    "dispenser_id": dispenser_id,
                    "dispenser_name": dispenser_name,
                    "value": temp_value,
                    "unit": latest_temp.get("unit", "°C"),
                    "min": min_temp,
                    "max": max_temp,
                    "timestamp": latest_temp.get("timestamp")
                })
                
        # Verifica umidità
        if latest_humidity:
            humidity_value = latest_humidity.get("value")
            
            if humidity_value < min_hum:
                results["humidity_alerts"].append({
                    "type": "low_humidity",
                    "dispenser_id": dispenser_id,
                    "dispenser_name": dispenser_name,
                    "value": humidity_value,
                    "unit": latest_humidity.get("unit", "%"),
                    "min": min_hum,
                    "max": max_hum,
                    "timestamp": latest_humidity.get("timestamp")
                })
            elif humidity_value > max_hum:
                results["humidity_alerts"].append({
                    "type": "high_humidity",
                    "dispenser_id": dispenser_id,
                    "dispenser_name": dispenser_name,
                    "value": humidity_value,
                    "unit": latest_humidity.get("unit", "%"),
                    "min": min_hum,
                    "max": max_hum,
                    "timestamp": latest_humidity.get("timestamp")
                })
    
    def handle_environmental_data(self, db_service, dt_factory, device_id, env_data):
        """
        Gestisce i dati ambientali combinati ricevuti via MQTT
        
        Args:
            db_service: Servizio database per accedere ai dati
            dt_factory: Factory per accedere ai Digital Twin
            device_id (str): ID univoco del dispositivo
            env_data (dict): Dizionario con temperatura, umidità e timestamp
        """
        try:
            # Estrai i dati dal payload
            temperature = env_data.get("avg_temperature")
            humidity = env_data.get("avg_humidity")
            time_str = env_data.get("time")
            
            if temperature is None or humidity is None:
                print(f"EnvironmentalMonitoringService: Dati ambientali incompleti per {device_id}")
                return
            
            # Valori soglia predefiniti - usiamo quelli configurati nel servizio
            MIN_TEMP, MAX_TEMP = self.temperature_range
            MIN_HUMIDITY, MAX_HUMIDITY = self.humidity_range
            MAX_MEASUREMENTS = 1000
            
            # Ottieni il dispenser dal database
            dispenser = db_service.get_dr("dispenser_medicine", device_id)
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
            db_service.update_dr("dispenser_medicine", device_id, update_operation)
            
            print(f"Dati ambientali aggiornati per {device_id}: Temperatura: {temperature}°C, Umidità: {humidity}%")
            
            # Importa la funzione per inviare notifiche
            from src.application.bot.notifications import send_environmental_alert
            
            # Invia notifiche se necessario
            if temp_out_of_range:
                send_environmental_alert(db_service, dt_factory, device_id, "temperatura", temperature, "°C", MIN_TEMP, MAX_TEMP)
                
            if humidity_out_of_range:
                send_environmental_alert(db_service, dt_factory, device_id, "umidità", humidity, "%", MIN_HUMIDITY, MAX_HUMIDITY)
                
            # Notifica eventuali Digital Twin associati
            # Aggiorniamo entrambe le misure
            self.process_measurement(device_id, new_temp_measurement)
            self.process_measurement(device_id, new_humidity_measurement)
            
            # Trova e aggiorna i DT associati
            if dt_factory:
                # Trova tutti i DT collegati a questo dispositivo
                dts_with_dispenser = []
                all_dts = db_service.query_drs("digital_twins", {})
                
                for dt in all_dts:
                    dt_id = str(dt.get("_id"))
                    dt_instance = dt_factory.get_dt_instance(dt_id)
                    
                    if dt_instance and dt_instance.contains_dr("dispenser_medicine", device_id):
                        dts_with_dispenser.append(dt_id)
                
                # Notifica i servizi nei DT
                for dt_id in dts_with_dispenser:
                    try:
                        dt_instance = dt_factory.get_dt_instance(dt_id)
                        if dt_instance:
                            # Verifica servizio di irregolarità che potrebbe usare i dati ambientali
                            irreg_service = dt_instance.get_service("IrregularityAlertService")
                            if irreg_service:
                                # Verifica delle irregolarità
                                dt_data = dt_instance.get_dt_data()
                                alerts = irreg_service.execute(dt_data)
                                
                                if alerts.get("environmental_alerts"):
                                    print(f"Rilevate irregolarità ambientali per DT {dt_id}")
                    except Exception as e:
                        print(f"Errore nell'aggiornamento dei servizi del DT {dt_id}: {e}")
        
        except Exception as e:
            print(f"Errore nella gestione dei dati ambientali: {e}")
            import traceback
            traceback.print_exc()
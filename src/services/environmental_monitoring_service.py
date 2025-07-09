from src.services.base import BaseService
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

class EnvironmentalMonitoringService(BaseService):
    """
    Servizio per il monitoraggio ambientale (FR-7)
    """
    
    def __init__(self):
        super().__init__()
        self.name = "EnvironmentalMonitoringService"
        self.alerts = []
        self.temperature_range = [18, 30]
        self.humidity_range = [30, 70]
        self.air_quality_threshold = 50
        
    def configure(self, config):
        """Configurazione del servizio"""
        self.temperature_range = config.get("temperature_range", [18, 30])
        self.humidity_range = config.get("humidity_range", [30, 70])
        self.air_quality_threshold = config.get("air_quality_threshold", 50)
        return self
    
    def execute(self, dt_data, **kwargs):
        """
        Verifica condizioni ambientali per tutti i dispositivi collegati
        Metodo mantenuto per retrocompatibilità
        """
        if 'dt_instance' in kwargs:
            return kwargs['dt_instance'].execute_environmental_monitoring()
            
        
    
    # Implementazione dei metodi dell'interfaccia
    def process_measurement(self, device_id: str, measurement: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Elabora una nuova misura e verifica se è necessario attivare un allarme
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
        
    def check_environmental_irregularities(self, dt_data: Dict[str, Any], 
                                         temp_range: Optional[Tuple[float, float]] = None) -> List[Dict[str, Any]]:
        """Verifica le condizioni ambientali"""
        alerts = []
        
        # Se non viene fornito un range, usa i valori di default del servizio
        min_temp, max_temp = temp_range if temp_range else (self.temperature_range[0], self.temperature_range[1])
        
        # Cerca sia sensori dedicati che dispenser con sensori integrati
        env_sensors = []
        
        for dr in dt_data.get("digital_replicas", []):
            if dr.get("type") == "environmental_sensor":
                env_sensors.append(dr)
            elif dr.get("type") == "dispenser_medicine" and dr.get("data", {}).get("environmental_data"):
                env_sensors.append(dr)
        
        for sensor in env_sensors:
            # Ottieni le misurazioni
            measures = []
            if sensor.get("type") == "environmental_sensor":
                measures = sensor.get("data", {}).get("measures", [])
            else:  # dispenser
                measures = sensor.get("data", {}).get("environmental_data", [])
                
            if not measures:
                continue
                
            # Trova l'ultima misura di temperatura
            temp_measures = [m for m in measures if m.get("type") == "temperature"]
            if temp_measures:
                latest_temp = sorted(temp_measures, key=lambda x: x.get("timestamp"), reverse=True)[0]
                temp_value = latest_temp.get("value")
                
                if temp_value < min_temp:
                    alerts.append({
                        "type": "low_temperature",
                        "sensor_id": sensor.get("_id"),
                        "location": sensor.get("data", {}).get("location", "sconosciuta"),
                        "value": temp_value,
                        "unit": latest_temp.get("unit", "°C"),
                        "severity": "medium",
                        "timestamp": datetime.now()
                    })
                elif temp_value > max_temp:
                    alerts.append({
                        "type": "high_temperature",
                        "sensor_id": sensor.get("_id"),
                        "location": sensor.get("data", {}).get("location", "sconosciuta"),
                        "value": temp_value,
                        "unit": latest_temp.get("unit", "°C"),
                        "severity": "medium",
                        "timestamp": datetime.now()
                    })
        
        return alerts
        
    def get_environmental_limits(self, device_id: str) -> Dict[str, Tuple[float, float]]:
        """
        Ottiene i limiti ambientali configurati per un dispositivo
        """
        # Valori predefiniti
        limits = {
            "temperature": tuple(self.temperature_range),
            "humidity": tuple(self.humidity_range)
        }
        
        # Se abbiamo accesso al database, ottieni limiti personalizzati
        if hasattr(self, 'db_service') and self.db_service:
            try:
                device = self.db_service.get_dr("dispenser_medicine", device_id)
                if device:
                    # Ottieni i limiti personalizzati, se disponibili
                    custom_temp_limits = device.get("data", {}).get("temperature_limits")
                    if custom_temp_limits and len(custom_temp_limits) == 2:
                        limits["temperature"] = tuple(custom_temp_limits)
                        
                    custom_humidity_limits = device.get("data", {}).get("humidity_limits")
                    if custom_humidity_limits and len(custom_humidity_limits) == 2:
                        limits["humidity"] = tuple(custom_humidity_limits)
            except Exception as e:
                print(f"Errore nel recupero dei limiti ambientali: {e}")
                
        return limits

    def handle_environmental_data(self, db_service, dt_factory, device_id, env_data):
        """
        Gestisce i dati ambientali ricevuti da MQTT, estraendo temperatura e umidità.
        """
        print(f"Received environmental data for device {device_id}: {env_data}")

        # Lista per contenere le nuove misurazioni formattate
        measurements_to_push = []
        # Usiamo un timestamp unico per questo "pacchetto" di dati
        timestamp = datetime.now().isoformat()

        # 1. Estrai e formatta la misurazione della temperatura
        if "avg_temperature" in env_data:
            temp_measurement = {
                "type": "temperature",
                "value": env_data["avg_temperature"],
                "unit": "°C",
                "timestamp": timestamp
            }
            measurements_to_push.append(temp_measurement)

        # 2. Estrai e formatta la misurazione dell'umidità
        if "avg_humidity" in env_data:
            humidity_measurement = {
                "type": "humidity",
                "value": env_data["avg_humidity"],
                "unit": "%",
                "timestamp": timestamp
            }
            measurements_to_push.append(humidity_measurement)

        # Se non abbiamo estratto dati validi, interrompiamo l'esecuzione
        if not measurements_to_push:
            print(f"Warning: No valid measurements found in data from device {device_id}: {env_data}")
            return

        # 3. Prepara l'operazione di aggiornamento per il database
        # Usiamo $each per aggiungere tutti gli elementi della lista in una sola operazione
        update_operation = {
            "$push": {
                "data.environmental_data": {
                    "$each": measurements_to_push
                }
            }
        }

        # 4. Aggiorna il documento del dispenser nel database
        db_service.update_dr("dispenser_medicine", device_id, update_operation)
        print(f"Successfully updated device {device_id} with data: {measurements_to_push}")


    def set_environmental_limits(self, device_id: str, 
                               limit_type: str, 
                               min_value: float, 
                               max_value: float) -> bool:
        """
        Imposta nuovi limiti ambientali per un dispositivo
        """
        if min_value >= max_value:
            return False
            
        # Verifica che i valori rientrino in range ragionevoli
        if limit_type == "temperature":
            if min_value < -10 or max_value > 50:
                return False
        elif limit_type == "humidity":
            if min_value < 0 or min_value > 100 or max_value < 0 or max_value > 100:
                return False
        else:
            return False
            
        # Se abbiamo accesso al database, aggiorna i limiti
        if hasattr(self, 'db_service') and self.db_service:
            try:
                update_field = "temperature_limits" if limit_type == "temperature" else "humidity_limits"
                
                # Aggiorna il dispenser
                update_operation = {
                    "$set": {
                        f"data.{update_field}": [min_value, max_value],
                        "metadata.updated_at": datetime.now().isoformat()
                    }
                }
                
                self.db_service.update_dr("dispenser_medicine", device_id, update_operation)
                return True
            except Exception as e:
                print(f"Errore nell'aggiornamento dei limiti ambientali: {e}")
                return False
        
        return False
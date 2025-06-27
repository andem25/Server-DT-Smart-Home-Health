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
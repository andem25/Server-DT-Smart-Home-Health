from src.services.base import BaseService
from datetime import datetime, timedelta

class IrregularityAlertService(BaseService):
    """Servizio per il rilevamento di irregolarità per FR-5"""
    
    def __init__(self):
        self.name = "IrregularityAlertService"
        self.alerts = []
    
    def configure(self, config):
        self.missed_doses_threshold = config.get("missed_doses_threshold", 2)
        self.door_open_alert_time = config.get("door_open_alert_time", 30)  # minuti
        self.env_min_temperature = config.get("min_temperature", 18)
        self.env_max_temperature = config.get("max_temperature", 30)
        return self
    
    def execute(self, dt_data, **kwargs):
        """Controlla tutti i possibili pattern di irregolarità"""
        alert_results = {
            "medication_alerts": self._check_medication_adherence(dt_data),
            "door_alerts": self._check_door_status(dt_data),
            "environmental_alerts": self._check_environmental_conditions(dt_data)
        }
        
        return alert_results
    
    def _check_medication_adherence(self, dt_data):
        """Verifica l'aderenza ai farmaci"""
        alerts = []
        dispensers = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "dispenser_medicine"]
        
        for dispenser in dispensers:
            dispenser_name = dispenser.get("data", {}).get("name", "medicinale")
            regularity = dispenser.get("data", {}).get("regularity", [])
            
            # Controlla se negli ultimi giorni ci sono state assunzioni mancate
            # Questo è un esempio semplificato - in un sistema reale si userebbe
            # una logica più sofisticata basata sull'intervallo e lo storico
            today = datetime.now().date()
            missing_days = 0
            
            for i in range(1, 4):  # controlla gli ultimi 3 giorni
                check_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                day_entries = [r for r in regularity if r.get("date") == check_date]
                if not day_entries:
                    missing_days += 1
            
            if missing_days >= self.missed_doses_threshold:
                alerts.append({
                    "type": "missed_medication",
                    "dispenser_id": dispenser.get("_id"),
                    "dispenser_name": dispenser_name,
                    "missing_days": missing_days,
                    "severity": "high" if missing_days >= 3 else "medium",
                    "timestamp": datetime.now()
                })
                
        return alerts
    
    def _check_door_status(self, dt_data):
        """Verifica se ci sono porte rimaste aperte troppo a lungo"""
        alerts = []
        doors = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "door_sensor"]
        
        for door in doors:
            status = door.get("data", {}).get("status")
            last_change = door.get("data", {}).get("last_change")
            
            if status == "open" and last_change:
                # Calcola quanto tempo è rimasta aperta la porta
                last_change_dt = last_change if isinstance(last_change, datetime) else datetime.fromisoformat(last_change)
                minutes_open = (datetime.now() - last_change_dt).total_seconds() / 60
                
                if minutes_open > self.door_open_alert_time:
                    alerts.append({
                        "type": "door_open_too_long",
                        "door_id": door.get("_id"),
                        "door_name": door.get("data", {}).get("name", "porta"),
                        "location": door.get("data", {}).get("location", "sconosciuta"),
                        "minutes_open": round(minutes_open),
                        "severity": "medium",
                        "timestamp": datetime.now()
                    })
        
        return alerts
    
    def _check_environmental_conditions(self, dt_data):
        """Verifica le condizioni ambientali"""
        alerts = []
        env_sensors = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "environmental_sensor"]
        
        for sensor in env_sensors:
            measures = sensor.get("data", {}).get("measures", [])
            if not measures:
                continue
                
            # Trova l'ultima misura di temperatura
            temp_measures = [m for m in measures if m.get("type") == "temperature"]
            if not temp_measures:
                continue
                
            latest_temp = sorted(temp_measures, key=lambda x: x.get("timestamp"), reverse=True)[0]
            temp_value = latest_temp.get("value")
            
            if temp_value < self.env_min_temperature:
                alerts.append({
                    "type": "low_temperature",
                    "sensor_id": sensor.get("_id"),
                    "location": sensor.get("data", {}).get("location", "sconosciuta"),
                    "value": temp_value,
                    "unit": latest_temp.get("unit", "°C"),
                    "severity": "medium",
                    "timestamp": datetime.now()
                })
            elif temp_value > self.env_max_temperature:
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
from typing import Dict, List, Type, Any
from src.services.base import BaseService
from datetime import datetime


class DigitalTwin:
    """Core Digital Twin class that manages DRs and services"""

    def __init__(self):
        self.digital_replicas: List = []  # Lista di DR objects
        self.active_services: Dict = {}  # service_name -> service_instance

    def add_digital_replica(self, dr_instance: Any) -> None:
        """Aggiunge una Digital Replica al twin"""
        self.digital_replicas.append(dr_instance)

    def add_service(self, service):
        """Add a service to the DT"""
        if isinstance(service, type):
            # If a class is passed, instantiate it
            service = service()
        self.active_services[service.name] = service

    def list_services(self):
        """List all services"""
        return list(self.active_services.keys())

    def get_service(self, service_name: str):
        """Get a service by name"""
        return self.active_services.get(service_name)

    def remove_service(self, service_name: str) -> None:
        """Rimuove un servizio attivo"""
        if service_name in self.active_services:
            del self.active_services[service_name]

    def get_dt_data(self):
        """Get all DT data including DRs"""
        return {"digital_replicas": self.digital_replicas}

    def execute_service(self, service_name: str, **kwargs):
        """Execute a named service with parameters"""
        if service_name not in self.active_services:
            raise ValueError(f"Service {service_name} not found")

        service = self.active_services[service_name]

        # Prepare data for service
        data = {"digital_replicas": self.digital_replicas}

        # Execute service with data and additional parameters
        return service.execute(data, **kwargs)

    def contains_dr(self, dr_type: str, dr_id: str) -> bool:
        """
        Verifica se il Digital Twin contiene una specifica Digital Replica.

        Args:
            dr_type (str): Tipo della Digital Replica
            dr_id (str): ID della Digital Replica

        Returns:
            bool: True se la Digital Replica è contenuta nel Digital Twin, False altrimenti
        """
        dt_data = self._dt_data
        for dr in dt_data.get("digital_replicas", []):
            if dr.get("type") == dr_type and dr.get("id") == dr_id:
                return True
        return False

    def execute_medication_reminders(self):
        """Esegue i promemoria medicinali orchestrando il servizio"""

        # Ottieni il servizio
        reminder_service = self.get_service("MedicationReminderService")
        if not reminder_service:
            return {"error": "Servizio non disponibile"}

        results = {
            "promemoria_verificati": 0,
            "promemoria_inviati": 0
        }

        # Per ogni dispenser nel DT
        for dispenser in self.get_replicas_by_type("dispenser_medicine"):
            # Il DT fornisce i dati al servizio
            results["promemoria_verificati"] += 1

            # Verifica se è necessario un promemoria
            if reminder_service.check_reminders(dispenser):
                # Il DT fornisce anche il canale di notifica
                notification_sent = reminder_service.send_reminder(
                    dispenser,
                    notification_channel=self.send_notification
                )

                if notification_sent:
                    results["promemoria_inviati"] += 1

                    # Il DT aggiorna i propri dati
                    self._update_reminder_status(dispenser["_id"])

        return results

    def send_notification(self, target_id, message, channel="mqtt"):
        """Metodo del DT per inviare notifiche"""
        # Implementazione centralizzata nel DT
        from src.application.mqtt import send_mqtt_message

        topic = f"{target_id}/notification"
        return send_mqtt_message(message, topic)

    def _update_reminder_status(self, dispenser_id):
        """Aggiorna lo stato del promemoria nel dispenser"""
        from datetime import datetime

        for idx, replica in enumerate(self.digital_replicas):
            if replica.get("type") == "dispenser_medicine" and replica.get("_id") == dispenser_id:
                if "data" not in replica:
                    replica["data"] = {}

                # Aggiorna il timestamp dell'ultimo promemoria
                replica["data"]["last_reminder_sent"] = datetime.now().isoformat()

                # Se c'è un db_service disponibile, persisti la modifica
                if hasattr(self, 'db_service') and self.db_service:
                    self.db_service.update_dr("dispenser_medicine", dispenser_id, {
                        "$set": {"data.last_reminder_sent": replica["data"]["last_reminder_sent"]}
                    })

                return True

        return False

    def execute_environmental_monitoring(self):
        """Esegue il monitoraggio ambientale orchestrando il servizio"""

        # Ottieni il servizio
        env_service = self.get_service("EnvironmentalMonitoringService")
        if not env_service:
            return {"error": "Servizio non disponibile"}

        results = {
            "temperature_alerts": [],
            "humidity_alerts": [],
            "air_quality_alerts": []
        }

        # Per ogni dispositivo ambientale nel DT
        for device in self.get_replicas_by_type("dispenser_medicine"):
            # Il DT fornisce i dati al servizio
            device_id = device.get("_id")
            device_data = device

            # Verifica i limiti ambientali per questo dispositivo
            limits = env_service.get_environmental_limits(device_id)

            # Verifica irregolarità ambientali
            alerts = env_service.check_environmental_irregularities(
                {"digital_replicas": [device]},
                temp_range=limits.get("temperature")
            )

            # Se ci sono alert, il DT decide come gestirli
            for alert in alerts:
                alert_type = alert.get("type", "")

                if "temperature" in alert_type:
                    results["temperature_alerts"].append(alert)
                    if hasattr(self, 'send_notification'):
                        self._handle_temperature_alert(alert)

                elif "humidity" in alert_type:
                    results["humidity_alerts"].append(alert)
                    if hasattr(self, 'send_notification'):
                        self._handle_humidity_alert(alert)

        return results

    def _handle_temperature_alert(self, alert):
        """Gestisce un allarme di temperatura"""
        device_id = alert.get("sensor_id") or alert.get("dispenser_id")
        value = alert.get("value", "N/A")
        message = f"Allarme temperatura: {value}°C"

        # Il DT gestisce direttamente l'invio della notifica
        self.send_notification(device_id, message, "environmental")

    def _handle_humidity_alert(self, alert):
        """Gestisce un allarme di umidità"""
        device_id = alert.get("sensor_id") or alert.get("dispenser_id")
        value = alert.get("value", "N/A")
        message = f"Allarme umidità: {value}%"

        # Il DT gestisce direttamente l'invio della notifica
        self.send_notification(device_id, message, "environmental")

    def execute_door_monitoring(self, threshold_minutes=1):
        """Esegue il monitoraggio delle porte orchestrando il servizio"""

        # Ottieni il servizio
        door_service = self.get_service("DoorEventService")
        if not door_service:
            return {"error": "Servizio non disponibile"}

        results = {
            "door_alerts": []
        }

        # Per ogni dispenser nel DT
        for dispenser in self.get_replicas_by_type("dispenser_medicine"):
            # Il DT fornisce i dati al servizio
            alerts = door_service.check_door_alerts(dispenser, threshold_minutes)

            # Aggiungi eventuali alert rilevati
            if alerts:
                for alert in alerts:
                    results["door_alerts"].append(alert)
                    # Il DT gestisce direttamente la notifica
                    self._handle_door_alert(alert)

        return results

    def _handle_door_alert(self, alert):
        """Gestisce un allarme relativo alla porta"""
        device_id = alert.get("dispenser_id")
        minutes = alert.get("minutes_open", 0)
        
        # Invia notifica Telegram agli utenti
        door_service = self.get_service("DoorEventService")
        if door_service and hasattr(door_service, 'db_service') and hasattr(door_service, 'dt_factory'):
            from src.application.bot.notifications import send_door_open_alert
            send_door_open_alert(door_service.db_service, door_service.dt_factory, device_id, minutes)

    def get_replicas_by_type(self, dr_type):
        """Ottiene tutte le Digital Replica di un certo tipo"""
        return [dr for dr in self.digital_replicas if dr.get("type") == dr_type]

    def execute_emergency_request(self, device_id, timestamp=None):
        """Gestisce una richiesta di emergenza orchestrando il servizio"""

        # Ottieni il servizio
        emergency_service = self.get_service("EmergencyRequestService")
        if not emergency_service:
            return {"error": "Servizio di emergenza non disponibile"}

        if timestamp is None:
            timestamp = datetime.now()

        # Ottieni le informazioni necessarie dal DT
        dt_id = self.id
        dt_name = self.name

        # Ottieni informazioni sul dispositivo
        device = None
        for replica in self.digital_replicas:
            if replica.get("type") == "dispenser_medicine" and replica.get("_id") == device_id:
                device = replica
                break

        if not device:
            return {"error": f"Dispositivo {device_id} non trovato in questo Digital Twin"}

        # Il DT gestisce l'aggiornamento dello stato di emergenza del dispositivo
        self._update_device_emergency_status(device_id, True, timestamp)

        # Il DT delega l'invio delle notifiche al servizio
        notifications_sent = emergency_service.handle_emergency_notification(
            device_id,
            dt_id,
            dt_name
        )

        # Log dell'evento
        print(f"[DT] Gestita richiesta di emergenza da {device_id} (DT: {dt_name}) alle {timestamp.strftime('%H:%M:%S')}")

        return {
            "device_id": device_id,
            "dt_id": dt_id,
            "timestamp": timestamp.isoformat(),
            "notifications_sent": notifications_sent
        }

    def _update_device_emergency_status(self, device_id, is_active, timestamp):
        """Aggiorna lo stato di emergenza del dispositivo"""
        # Aggiorna la replica locale
        for idx, replica in enumerate(self.digital_replicas):
            if replica.get("_id") == device_id and replica.get("type") == "dispenser_medicine":
                if "data" not in replica:
                    replica["data"] = {}

                # Aggiorna i dati di emergenza
                replica["data"]["emergency_active"] = is_active
                replica["data"]["last_emergency_request"] = timestamp.isoformat()

                # Aggiungi l'evento alla lista degli eventi di emergenza
                if "emergency_requests" not in replica["data"]:
                    replica["data"]["emergency_requests"] = []

                replica["data"]["emergency_requests"].append({
                    "timestamp": timestamp.isoformat(),
                    "status": "active",
                    "resolved_at": None
                })

                # Persisti le modifiche nel DB se possibile
                if hasattr(self, 'db_service') and self.db_service:
                    update_operation = {
                        "$push": {
                            "data.emergency_requests": {
                                "timestamp": timestamp.isoformat(),
                                "status": "active",
                                "resolved_at": None
                            }
                        },
                        "$set": {
                            "data.emergency_active": is_active,
                            "data.last_emergency_request": timestamp.isoformat()
                        }
                        
                    }
                    self.db_service.update_dr("dispenser_medicine", device_id, update_operation)
                return True
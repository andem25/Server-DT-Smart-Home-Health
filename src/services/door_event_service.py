from datetime import datetime
from src.services.base import BaseService

class DoorEventService(BaseService):
    """
    Servizio che monitora eventi di apertura/chiusura delle porte (FR-2)
    """
    
    def __init__(self):
        self.name = "DoorEventService"
        self.last_state = {}
        
    def configure(self, config):
        self.notification_threshold = config.get('notification_threshold', 30)  # secondi
        self.db_service = None  # Sarà impostato durante l'esecuzione
        return self
        
    def execute(self, dt_data, **kwargs):
        """Verifica lo stato delle porte e invia notifiche se necessario"""
        if 'db_service' in kwargs:
            self.db_service = kwargs['db_service']
            
        results = {"doors_checked": 0, "notifications_sent": 0}
        
        # Recupera tutti i dispenser dal Digital Twin
        dispensers = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "dispenser_medicine"]
        for dispenser in dispensers:
            results["doors_checked"] += 1
            
            dispenser_id = dispenser.get("_id")
            door_status = dispenser.get("data", {}).get("door_status")
            last_event = dispenser.get("data", {}).get("last_door_event")
            
            # Se la porta è aperta e c'è un timestamp valido
            if door_status == "open" and last_event:
                try:
                    last_event_time = datetime.fromisoformat(str(last_event)) if not isinstance(last_event, datetime) else last_event
                    seconds_open = (datetime.now() - last_event_time).total_seconds()
                    
                    if seconds_open > self.notification_threshold:
                        # Registra notifica
                        self._send_door_notification(dispenser)
                        results["notifications_sent"] += 1
                except Exception as e:
                    print(f"Errore nel controllo porta {dispenser_id}: {e}")
                
        return results
    
    def door_state_changed(self, door_id, state, timestamp=None):
        """
        Gestisce il cambio di stato di una porta e aggiorna il database
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Memorizza lo stato localmente
        self.last_state[door_id] = {
            'state': state,
            'timestamp': timestamp
        }
        
        # Aggiorna il database se disponibile
        if self.db_service:
            update_operation = {
                "$set": {
                    "data.door_status": state,
                    "data.last_door_event": timestamp.isoformat()
                }
            }
            self.db_service.update_dr("dispenser_medicine", door_id, update_operation)
            
        print(f"[DoorEventService] Porta {door_id}: {state} alle {timestamp.strftime('%H:%M:%S')}")
    
    def _send_door_notification(self, dispenser):
        """Invia una notifica per una porta aperta da troppo tempo"""
        dispenser_id = dispenser.get("_id")
        dispenser_name = dispenser.get("data", {}).get("name", "dispenser")
        
        message = f"⚠️ La porta del dispenser '{dispenser_name}' è rimasta aperta troppo a lungo."
        print(f"Invio notifica porta: {message} per dispenser {dispenser_id}")
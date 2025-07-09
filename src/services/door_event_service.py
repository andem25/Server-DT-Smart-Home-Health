# Modifichiamo la classe esistente per implementare la nuova interfaccia
from datetime import datetime
from src.services.base import BaseService
import json

class DoorEventService(BaseService):
    """
    Servizio che monitora eventi di apertura/chiusura delle porte (FR-2)
    """
    
    def __init__(self, db_service=None):
        super().__init__()
        self.name = "DoorEventService"
        self.last_state = {}
        self.irregularity_events = {}
        self.last_notifications = {}
        self.notification_threshold = 30  # secondi
        self.db_service = db_service
    
    # Metodo di compatibilità con lo scheduler esistente
    def execute(self, dt_data, threshold_minutes=1, **kwargs):
        """
        Metodo di compatibilità - delega al DigitalTwin
        """
        # Se abbiamo un'istanza DT, deleghiamo
        if 'dt_instance' in kwargs:
            return kwargs['dt_instance'].execute_door_monitoring(threshold_minutes)
    
    # Metodi dell'interfaccia DoorServiceInterface
    def check_door_alerts(self, dispenser_data, threshold_minutes=1):
        """
        Verifica se ci sono porte rimaste aperte troppo a lungo
        """
        alerts = []
        now = datetime.now()
        
        dispenser_id = dispenser_data.get("_id")
        door_status = dispenser_data.get("data", {}).get("door_status")
        last_event_time_str = dispenser_data.get("data", {}).get("last_door_event")
        
        # Controlla solo se la porta è aperta e se abbiamo un timestamp valido
        if door_status == "open" and last_event_time_str:
            try:
                # Converte il timestamp in oggetto datetime
                if isinstance(last_event_time_str, str):
                    last_event_time = datetime.fromisoformat(last_event_time_str)
                else:
                    last_event_time = last_event_time_str
                
                # Calcola da quanti minuti è aperta
                minutes_open = (now - last_event_time).total_seconds() / 60
                
                if minutes_open > threshold_minutes:
                    alert = {
                        "type": "door_open_too_long",
                        "dispenser_id": dispenser_id,
                        "dispenser_name": dispenser_data.get("data", {}).get("name", "dispenser"),
                        "location": dispenser_data.get("data", {}).get("location", "sconosciuta"),
                        "minutes_open": round(minutes_open),
                        "severity": "medium", 
                        "timestamp": now.isoformat()
                    }
                    alerts.append(alert)
            except Exception as e:
                print(f"Errore nel controllo porta {dispenser_id}: {e}")
        
        return alerts
    
    def handle_door_event(self, dispenser_id, state, timestamp=None):
        """
        Gestisce un evento di cambio stato della porta
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Ottieni il dispenser per verificare la regolarità
        if self.db_service:
            dispenser = self.db_service.get_dr("dispenser_medicine", dispenser_id)
            if dispenser:
                # Verifica se l'evento è regolare
                is_regular = self.is_event_regular(dispenser, timestamp, state)
                
                # Crea l'oggetto evento
                event_regularity = "regular" if is_regular else "irregular"
                reason = "within_schedule" if is_regular else "outside_schedule"
                
                # Dettagli dell'evento
                event_details = {
                    "state": state,
                    "timestamp": timestamp.isoformat(),
                    "regularity": event_regularity,
                    "reason": reason,
                    "is_regular": is_regular
                }
                
                # Memorizza l'evento nel database
                self.door_state_changed(dispenser_id, state, timestamp, is_regular)
                
                return event_details
        
        # Se non è stato possibile verificare la regolarità, considera l'evento come irregolare
        return {
            "state": state,
            "timestamp": timestamp.isoformat() if timestamp else datetime.now().isoformat(),
            "regularity": "irregular",
            "reason": "unknown",
            "is_regular": False
        }
    
    def is_event_regular(self, dispenser_data, timestamp, state):
        """
        Determina se un evento porta è regolare in base all'orario configurato
        """
        # Ottieni l'orario di assunzione configurato
        medicine_time = dispenser_data.get("data", {}).get("medicine_time", {})
        if not medicine_time:
            return False
            
        start_time = medicine_time.get("start")
        end_time = medicine_time.get("end")
        
        if not start_time or not end_time:
            return False
        
        try:
            # Converti orari in oggetti datetime per confronto
            today_str = timestamp.strftime("%Y-%m-%d")
            start_dt = datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{today_str} {end_time}", "%Y-%m-%d %H:%M")
            
            # L'evento è regolare se avviene nell'intervallo configurato
            return start_dt <= timestamp <= end_dt
            
        except ValueError as e:
            print(f"Errore nel parsing degli orari di medicina: {e}")
            return False
    
    # Mantieni i metodi esistenti per retrocompatibilità
    def handle_door_status_update(self, db_service, dt_factory, dispenser_id, payload):
        """
        Gestisce un aggiornamento di stato della porta ricevuto via MQTT
        """
        try:
            # Parsing del payload
            data = json.loads(payload)
            door_value = data.get("door")
            time_str = data.get("time")
            
            # Converti il valore numerico in stato testuale
            if door_value == 1:
                state = "open"
            elif door_value == 0:
                state = "closed"
            else:
                print(f"DoorEventService: Valore porta non valido: {door_value}")
                return
            
            # Crea timestamp completo
            if time_str:
                today = datetime.now().strftime("%Y-%m-%d")
                timestamp = datetime.fromisoformat(f"{today}T{time_str}")
            else:
                timestamp = datetime.now()
            
            # Assegna i servizi se sono stati passati
            if db_service:
                self.db_service = db_service
            if dt_factory:
                self.dt_factory = dt_factory
            
            # Ottieni il dispenser
            dispenser = self.db_service.get_dr("dispenser_medicine", dispenser_id)
            if not dispenser:
                print(f"Dispenser {dispenser_id} non trovato nel database")
                return
            
            # Usa il nuovo metodo dell'interfaccia
            event_details = self.handle_door_event(dispenser_id, state, timestamp)
            is_regular = event_details.get("is_regular", False)
            
            # Invia notifica all'utente se l'evento è irregolare
            if not is_regular and hasattr(self, 'dt_factory'):
                from src.application.bot.notifications import send_door_irregularity_alert
                send_door_irregularity_alert(
                    self.db_service,
                    self.dt_factory,
                    dispenser_id,
                    state,
                    timestamp,
                    event_details
                )
            
        except Exception as e:
            print(f"Errore nell'aggiornamento dello stato porta per dispenser {dispenser_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def door_state_changed(self, dispenser_id, state, timestamp, is_regular):
        """
        Aggiorna lo stato della porta nel database e registra l'evento
        
        Args:
            dispenser_id: ID del dispenser
            state: Nuovo stato della porta ('open' o 'closed')
            timestamp: Data e ora dell'evento
            is_regular: Flag che indica se l'evento è regolare
        """
        if not self.db_service:
            print(f"Impossibile aggiornare stato porta: servizio database non disponibile")
            return
            
        try:
            # Aggiorna lo stato attuale della porta nel dispenser
            update_operation = {
                "$set": {
                    "data.door_status": state,
                    "data.last_door_event": timestamp.isoformat()
                }
            }
            self.db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
            
            # Aggiungi il nuovo evento alla cronologia degli eventi
            event_data = {
                "state": state,
                "timestamp": timestamp.isoformat(),
                "is_regular": is_regular
            }
            
            # Aggiungi l'evento alla lista degli eventi porta
            update_operation = {
                "$push": {
                    "data.door_events": event_data
                }
            }
            self.db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
            
            print(f"Stato porta aggiornato per dispenser {dispenser_id}: {state}, regolare: {is_regular}")
        
        except Exception as e:
            print(f"Errore nell'aggiornamento dello stato porta nel database: {e}")

from datetime import datetime
from src.services.base import BaseService
import json

class DoorEventService(BaseService):
    """
    Servizio che monitora eventi di apertura/chiusura delle porte (FR-2)
    """
    
    def __init__(self):
        self.name = "DoorEventService"
        self.last_state = {}
        self.irregularity_events = {}
        
    def configure(self, config):
        self.notification_threshold = config.get('notification_threshold', 30)  # secondi
        self.db_service = None  # Sarà impostato durante l'esecuzione
        return self
        
    def execute(self, dt_data, **kwargs):
        """Verifica lo stato delle porte e invia notifiche se necessario"""
        if 'db_service' in kwargs:
            self.db_service = kwargs['db_service']
            
        results = {
            "doors_checked": 0, 
            "notifications_sent": 0,
            "irregularities_detected": 0
        }
        
        # Recupera tutti i dispenser dal Digital Twin
        dispensers = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "dispenser_medicine"]
        for dispenser in dispensers:
            results["doors_checked"] += 1
            
            dispenser_id = dispenser.get("_id")
            door_status = dispenser.get("data", {}).get("door_status")
            last_event = dispenser.get("data", {}).get("last_door_event")
            last_event_regular = dispenser.get("data", {}).get("last_event_regular", True)
            
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
            
            # Conta irregolarità
            if not last_event_regular:
                results["irregularities_detected"] += 1
                
        return results
    
    def door_state_changed(self, door_id, state, timestamp=None, is_regular=False):
        """
        Gestisce il cambio di stato di una porta e aggiorna il database
        
        Args:
            door_id: ID della porta
            state: Stato della porta ('open' o 'closed')
            timestamp: Timestamp dell'evento
            is_regular: Se l'evento è considerato "regolare" rispetto all'orario di assunzione
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Memorizza lo stato localmente
        self.last_state[door_id] = {
            'state': state,
            'timestamp': timestamp,
            'is_regular': is_regular
        }
        
        # Traccia le irregolarità separatamente
        if not is_regular:
            if door_id not in self.irregularity_events:
                self.irregularity_events[door_id] = []
            
            self.irregularity_events[door_id].append({
                'state': state,
                'timestamp': timestamp,
                'action': 'open' if state == 'open' else 'close'
            })
        
        # Aggiorna il database se disponibile
        if self.db_service:
            update_operation = {
                "$set": {
                    "data.door_status": state,
                    "data.last_door_event": timestamp.isoformat(),
                    "data.last_event_regular": is_regular
                }
            }
            self.db_service.update_dr("dispenser_medicine", door_id, update_operation)
            
        # Log con informazioni sulla regolarità
        regularity_str = "regolare" if is_regular else "irregolare"
        print(f"[DoorEventService] Porta {door_id}: {state} alle {timestamp.strftime('%H:%M:%S')} - {regularity_str}")
    
    def _send_door_notification(self, dispenser):
        """Invia una notifica per una porta aperta da troppo tempo"""
        dispenser_id = dispenser.get("_id")
        dispenser_name = dispenser.get("data", {}).get("name", "dispenser")
        
        message = f"⚠️ La porta del dispenser '{dispenser_name}' è rimasta aperta troppo a lungo."
        print(f"Invio notifica porta: {message} per dispenser {dispenser_id}")
        
        # In un sistema reale qui invieremmo la notifica all'utente
        # Questo viene già gestito dal MQTT Subscriber
    
    def handle_door_status_update(self, db_service, dt_factory, dispenser_id, payload):
        """
        Gestisce un aggiornamento di stato della porta ricevuto via MQTT
        
        Args:
            db_service: Servizio database per accedere ai dati
            dt_factory: Factory per accedere ai Digital Twin
            dispenser_id (str): ID del dispenser
            payload (str): Payload JSON ricevuto via MQTT
        """
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
                    print(f"DoorEventService: Valore porta non valido: {door_value}")
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
                print(f"DoorEventService: Formato payload non valido: '{payload}'")
                return
            except ValueError as e:
                print(f"DoorEventService: Errore nel parsing dell'orario: {e}")
                timestamp = datetime.now()
                time_str = timestamp.strftime("%H:%M:%S")
        
            # Genera timestamp ISO
            timestamp_iso = timestamp.isoformat()
            
            # Ottieni il dispenser per verificare gli orari di medicina configurati
            dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
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
            db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
            
            # Log con informazioni sulla regolarità
            regularity_str = "REGOLARE" if is_regular else "IRREGOLARE"
            print(f"Dispenser {dispenser_id}: porta {state} alle {timestamp.strftime('%H:%M:%S')} - {regularity_str}")
            
            # Importa la funzione per inviare notifiche
            from src.application.bot.notifications import send_door_irregularity_alert
            
            # Invia notifica all'utente se l'evento è irregolare
            if not is_regular:
                event_details = {
                    "timestamp": timestamp,
                    "state": state,
                    "regularity": event_regularity,
                    "reason": reason
                }
                send_door_irregularity_alert(db_service, dt_factory, dispenser_id, state, timestamp, event_details)
        
            # Notifica il servizio usando il metodo esistente door_state_changed
            self.door_state_changed(dispenser_id, state, timestamp, is_regular)
            
        except Exception as e:
            print(f"Errore nell'aggiornamento dello stato porta per dispenser {dispenser_id}: {e}")
            import traceback
            traceback.print_exc()
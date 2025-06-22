from datetime import datetime

class DoorEventService:
    """
    Servizio che monitora eventi di apertura/chiusura delle porte (FR-2)
    """
    
    def __init__(self, dt, config):
        """
        Inizializza il servizio
        
        Args:
            dt: Riferimento al Digital Twin
            config: Configurazione del servizio
        """
        self.dt = dt
        self.config = config
        self.notification_threshold = config.get('notification_threshold', 30)  # secondi
        self.last_state = {}  # Memorizza l'ultimo stato noto per ogni porta
        self.timer = {}  # Timer per ciascuna porta
        print(f"[DoorEventService] Inizializzato per {dt.name} con threshold {self.notification_threshold}s")
        
    def door_state_changed(self, door_id, state, timestamp=None):
        """
        Gestisce il cambio di stato di una porta
        
        Args:
            door_id: Identificativo della porta
            state: Nuovo stato ('open' o 'closed')
            timestamp: Timestamp dell'evento (opzionale)
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Memorizza il nuovo stato
        self.last_state[door_id] = {
            'state': state,
            'timestamp': timestamp
        }
        
        print(f"[DoorEventService] Porta {door_id}: {state} alle {timestamp.strftime('%H:%M:%S')}")
        
        # Avvia un timer se la porta è stata aperta
        if state == 'open':
            # TODO: implementare timer per notifica dopo notification_threshold
            pass
    
    def get_door_state(self, door_id):
        """Restituisce lo stato corrente di una porta"""
        if door_id in self.last_state:
            return self.last_state[door_id]
        return None
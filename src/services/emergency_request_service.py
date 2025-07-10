from datetime import datetime
from src.services.base import BaseService
from flask import current_app

class EmergencyRequestService(BaseService):
    """
    Servizio che gestisce le richieste di aiuto di emergenza (FR-6)
    """
    
    def __init__(self):
        super().__init__()
        self.name = "EmergencyRequestService"
        self.emergency_requests = {}
        
    def configure(self, config):
        """Configurazione del servizio"""
        self.emergency_contacts = config.get("emergency_contacts", ["supervisor"])
        self.auto_call_threshold = config.get("auto_call_threshold", 120)  # secondi
        self.db_service = None
        return self
    
    # metodo che separa le notifiche dall'aggiornamento dello stato
    def handle_emergency_notification(self, device_id, dt_id, dt_name):
        """
        Invia notifiche per una richiesta di emergenza
        Questa funzione è chiamata dal DigitalTwin
        
        Args:
            device_id: ID del dispositivo che ha richiesto aiuto
            dt_id: ID del Digital Twin
            dt_name: Nome del Digital Twin
            
        Returns:
            int: Numero di notifiche inviate
        """
        # Memorizza la richiesta localmente
        self.emergency_requests[device_id] = {
            'dt_id': dt_id,
            'dt_name': dt_name,
            'timestamp': datetime.now(),
            'status': 'active'
        }
        
        # Invia le notifiche
        return self._send_emergency_notification(device_id, dt_id, dt_name)
    
    def execute(self, device_id, dt_id, dt_name, timestamp=None):
        """
        Metodo legacy per retrocompatibilità
        Ora delega al Digital Twin quando possibile
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Se dt_factory è disponibile, cerca l'istanza DT e delega
        if hasattr(self, 'dt_factory') and self.dt_factory:
            try:
                dt_instance = self.dt_factory.get_dt_instance(dt_id)
                if dt_instance:
                    return dt_instance.execute_emergency_request(device_id, timestamp)
            except Exception as e:
                print(f"Errore nell'ottenere l'istanza DT: {e}")
        
        # Altrimenti, gestisci direttamente (per compatibilità)
        
        # Registra l'evento nel database
        if self.db_service:
            # Aggiornamento del documento del dispositivo
            update_operation = {
                "$push": {
                    "data.emergency_requests": {
                        "timestamp": timestamp.isoformat(),
                        "status": "active",
                        "resolved_at": None
                    }
                },
                "$set": {
                    "data.emergency_active": True,
                    "data.last_emergency_request": timestamp.isoformat()
                }
            }
            self.db_service.update_dr("dispenser_medicine", device_id, update_operation)
        
        # Invia notifiche di emergenza
        notifications_sent = self._send_emergency_notification(device_id, dt_id, dt_name)
        
        # Log dell'evento
        print(f"[EmergencyRequestService] Richiesta di emergenza da {device_id} (DT: {dt_name}) alle {timestamp.strftime('%H:%M:%S')}")
        
        return {
            "device_id": device_id,
            "dt_id": dt_id,
            "timestamp": timestamp.isoformat(),
            "notifications_sent": notifications_sent
        }
    
    def _send_emergency_notification(self, device_id, dt_id, dt_name):
        """Invia notifica di emergenza ai contatti configurati"""
        try:
            # Prepara il messaggio
            message = (
                f"🚨 *ALLARME EMERGENZA*!\n\n"
                f"⚠️ *RICHIESTA DI AIUTO* dal dispositivo `{device_id}`\n"
                f"📍 Appartiene alla casa: *{dt_name}*\n\n"
                f"*Intervento richiesto immediatamente.*"
            )
            
            # Importa la funzione per inviare notifiche
            from src.application.bot.notifications import send_notification_to_dt_users, send_generic_emergency_alert
            
            # Se dt_factory è disponibile, usa send_notification_to_dt_users
            if hasattr(self, 'dt_factory') and self.dt_factory:
                return send_notification_to_dt_users(self.dt_factory, dt_id, message)
            # Altrimenti usa send_generic_emergency_alert che non richiede dt_factory
            else:
                return send_generic_emergency_alert(self.db_service, device_id)
                
        except Exception as e:
            print(f"Errore nell'invio della notifica di emergenza: {e}")
            import traceback
            traceback.print_exc()
            return 0
        
    def _get_dt_supervisors(self, dt_id):
        """Recupera tutti i supervisori associati al Digital Twin"""
        return [
            {"telegram_id": 157933243, "username": "supervisore_test"}
        ]
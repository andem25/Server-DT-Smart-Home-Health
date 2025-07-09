from datetime import datetime
from src.services.base import BaseService
from flask import current_app
from asyncio import run_coroutine_threadsafe

class EmergencyRequestService(BaseService):
    """
    Servizio che gestisce le richieste di aiuto di emergenza (FR-6)
    """
    
    def __init__(self):
        self.name = "EmergencyRequestService"
        self.emergency_requests = {}
        
    def configure(self, config):
        """Configurazione del servizio"""
        self.emergency_contacts = config.get("emergency_contacts", ["supervisor"])
        self.auto_call_threshold = config.get("auto_call_threshold", 120)  # secondi
        self.db_service = None
        return self
    
    
    def execute(self, device_id, dt_id, dt_name, timestamp=None):
        """
        Gestisce una richiesta di emergenza da un dispositivo
        e invia notifiche ai contatti di emergenza
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Memorizza la richiesta localmente
        self.emergency_requests[device_id] = {
            'dt_id': dt_id,
            'dt_name': dt_name,
            'timestamp': timestamp,
            'status': 'active'
        }
        
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
        self._send_emergency_notification(device_id, dt_id, dt_name)
        
        # Log dell'evento
        print(f"[EmergencyRequestService] Richiesta di emergenza da {device_id} (DT: {dt_name}) alle {timestamp.strftime('%H:%M:%S')}")
        return True
    
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
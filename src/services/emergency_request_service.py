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
    
    def execute(self, dt_data, **kwargs):
        """Verifica lo stato delle richieste di emergenza attive"""
        if 'db_service' in kwargs:
            self.db_service = kwargs['db_service']
            
        results = {"requests_active": 0, "notifications_sent": 0}
        
        # Recupera tutte le richieste di emergenza attive dal Digital Twin
        # In una implementazione completa, si potrebbero controllare richieste di emergenza
        # non gestite e inviarle nuovamente
        
        return results
    
    def emergency_requested(self, device_id, dt_id, dt_name, timestamp=None):
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
            # Ottieni il Digital Twin per accedere agli ID Telegram attivi
            dt = None
            if self.dt_factory:
                dt = self.dt_factory.get_dt(dt_id)
            
            # Ottieni gli ID Telegram attivi dal DT
            telegram_ids = []
            if dt and "metadata" in dt and "active_telegram_ids" in dt["metadata"]:
                # Converti esplicitamente tutti gli ID a int
                try:
                    # Gestisci sia liste di stringhe che di interi
                    telegram_ids = [int(id_val) for id_val in dt["metadata"]["active_telegram_ids"]]
                    print(f"DEBUG: IDs Telegram trovati per emergenza: {telegram_ids}")
                except (ValueError, TypeError) as e:
                    print(f"ERRORE nella conversione degli ID Telegram: {e}")
            
            # Se non ci sono ID attivi, usa i supervisori come fallback
            if not telegram_ids:
                supervisors = self._get_dt_supervisors(dt_id)
                for supervisor in supervisors:
                    if "telegram_id" in supervisor:
                        telegram_ids.append(supervisor["telegram_id"])
            
            # Se ancora non ci sono ID, usa l'ID di test come ultima risorsa
            if not telegram_ids:
                telegram_ids = [157933243]  # ID di fallback solo come ultima risorsa
                print(f"ATTENZIONE: Nessun ID Telegram trovato per il DT {dt_id}, uso ID di fallback")
            
            # Prepara il messaggio
            message = (
                f"🚨 *ALLARME EMERGENZA*!\n\n"
                f"⚠️ *RICHIESTA DI AIUTO* dal dispositivo `{device_id}`\n"
                f"📍 Appartiene alla casa: *{dt_name}*\n\n"
                f"*Intervento richiesto immediatamente.*"
            )
            
            # Ottieni il token del bot dalle variabili d'ambiente
            from os import environ
            token = environ.get('TELEGRAM_TOKEN')
            
            if not token:
                print("DEBUG: Token Telegram non trovato per notifica di emergenza")
                return
            
            # Invia messaggio a tutti gli ID Telegram attivi
            import requests
            successful_sends = 0
            for telegram_id in telegram_ids:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = {
                    "chat_id": telegram_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                
                response = requests.post(url, json=data)
                if response.status_code == 200:
                    print(f"Notifica di emergenza inviata all'ID Telegram: {telegram_id}")
                    successful_sends += 1
                else:
                    print(f"Errore nell'invio notifica: {response.status_code} - {response.text}")
            
            return successful_sends
                
        except Exception as e:
            print(f"Errore nell'invio della notifica di emergenza: {e}")
            import traceback
            traceback.print_exc()
            return 0
        
    def _get_dt_supervisors(self, dt_id):
        """Recupera tutti i supervisori associati al Digital Twin"""
        # In un caso reale, questa funzione dovrebbe interrogare il database
        # per trovare tutti i supervisori associati al dt_id
        
        # Per ora restituiamo un array di esempio
        # Nel sistema reale, questo dovrebbe essere recuperato dal database
        return [
            {"telegram_id": 157933243, "username": "supervisore_test"}
            # Aggiungere altri supervisori se necessario
        ]
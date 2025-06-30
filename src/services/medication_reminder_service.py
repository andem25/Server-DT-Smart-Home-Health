from src.services.base import BaseService
from datetime import datetime, timedelta
import json
from src.services.mqtt.mqtt_service import send_mqtt_message

class MedicationReminderService(BaseService):
    """Servizio promemoria medicinali per FR-1"""
    
    def __init__(self):
        self.name = "MedicationReminderService"
        self.active_reminders = {}
        self.time_based_reminders = {}  # Nuova struttura per i promemoria basati sull'orario
        
    def configure(self, config):
        """Configurazione del servizio"""
        self.reminder_interval = config.get("reminder_interval", 300)  # 5 minuti di default
        self.notification_channels = config.get("channels", ["telegram"])
        return self
        
    def execute(self, dt_data, **kwargs):
        """Esegue il controllo e invia promemoria quando necessario"""
        results = {"promemoria_inviati": 0, "dispenser_verificati": 0}
        
        # Estrai tutti i dispensatori dal Digital Twin
        dispensers = []
        for dr in dt_data.get("digital_replicas", []):
            if dr.get("type") == "dispenser_medicine":
                dispensers.append(dr)
                results["dispenser_verificati"] += 1
                
        if not dispensers:
            return {"status": "no_dispensers_found"}
            
        # Verifica ed elabora ogni dispenser
        for dispenser in dispensers:
            # Controllo basato su intervallo orario
            if self._check_time_based_reminder(dispenser):
                self._send_time_based_reminder(dispenser)
                results["promemoria_inviati"] += 1
                
            # Controllo basato su intervallo generico (funzionalità esistente)
            elif self._check_dispenser_needs_reminder(dispenser):
                self._send_reminder(dispenser)
                self._register_reminder_sent(dispenser)
                results["promemoria_inviati"] += 1
                
        return results
        
    def _check_time_based_reminder(self, dispenser):
        """Verifica se è il momento di inviare un promemoria basato sull'orario configurato"""
        dispenser_id = dispenser.get("_id")
        medicine_time = dispenser.get("data", {}).get("medicine_time")
        
        if not medicine_time:
            return False
            
        start_time = medicine_time.get("start")
        end_time = medicine_time.get("end")
        
        if not start_time or not end_time:
            return False
            
        try:
            # Converti gli orari in oggetti datetime
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            start_dt = datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{today_str} {end_time}", "%Y-%m-%d %H:%M")
            
            # MODIFICA: Usa direttamente l'orario di inizio invece di calcolare il punto medio
            # Calcola la differenza tra l'ora corrente e l'orario di inizio
            time_diff = (now - start_dt).total_seconds()
            
            # Verifichiamo che non abbiamo già inviato un promemoria per questo dispenser oggi
            last_sent = self.time_based_reminders.get(dispenser_id, {}).get(today_str)
            
            if not last_sent and -60 <= time_diff <= 60:
                # Registra che abbiamo inviato il promemoria oggi
                if dispenser_id not in self.time_based_reminders:
                    self.time_based_reminders[dispenser_id] = {}
                self.time_based_reminders[dispenser_id][today_str] = now
                return True
                
            return False
                
        except Exception as e:
            print(f"Errore nella verifica del promemoria basato sull'orario: {e}")
            return False
            
    def _send_time_based_reminder(self, dispenser):
        """Invia un promemoria basato sull'orario configurato"""
        dispenser_id = dispenser.get("_id")
        user_db_id = dispenser.get("user_db_id")
        medicine_name = dispenser.get("data", {}).get("medicine_name", "medicinale")
        
        # Dettagli orario
        medicine_time = dispenser.get("data", {}).get("medicine_time", {})
        start_time = medicine_time.get("start", "??:??")
        end_time = medicine_time.get("end", "??:??")
        
        # Prepara il messaggio di notifica
        topic = f"{dispenser_id}/notification"
        message = "1"
        
        # Invia il messaggio MQTT
        try:
            send_mqtt_message(message, topic)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Inviato promemoria via MQTT a {dispenser_id} per {medicine_name} (finestra oraria: {start_time}-{end_time})")
            
            # DEBUG: Stampa dettagli completi per debugging
            print(f"DEBUG - Dettagli promemoria:")
            print(f" - Topic: {topic}")
            print(f" - Messaggio: {message}")
            print(f" - Dispenser ID: {dispenser_id}")
            print(f" - Utente: {user_db_id}")
            
            return True
        except Exception as e:
            print(f"Errore nell'invio del messaggio MQTT: {e}")
            return False
            
    def update_medicine_times(self, dispenser_id, start_time, end_time):
        """
        Aggiorna gli orari di assunzione per un dispenser specifico
        Può essere chiamato direttamente dal handler per aggiornare il servizio
        """
        # Resetta eventuali promemoria precedenti per questo dispenser
        if dispenser_id in self.time_based_reminders:
            del self.time_based_reminders[dispenser_id]
            print(f"Reset dei promemoria per il dispenser {dispenser_id}")
            
    def _check_dispenser_needs_reminder(self, dispenser):
        """Verifica se è necessario inviare un promemoria per questo dispenser"""
        # Accesso sicuro ai dati
        dispenser_data = dispenser.get("data", {})
        medicine_name = dispenser_data.get("medicine_name", "medicinale")
        interval_str = dispenser_data.get("interval", "")
        status = dispenser_data.get("status", "")
        frequency = dispenser_data.get("frequency_per_day", 1)
        
        # Se il dispenser è vuoto o in errore, non inviare promemoria
        if status in ["empty", "error"]:
            return False
            
        # Verifica se l'orario attuale rientra nell'intervallo configurato
        if not interval_str:
            return False
            
        try:
            start_hour, end_hour = map(int, interval_str.split("-"))
            current_hour = datetime.now().hour
            
            # Se non siamo nell'intervallo orario, non inviare promemoria
            if not (start_hour <= current_hour <= end_hour):
                return False
                
            # Verifica quante dosi sono già state prese oggi
            today = datetime.now().strftime("%Y-%m-%d")
            regularity = dispenser_data.get("regularity", [])
            today_entries = [r for r in regularity if r.get("date") == today]
            
            # Se non ci sono dati per oggi, è necessario un promemoria
            if not today_entries:
                return True
                
            # Altrimenti, controlla se sono state prese tutte le dosi previste
            today_entry = today_entries[0]
            times_taken = len(today_entry.get("times", []))
            
            # Se il numero di dosi prese è inferiore alla frequenza giornaliera, invia promemoria
            if times_taken < frequency:
                # Verifica quanto tempo è passato dall'ultimo promemoria
                last_alert = next((a for a in dispenser_data.get("alerts", []) 
                                if a.get("type") == "reminder" and 
                                datetime.fromisoformat(a.get("timestamp")).date() == datetime.now().date()), 
                                None)
                
                # Se non è mai stato inviato un promemoria oggi o è passato abbastanza tempo dall'ultimo
                if not last_alert or (datetime.now() - datetime.fromisoformat(last_alert.get("timestamp"))).seconds > self.reminder_interval:
                    return True
            
            return False
                
        except Exception as e:
            print(f"Errore nella verifica del promemoria: {e}")
            return False
    
    def _send_reminder(self, dispenser):
        """Invia un promemoria per un dispenser specifico"""
        user_db_id = dispenser.get("user_db_id")
        medicine_name = dispenser.get("data", {}).get("medicine_name", "medicinale")
        dosage = dispenser.get("data", {}).get("dosage", "")
        
        message = f"⏰ Promemoria: È ora di assumere {medicine_name}"
        if dosage:
            message += f" ({dosage})"
            
        # In un sistema reale, qui si invierebbe la notifica attraverso i canali configurati
        print(f"Invio promemoria: {message} a utente {user_db_id}")
    
    def _register_reminder_sent(self, dispenser):
        """Registra l'invio del promemoria nella Digital Replica del dispenser"""
        dispenser_id = dispenser.get("_id")
        
        # Aggiunge un alert di tipo "reminder" nel dispenser
        alert = {
            "type": "reminder",
            "timestamp": datetime.now().isoformat(),
            "resolved": False
        }
        
        # Qui dovresti aggiornare il documento nella collezione MongoDB
        # usando db_service.update_dr("dispenser_medicine", dispenser_id, ...)
        # Ma per semplicità qui stampiamo solo un messaggio
        print(f"Registrato promemoria inviato per dispenser {dispenser_id}")
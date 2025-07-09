
from src.services.base import BaseService
from datetime import datetime, timedelta
from src.application.mqtt import send_mqtt_message
import json

class MedicationReminderService(BaseService):
    """Servizio promemoria medicinali per FR-1"""
    
    def __init__(self):
        super().__init__()
        self.name = "MedicationReminderService"
        self.time_based_reminders = {}  # Per compatibilità con codice esistente
        self.last_notification_sent = {}
        self.missed_dose_notifications = {}
        self.min_notification_interval = 3600  # 1 ora, configurable
        
    # Metodo di compatibilità con lo scheduler esistente
    def execute(self, dt_data, **kwargs):
        """
        Metodo di compatibilità - delega al DigitalTwin
        """
        # Se abbiamo un'istanza DT, deleghiamo
        if 'dt_instance' in kwargs:
            return kwargs['dt_instance'].execute_medication_reminders()
        
        
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
            
            # Verifica l'ultima notifica inviata (ora usa timestamp completo)
            last_sent = self.last_notification_sent.get(dispenser_id)
            
            # Invia il promemoria solo se:
            # 1. Non è già stato inviato recentemente (nell'intervallo minimo)
            # 2. L'ora attuale è entro un minuto dall'inizio dell'intervallo
            time_diff = (now - start_dt).total_seconds()
            
            if (not last_sent or (now - last_sent).total_seconds() > self.min_notification_interval) and 0 <= time_diff <= 60:
                # Registra l'invio di questa notifica
                self.last_notification_sent[dispenser_id] = now
                
                # Mantiene anche la compatibilità col vecchio sistema di tracciamento
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
        medicine_name = dispenser.get("data", {}).get("medicine_name", "medicinale")
        
        # Dettagli orario
        
        # Prepara il messaggio di notifica - CORREZIONE: aggiungiamo timestamp per rendere univoco
        now = datetime.now()
        topic = f"{dispenser_id}/notification"
        message = f"1"  # Aggiungiamo timestamp per rendere univoco ogni messaggio
        
        # Invia il messaggio MQTT
        try:
            print(f"DEBUG: Invio notifica MQTT a {topic}: '{message}'")
            # Mettiamo l'aggiornamento del timestamp DOPO l'invio riuscito
            send_mqtt_message(message, topic)
            
            # Aggiorniamo l'ultimo invio SOLO dopo un invio riuscito
            self.last_notification_sent[dispenser_id] = now
            
            # Aggiungiamo al dizionario di monitoraggio
            if dispenser_id not in self.time_based_reminders:
                self.time_based_reminders[dispenser_id] = {}
            self.time_based_reminders[dispenser_id][now.strftime("%Y-%m-%d")] = now
            
            print(f"✅ [{now.strftime('%H:%M:%S')}] Inviata notifica MQTT a {topic} per {medicine_name}")
            return True
        except Exception as e:
            print(f"❌ Errore nell'invio del messaggio MQTT: {repr(e)}")
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
        dispenser_id = dispenser.get("_id")
        # Verifica se è già stata inviata una notifica recentemente
        last_sent = self.last_notification_sent.get(dispenser_id)
        now = datetime.now()
        
        if last_sent and (now - last_sent).total_seconds() < self.min_notification_interval:
            return False
        
        # Accesso sicuro ai dati
        dispenser_data = dispenser.get("data", {})
        medicine_name = dispenser_data.get("medicine_name", "medicinale")
        status = dispenser_data.get("status", "")
        frequency = dispenser_data.get("frequency_per_day", 1)
        
        # Se il dispenser è vuoto o in errore, non inviare promemoria
        if status in ["empty", "error"]:
            return False
        
        # Verifica se esiste medicine_time invece dell'intervallo
        medicine_time = dispenser_data.get("medicine_time", {})
        start_time = medicine_time.get("start")
        end_time = medicine_time.get("end")
        
        # Se non ci sono orari configurati, non inviare promemoria
        if not start_time or not end_time:
            return False
        
        try:
            # Converti gli orari in oggetti datetime
            today_str = now.strftime("%Y-%m-%d")
            start_dt = datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{today_str} {end_time}", "%Y-%m-%d %H:%M")
            
            # Se non siamo nell'intervallo orario, non inviare promemoria
            if not (start_dt <= now <= end_dt):
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
                                datetime.fromisoformat(a.get("timestamp")).date() == now.date()), 
                                None)
                
                # Se non è mai stato inviato un promemoria oggi o è passato abbastanza tempo dall'ultimo
                if not last_alert or (now - datetime.fromisoformat(last_alert.get("timestamp"))).seconds > self.reminder_interval:
                    # Aggiorna l'ultima notifica inviata
                    self.last_notification_sent[dispenser_id] = now
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
    

    def check_adherence_irregularities(self, dt_data, threshold=1):
        """Verifica l'aderenza ai farmaci e rileva irregolarità"""
        alerts = []
        dispensers = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "dispenser_medicine"]
        
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        for dispenser in dispensers:
            dispenser_id = dispenser.get("_id")
            dispenser_name = dispenser.get("data", {}).get("name", "medicinale")
            regularity = dispenser.get("data", {}).get("regularity", [])
            
            # Controlla se negli ultimi giorni ci sono state assunzioni mancate
            missing_days = 0
            
            for i in range(1, 4):  # controlla gli ultimi 3 giorni
                check_date = (now.date() - timedelta(days=i)).strftime("%Y-%m-%d")
                day_entries = [r for r in regularity if r.get("date") == check_date]
                if not day_entries:
                    missing_days += 1
            
            if missing_days >= threshold:
                alerts.append({
                    "type": "missed_medication",
                    "dispenser_id": dispenser_id,
                    "dispenser_name": dispenser_name,
                    "missing_days": missing_days,
                    "severity": "high" if missing_days >= 3 else "medium",
                    "timestamp": datetime.now()
                })

            # Verifica se oggi è mancata una dose nell'intervallo configurato
            medicine_time = dispenser.get("data", {}).get("medicine_time", {})
            if medicine_time:
                start_time = medicine_time.get("start")
                end_time = medicine_time.get("end")
                
                if start_time and end_time:
                    try:
                        # Converti gli orari in oggetti datetime
                        end_dt = datetime.strptime(f"{today} {end_time}", "%Y-%m-%d %H:%M")
                        
                        # Se siamo DOPO la fine dell'intervallo di assunzione, verifichiamo se c'è stata un'assunzione
                        if now > end_dt:
                            # Verificare se esiste già una notifica per questo dispenser e intervallo orario oggi
                            # MODIFICA: Verifica nel database se è già stata inviata una notifica
                            missed_notifications = dispenser.get("data", {}).get("missed_dose_notifications", [])
                            notification_key = f"{today}_{start_time}_{end_time}"
                            
                            # Verifica se questa notifica è già stata inviata oggi
                            if notification_key in missed_notifications:
                                # Già inviata notifica per oggi, salta
                                continue
                            
                            # Verifica se c'è stata un'assunzione nell'intervallo
                            door_events = dispenser.get("data", {}).get("door_events", [])
                            today_events = [e for e in door_events if e.get("timestamp", "").startswith(today)]
                            
                            # Filtriamo gli eventi nell'intervallo di assunzione
                            open_events = False
                            close_events = False
                            
                            for event in today_events:
                                timestamp = event.get("timestamp", "")
                                if "T" in timestamp:
                                    event_time = timestamp.split("T")[1][:5]  # Estrae HH:MM
                                    if start_time <= event_time <= end_time:
                                        state = event.get("state", "")
                                        if state == "open":
                                            open_events = True
                                        elif state == "closed":
                                            close_events = True
                            
                            # Se non c'è stata un'assunzione completa, aggiungiamo un alert e notifichiamo
                            if not (open_events and close_events):
                                # Aggiungiamo l'alert
                                alerts.append({
                                    "type": "today_missed_dose",
                                    "dispenser_id": dispenser_id,
                                    "dispenser_name": dispenser_name,
                                    "scheduled_time": f"{start_time} - {end_time}",
                                    "severity": "high",
                                    "timestamp": now
                                })
                                
                                # Invia una notifica al supervisore
                                try:
                                    # Importa qui per evitare dipendenze circolari
                                    from src.application.bot.notifications import send_adherence_notification
                                    
                                    if hasattr(self, 'db_service') and self.db_service and hasattr(self, 'dt_factory') and self.dt_factory:
                                        # Prepara i dettagli per la notifica
                                        details = {
                                            "scheduled_time": f"{start_time} - {end_time}"
                                        }
                                        
                                        # Invia la notifica per dose mancata
                                        send_adherence_notification(
                                            self.db_service,
                                            self.dt_factory,
                                            dispenser_id,
                                            "missed_dose",
                                            details
                                        )
                                        
                                        # MODIFICA: Salva nel database che la notifica è stata inviata
                                        # Aggiungi questa notifica all'elenco delle notifiche inviate per questo dispenser
                                        update_operation = {
                                            "$addToSet": {  # Usa $addToSet per evitare duplicati
                                                "data.missed_dose_notifications": notification_key
                                            }
                                        }
                                        self.db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
                                        
                                        print(f"Inviata notifica per dose mancata del dispenser {dispenser_name} ({start_time}-{end_time})")
                                except Exception as e:
                                    print(f"Errore nell'invio della notifica per dose mancata: {e}")
                    
                    except ValueError as e:
                        print(f"Errore nel parsing degli orari di medicina: {e}")
                    except Exception as e:
                        print(f"Errore nel controllo dose mancata per dispenser {dispenser.get('_id')}: {e}")
                
        return alerts
    
    # Nuovi metodi conformi all'interfaccia
    def check_reminders(self, dispenser_data, timestamp=None):
        """
        Verifica se è necessario inviare un promemoria
        """
        if not timestamp:
            timestamp = datetime.now()
            
        dispenser_id = dispenser_data.get("_id")
        
        # Logica per determinare se è necessario un promemoria
        # (adattato dal metodo _check_time_based_reminder esistente)
        
        # Verifica se è già stato inviato un promemoria di recente
        last_sent = self.last_notification_sent.get(dispenser_id)
        if last_sent and (timestamp - last_sent).total_seconds() < self.min_notification_interval:
            return False
            
        # Verifica orario di assunzione
        medicine_time = dispenser_data.get("data", {}).get("medicine_time", {})
        start_time = medicine_time.get("start")
        end_time = medicine_time.get("end")
        
        if not start_time or not end_time:
            return False
            
        try:
            # Converti gli orari in oggetti datetime
            today_str = timestamp.strftime("%Y-%m-%d")
            
            start_dt = datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{today_str} {end_time}", "%Y-%m-%d %H:%M")
            
            # Verifica l'ultima notifica inviata (ora usa timestamp completo)
            last_sent = self.last_notification_sent.get(dispenser_id)
            
            # Invia il promemoria solo se:
            # 1. Non è già stato inviato recentemente (nell'intervallo minimo)
            # 2. L'ora attuale è entro un minuto dall'inizio dell'intervallo
            time_diff = (timestamp - start_dt).total_seconds()
            
            if (not last_sent or (timestamp - last_sent).total_seconds() > self.min_notification_interval) and 0 <= time_diff <= 60:
                # Registra l'invio di questa notifica
                self.last_notification_sent[dispenser_id] = timestamp
                
                # Mantiene anche la compatibilità col vecchio sistema di tracciamento
                if dispenser_id not in self.time_based_reminders:
                    self.time_based_reminders[dispenser_id] = {}
                self.time_based_reminders[dispenser_id][today_str] = timestamp
                
                return True
                
            return False
                
        except Exception as e:
            print(f"Errore nella verifica del promemoria basato sull'orario: {e}")
            return False
            
    def send_reminder(self, dispenser_data, notification_channel):
        """
        Invia un promemoria per un dispenser
        """
        dispenser_id = dispenser_data.get("_id")
        medicine_name = dispenser_data.get("data", {}).get("medicine_name", "medicinale")
        
        # Prepara il messaggio
        message = f"1"  # O un messaggio più complesso
        
        # Usa il canale fornito dal DT
        success = notification_channel(dispenser_id, message)
        
        if success:
            # Aggiorna solo i dati locali, il DT si occuperà del database
            self.last_notification_sent[dispenser_id] = datetime.now()
            
        return success
        
    def check_adherence(self, dispenser_data, config=None):
        """
        Verifica l'aderenza alla terapia
        """
        if config is None:
            config = {"threshold": 1}
            
        # Implementa la logica per verificare l'aderenza
        # (adattato dal metodo check_adherence_irregularities)
        
        alerts = []
        # Logica per verificare l'aderenza...
        
        return alerts
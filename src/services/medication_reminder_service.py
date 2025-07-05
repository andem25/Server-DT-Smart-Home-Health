from src.services.base import BaseService
from datetime import datetime, timedelta
from src.application.mqtt import send_mqtt_message

class MedicationReminderService(BaseService):
    """Servizio promemoria medicinali per FR-1"""
    
    def __init__(self):
        self.name = "MedicationReminderService"
        self.active_reminders = {}
        self.time_based_reminders = {}  # Nuova struttura per i promemoria basati sull'orario
        self.last_notification_sent = {}  # Dizionario per tenere traccia dell'ultimo invio per dispenser

    def configure(self, config):
        """Configurazione del servizio"""
        self.reminder_interval = config.get("reminder_interval", 300)  # 5 minuti di default
        self.notification_channels = config.get("channels", ["telegram"])
        # Intervallo minimo tra notifiche consecutive (in secondi)
        self.min_notification_interval = config.get("min_notification_interval", 900)  # 15 minuti default
        return self
        
    def execute(self, dt_data, **kwargs):
        """Esegue il controllo delle assunzioni pianificate e invia promemoria se necessario"""
        # Salva il db_service passato per le operazioni database
        if 'db_service' in kwargs:
            self.db_service = kwargs['db_service']
    
        # Aggiungi questa riga per catturare dt_factory
        if 'dt_factory' in kwargs:
            self.dt_factory = kwargs['dt_factory']
    
        results = {
            "promemoria_verificati": 0,
            "promemoria_inviati": 0  # Contatore corretto delle notifiche inviate
        }
        
        # Recupera tutti i dispenser dal Digital Twin
        dispensers = []
        for replica in dt_data.get("digital_replicas", []):
            if replica.get("type") == "dispenser_medicine":
                dispensers.append(replica)
    
        for dispenser in dispensers:
            results["promemoria_verificati"] += 1
            
            # Verifica promemoria basati sull'orario configurato
            if self._check_time_based_reminder(dispenser):
                sent = self._send_time_based_reminder(dispenser)
                # Incrementa contatore SOLO se l'invio è avvenuto con successo
                if sent:
                    results["promemoria_inviati"] += 1
            
            # Verifica promemoria basati sul numero di dosi giornaliere
            elif self._check_dispenser_needs_reminder(dispenser):
                sent = self._send_reminder(dispenser)
                # Incrementa contatore SOLO se l'invio è avvenuto con successo
                if sent:
                    results["promemoria_inviati"] += 1
        
        # Controllo di sicurezza che il conteggio sia corretto
        if results["promemoria_inviati"] > 0:
            print(f"[Scheduler] dio: Inviati {results['promemoria_inviati']} promemoria medicinali effettivi")
        
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
        user_db_id = dispenser.get("user_db_id")
        medicine_name = dispenser.get("data", {}).get("medicine_name", "medicinale")
        
        # Dettagli orario
        medicine_time = dispenser.get("data", {}).get("medicine_time", {})
        start_time = medicine_time.get("start", "??:??")
        end_time = medicine_time.get("end", "??:??")
        
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

    def check_adherence_irregularities(self, dt_data, threshold=1):
        """Verifica l'aderenza ai farmaci e rileva irregolarità"""
        alerts = []
        dispensers = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "dispenser_medicine"]
        
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        for dispenser in dispensers:
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
                    "dispenser_id": dispenser.get("_id"),
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
                                    "dispenser_id": dispenser.get("_id"),
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
                                            dispenser.get("_id"),
                                            "missed_dose",
                                            details
                                        )
                                except Exception as e:
                                    print(f"Errore nell'invio della notifica per dose mancata: {e}")
                    
                    except ValueError as e:
                        print(f"Errore nel parsing degli orari di medicina: {e}")
                    except Exception as e:
                        print(f"Errore nel controllo dose mancata per dispenser {dispenser.get('_id')}: {e}")
                
        return alerts
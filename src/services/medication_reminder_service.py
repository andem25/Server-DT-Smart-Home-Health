# src/services/medication_reminder_service.py

from src.services.base import BaseService
from datetime import datetime, timedelta

class MedicationReminderService(BaseService):
    """
    Servizio unificato per la gestione dei promemoria dei farmaci.
    """
    def __init__(self):
        super().__init__()
        self.name = "MedicationReminderService"
        # Questo dizionario tiene traccia dell'ultimo orario di notifica per ogni dispenser
        # per evitare invii ripetuti. La chiave è dispenser_id, il valore è un oggetto datetime.
        self.last_notification_sent = {}
        # Intervallo minimo in secondi tra due notifiche per lo stesso dispenser (es. 1 ora)
        self.min_notification_interval_seconds = 3600

    def execute(self, dt_data, **kwargs):
        """
        Questo metodo viene chiamato dallo Scheduler attraverso il DigitalTwin.
        Delega l'orchestrazione al metodo specifico del DigitalTwin, mantenendo la compatibilità.
        """
        if 'dt_instance' in kwargs:
            kwargs['dt_instance'].execute_medication_reminders()

    def check_reminders(self, dispenser_data):
        """
        Viene chiamato dal DigitalTwin per ogni dispenser.
        Verifica se è il momento giusto per inviare un promemoria.
        Restituisce True se è ora di inviare, altrimenti False.
        """
        dispenser_id = dispenser_data.get("_id")
        medicine_time = dispenser_data.get("data", {}).get("medicine_time", {})
        start_time_str = medicine_time.get("start")  # Es: "08:00"

        if not start_time_str:
            return False  # Nessun orario impostato, non fare nulla.

        now = datetime.now()

        # 1. Controlla se abbiamo già inviato una notifica di recente
        last_sent_time = self.last_notification_sent.get(dispenser_id)
        if last_sent_time and (now - last_sent_time).total_seconds() < self.min_notification_interval_seconds:
            # Notifica già inviata meno di un'ora fa, non fare nulla.
            return False

        # 2. Controlla se siamo nell'orario giusto per l'invio
        try:
            today_str = now.strftime("%Y-%m-%d")
            start_dt = datetime.strptime(f"{today_str} {start_time_str}", "%Y-%m-%d %H:%M")

            # Invia la notifica se l'ora attuale è compresa tra l'ora di inizio
            # e un minuto dopo, per dare un margine di tolleranza allo scheduler.
            time_difference_seconds = (now - start_dt).total_seconds()
            
            if 0 <= time_difference_seconds <= 60:
                print(f"✅ [CHECK] È ora di inviare un promemoria per il dispenser {dispenser_id}.")
                return True

        except (ValueError, TypeError) as e:
            print(f"❌ ERRORE in check_reminders: formato ora non valido per {dispenser_id}. Dettagli: {e}")
            return False
            
        return False

    def send_reminder(self, dispenser_data, notification_channel):
        """
        Viene chiamato dal DigitalTwin subito dopo che check_reminders ha restituito True.
        Invia la notifica MQTT con messaggio "1" usando il canale fornito dal DigitalTwin.
        """
        dispenser_id = dispenser_data.get("_id")
        message = "1"
        
        print(f"🚀 [SEND] Tentativo di invio notifica a {dispenser_id} con messaggio '{message}'...")
        
        # Usa il canale fornito dal DT per inviare la notifica MQTT
        success = notification_channel(dispenser_id, message)
        
        if success:
            # Aggiorna l'orario dell'ultima notifica per evitare invii multipli
            self.last_notification_sent[dispenser_id] = datetime.now()
        
        return success
    
    # Puoi mantenere gli altri metodi come check_adherence_irregularities se ti servono
    # per altre funzionalità, altrimenti puoi rimuoverli per ulteriore pulizia.
    
    def check_adherence_irregularities(self, dt_data, threshold=1):
            """Verifica l'aderenza ai farmaci e rileva irregolarità. Questo metodo è chiamato dallo scheduler."""
            alerts = []
            dispensers = [dr for dr in dt_data.get("digital_replicas", []) if dr.get("type") == "dispenser_medicine"]
            
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            
            for dispenser in dispensers:
                dispenser_id = dispenser.get("_id")
                
                # NOTA: Questo blocco di codice sembra complesso e potrebbe essere semplificato in futuro,
                # ma per ora lo reintegriamo così com'è per risolvere l'errore immediatamente.
                try:
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

                    # Altra logica di controllo specifica per dosi mancate...
                    # (Questa parte è molto complessa e dipende da altri servizi come il bot e il db)
                    
                except Exception as e:
                    print(f"❌ Errore durante check_adherence_irregularities per dispenser {dispenser_id}: {e}")

            return alerts
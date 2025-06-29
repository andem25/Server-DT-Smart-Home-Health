import threading
import time
from datetime import datetime

class SchedulerService:
    """Servizio schedulatore che esegue periodicamente i servizi dei Digital Twin"""
    
    def __init__(self, dt_factory, db_service=None, interval=60):
        """
        Inizializza il servizio di scheduling
        
        Args:
            dt_factory: Factory per accedere ai Digital Twin
            db_service: Servizio database per accesso ai dati
            interval: Intervallo di esecuzione in secondi (default: 60s)
        """
        self.dt_factory = dt_factory
        self.db_service = db_service
        self.interval = interval
        self.running = False
        self.thread = None
    
    def start(self):
        """Avvia lo scheduler in un thread separato"""
        if self.running:
            print("Scheduler già in esecuzione")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler)
        self.thread.daemon = True
        self.thread.start()
        print(f"Scheduler avviato - esecuzione servizi ogni {self.interval} secondi")
    
    def stop(self):
        """Ferma lo scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            print("Scheduler fermato")
    
    def _run_scheduler(self):
        """Loop principale dello scheduler"""
        while self.running:
            try:
                self._execute_dt_services()
            except Exception as e:
                print(f"Errore nell'esecuzione dei servizi DT: {e}")
            
            # Attendi l'intervallo configurato
            time.sleep(self.interval)
    
    def _execute_dt_services(self):
        """Esegue i servizi di tutti i Digital Twin"""
        try:
            # Ottieni tutti i Digital Twin dal database
            dt_docs = self.dt_factory.list_dts()
            print(f"[Scheduler] {datetime.now().strftime('%H:%M:%S')} - Esecuzione servizi per {len(dt_docs)} Digital Twin")
            
            for dt_doc in dt_docs:
                dt_id = dt_doc.get("_id")
                dt_name = dt_doc.get("name", "Unnamed DT")
                
                try:
                    # Ottieni l'istanza del DT con tutti i suoi servizi
                    dt_instance = self.dt_factory.get_dt_instance(dt_id)
                    if not dt_instance:
                        continue
                    
                    # Esegui servizi importanti come i promemoria
                    self._execute_reminder_service(dt_instance, dt_name)
                    
                except Exception as e:
                    print(f"[Scheduler] Errore nell'esecuzione dei servizi per DT {dt_name}: {e}")
        
        except Exception as e:
            print(f"[Scheduler] Errore generale nell'esecuzione dei servizi: {e}")
    
    def _execute_reminder_service(self, dt_instance, dt_name):
        """Esegue specificamente il servizio di promemoria medicinali"""
        try:
            reminder_service = dt_instance.get_service("MedicationReminderService")
            if reminder_service:
                result = dt_instance.execute_service("MedicationReminderService")
                if result and result.get("promemoria_inviati", 0) > 0:
                    print(f"[Scheduler] {dt_name}: Inviati {result['promemoria_inviati']} promemoria medicinali")
        except Exception as e:
            print(f"[Scheduler] Errore nell'esecuzione del servizio di promemoria per {dt_name}: {e}")
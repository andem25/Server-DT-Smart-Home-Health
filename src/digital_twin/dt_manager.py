from typing import Dict, List
from src.digital_twin.core import DigitalTwin
from src.digital_twin.dt_factory import DTFactory

from src.services.database_service import DatabaseService
from datetime import datetime

class DTManager:
    """Gestore centralizzato dei Digital Twin per l'assistenza sanitaria domestica"""
    
    def __init__(self, dt_factory: DTFactory):
        self.dt_factory = dt_factory
        
    
    def register_device(self, dt_id: str, dr_type: str, device_id: str) -> None:
        """
        Registra un dispositivo fisico come Digital Replica nel Digital Twin
        
        Args:
            dt_id: ID del Digital Twin
            dr_type: Tipo di Digital Replica (es. "dispenser_medicine")
            device_id: ID del dispositivo da collegare
        """
        try:
            # Ottieni informazioni sul dispositivo - CORREZIONE: il metodo si chiama get_dr
            device = self.dt_factory.db_service.get_dr(dr_type, device_id)
            if not device:
                raise ValueError(f"Dispositivo {device_id} non trovato nel database")
                
            # Aggiungi la DR al Digital Twin
            self.dt_factory.add_digital_replica(dt_id, dr_type, device_id)
            
            print(f"Dispositivo {device_id} collegato con successo al Digital Twin {dt_id}")
            return True
        except Exception as e:
            print(f"Errore nel collegamento del dispositivo {device_id} al DT {dt_id}: {e}")
            raise
    
    def create_dispenser(self, user_id: str, dt_id: str, medicine_name: str, dosage: str = "", 
                    start_time: str = "08:00", end_time: str = "20:00", frequency: int = 1) -> str:
        """
        Crea un nuovo dispenser di medicinali e restituisce il suo ID

        Args:
            user_id: ID dell'utente proprietario
            dt_id: ID del Digital Twin a cui associare il dispenser
            medicine_name: Nome del medicinale
            dosage: Dosaggio (es. "10mg")
            start_time: Orario di inizio per l'assunzione (formato HH:MM)
            end_time: Orario di fine per l'assunzione (formato HH:MM)
            frequency: Frequenza giornaliera (quante volte al giorno va preso)

        Returns:
            str: ID della Digital Replica creata
        """
        try:
            # Struttura standardizzata del dispenser
            dispenser_data = {
                "type": "dispenser_medicine",
                "user_db_id": user_id,
                "dt_id": dt_id,
                "data": {
                    "name": f"Dispenser - {medicine_name}",
                    "medicine_name": medicine_name,
                    "dosage": dosage,
                    "medicine_time": {
                        "start": start_time,
                        "end": end_time
                    },
                    "frequency_per_day": frequency,
                    "status": "active",
                    "door_status": "closed",
                    "battery_level": 100,
                    "last_refill": datetime.now().isoformat(),
                    "location": "Casa",
                    "regularity": [],
                    "alerts": []
                }
            }

            # Crea la DR nel database
            dr_id = self.dt_factory.db_service.save_dr("dispenser_medicine", dispenser_data)
            return dr_id
        except Exception as e:
            print(f"Errore nella creazione del dispenser: {e}")
            raise
    
    def create_smart_home_health_dt(self, user_id: str, name: str, description: str = "") -> str:
        """
        Crea un Digital Twin completo per Smart Home Health con tutti i 9 requisiti funzionali
        
        Args:
            user_id: ID dell'utente proprietario
            name: Nome del Digital Twin
            description: Descrizione opzionale
            
        Returns:
            str: ID del Digital Twin creato
        """
        try:
            # Crea il Digital Twin base
            dt_id = self.dt_factory.create_dt(name=name, description=description)
            
            # WORKAROUND: Evita la notazione a punti che causa un conflitto nel factory.
            # Leggi i metadati esistenti, aggiungi l'ID utente e aggiorna l'intero oggetto.
            dt_doc = self.dt_factory.get_dt(dt_id)
            metadata = dt_doc.get("metadata", {})
            metadata['user_id'] = user_id
            metadata['active_telegram_ids'] = []  # Assicurati che questo campo sia sempre creato come array
            
            # Aggiornamento esplicito per assicurare che i metadati siano salvati correttamente
            dt_collection = self.dt_factory.db_service.db["digital_twins"]
            dt_collection.update_one(
                {"_id": dt_id}, 
                {"$set": {"metadata": metadata}}
            )
            
            print(f"DEBUG CREATE_DT: Metadata inizializzati con active_telegram_ids=[] per DT {dt_id}")

            # Lista dei servizi da aggiungere
            services_to_add = [
                # FR-1: Medication Reminder
                ("MedicationReminderService", {
                    "reminder_interval": 300,
                    "channels": ["telegram", "app_notification"]
                }),
                # FR-2: Door Open/Close Detection
                ("DoorEventService", {
                    "notification_threshold": 30
                }),
                # FR-3: Supervisor Message Display
                ("MessageDisplayService", {
                    "display_modes": ["telegram", "app", "home_display"]
                }),
                # FR-4: Adherence Logging
                ("AdherenceLoggingService", {
                    "log_frequency": "real-time",
                    "storage_duration": "90d"
                }),
                # FR-5: Irregularity Alert - RIMOSSO perché i servizi specifici gestiscono già le irregolarità
                # FR-6: Emergency Help Request
                ("EmergencyRequestService", {
                    "emergency_contacts": ["supervisor"],
                    "auto_call_threshold": 120
                }),
                # FR-7: Environmental Monitoring
                ("EnvironmentalMonitoringService", {
                    "temperature_range": [18, 28],
                    "humidity_range": [40, 60],
                    "air_quality_threshold": 50
                }),
                # FR-8: User & Supervisor Registration
                ("ProfileManagementService", {
                    "roles": ["user", "supervisor", "caregiver"],
                    "authentication": "secure"
                }),
                # FR-9: Supervisor Remote Interaction
                ("SupervisorInteractionService", {
                    "allowed_actions": ["view", "modify", "emergency_override"],
                    "access_level": "full"
                })
            ]
            
            # Aggiungi i servizi uno alla volta e gestisci eventuali errori
            successful_services = 0
            failed_services = []
            
            for service_name, config in services_to_add:
                try:
                    self.dt_factory.add_service(dt_id, service_name, config)
                    successful_services += 1
                    print(f"Servizio {service_name} aggiunto con successo al DT {dt_id}")
                except Exception as e:
                    failed_services.append((service_name, str(e)))
                    print(f"Errore nell'aggiunta del servizio {service_name}: {e}")
            
            # Registra il risultato complessivo
            if failed_services:
                print(f"Digital Twin {dt_id} creato con {successful_services} servizi. {len(failed_services)} servizi non aggiunti.")
                for service_name, err in failed_services:
                    print(f"- {service_name}: {err}")
            else:
                print(f"Digital Twin {dt_id} creato con successo con tutti i {successful_services} servizi.")
            
            return dt_id
            
        except Exception as e:
            print(f"Errore nella creazione del Digital Twin completo: {e}")
            raise
# filepath: src\services\user_service.py
import bcrypt
from src.services.database_service import DatabaseService
from src.virtualization.digital_replica.dr_factory import DRFactory
from typing import Optional, Dict, Any

class UserService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.dr_factory = DRFactory(".\\src\\virtualization\\templates\\user.yaml")

    # --- MODIFIED METHOD ---
    def create_user(self, username: str, password: str, role: str = "supervisor", dt_id: str = None) -> str:
        """
        Crea un nuovo utente.
        
        Args:
            username: Nome utente
            password: Password in chiaro
            role: Ruolo dell'utente (supervisor o patient)
            dt_id: ID del Digital Twin associato (obbligatorio per i pazienti)
        
        Returns:
            str: ID dell'utente creato
        """
        existing = self.db_service.query_drs("user", {"data.username": username})
        if existing:
            raise ValueError("Username già esistente.")
        
        # Verifica che il ruolo sia valido
        if role not in ["supervisor", "patient"]:
            raise ValueError("Ruolo non valido. Deve essere 'supervisor' o 'patient'.")
        
        # Per i pazienti, il dt_id è obbligatorio
        if role == "patient" and not dt_id:
            raise ValueError("Per i pazienti è obbligatorio specificare un Digital Twin.")

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        user_data = {
            "username": username,
            "password_hash": password_hash,
            "role": role
        }
        
        # Aggiungi dt_id solo se specificato
        if dt_id:
            user_data["dt_id"] = dt_id

        user_dr = self.dr_factory.create_dr("user", {"data": user_data})
        saved_id = self.db_service.save_dr("user", user_dr)
        return user_dr.get('_id', saved_id)

    # --- MODIFIED METHOD ---
    def verify_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verifica le credenziali dell'utente."""
        user_list = self.db_service.query_drs("user", {"data.username": username})
        if not user_list:
            return None

        user_dr = user_list[0]
        stored_hash = user_dr.get("data", {}).get("password_hash")

        if stored_hash and bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
             return user_dr

        return None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Recupera un utente dal database tramite il nome utente.
        
        Args:
            username: Nome utente da cercare
            
        Returns:
            Il digital replica dell'utente se trovato, altrimenti None
        """
        user_list = self.db_service.query_drs("user", {"data.username": username})
        if not user_list:
            return None
        
        return user_list[0]

    def verify_credentials(self, username: str, password: str) -> Optional[str]:
        """
        Verifica le credenziali dell'utente e restituisce l'ID se valide.
        
        Args:
            username: Nome utente
            password: Password in chiaro
        
        Returns:
            str: ID dell'utente se le credenziali sono valide, altrimenti None
        """
        user = self.verify_user(username, password)
        if user:
            return user.get('_id')
        return None
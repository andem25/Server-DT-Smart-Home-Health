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
    def create_user(self, username: str, password: str) -> str: # Rimosso telegram_id
        """Crea un nuovo utente."""
        existing = self.db_service.query_drs("user", {"data.username": username})
        if existing:
            raise ValueError("Username già esistente.")

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user_data = {
            "username": username,
            "password_hash": password_hash,
            # Non c'è più telegram_id da aggiungere
        }

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
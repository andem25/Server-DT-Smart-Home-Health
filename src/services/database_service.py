from typing import Dict, List, Optional, Any
from pymongo import MongoClient
from datetime import datetime
from src.virtualization.digital_replica.schema_registry import SchemaRegistry
# import timezone
from datetime import timezone

class DatabaseService:
    def __init__(
        self, connection_string: str, db_name: str, schema_registry: SchemaRegistry
    ):
        self.connection_string = connection_string
        self.db_name = db_name
        self.schema_registry = schema_registry
        self.client = None
        self.db = None

    def connect(self) -> None:
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.db_name]
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {str(e)}")

    def disconnect(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def is_connected(self) -> bool:
        return self.client is not None and self.db is not None

    def save_dr(self, dr_type: str, dr_data: Dict) -> str:
        """Save a Digital Replica"""
        if not self.is_connected():
            raise ConnectionError("Not connected to MongoDB")

        try:
            # Get collection name and validation schema from registry
            collection_name = self.schema_registry.get_collection_name(dr_type)
            validation_schema = self.schema_registry.get_validation_schema(dr_type)

            # The SchemaRegistry handles ALL validation - no type-specific logic here!
            collection = self.db[collection_name]

            result = collection.insert_one(dr_data)
            return str(dr_data["_id"])
        except Exception as e:
            raise Exception(f"Failed to save Digital Replica: {str(e)}")

    def get_dr(self, dr_type: str, dr_id: str) -> Dict:
        """
        Retrieves a Digital Replica by type and ID
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MongoDB")

        try:
            print(f"DEBUG: Retrieving DR type={dr_type}, id={dr_id}")  # Aggiungi questa linea per il debug
            collection_name = self.schema_registry.get_collection_name(dr_type)
            collection = self.db[collection_name]
            result = collection.find_one({"_id": dr_id})
            if result:
                return result
            return None
        except Exception as e:
            print(f"ERROR in get_dr: {e}")  # Aggiungi questa linea per il debug
            raise

    def query_drs(self, dr_type: str, query: Dict = None) -> List[Dict]:
        if not self.is_connected():
            raise ConnectionError("Not connected to MongoDB")

        try:
            collection_name = self.schema_registry.get_collection_name(dr_type)
            return list(self.db[collection_name].find(query or {}))
        except Exception as e:
            raise Exception(f"Failed to query Digital Replicas: {str(e)}")

    # def update_dr(self, dr_type: str, dr_id: str, update_data: Dict) -> None:
    #     if not self.is_connected():
    #         raise ConnectionError("Not connected to MongoDB")

    #     try:
    #         collection_name = self.schema_registry.get_collection_name(dr_type)

    #         # Always update metadata.updated_at
    #         if "metadata" not in update_data:
    #             update_data["metadata"] = {}
    #         update_data["metadata"]["updated_at"] = datetime.utcnow()

    #         # Let SchemaRegistry handle validation through MongoDB schema
    #         result = self.db[collection_name].update_one(
    #             {"_id": dr_id}, {"$set": update_data}
    #         )

    #         if result.matched_count == 0:
    #             raise ValueError(f"Digital Replica not found: {dr_id}")

    #     except Exception as e:
    #         raise Exception(f"Failed to update Digital Replica: {str(e)}")


    def update_dr(self, dr_type: str, dr_id: str, update_doc: Dict) -> None: # Rinominato update_data in update_doc per chiarezza
        """
        Updates a Digital Replica using atomic operators (like $set)
        or replaces the document if no operators are provided.
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to MongoDB")

        try:
            collection_name = self.schema_registry.get_collection_name(dr_type)
            collection = self.db[collection_name]

            # Determina se è un aggiornamento atomico o una sostituzione
            is_atomic_update = any(key.startswith('$') for key in update_doc)
            now = datetime.now(timezone.utc) # Usa timezone aware datetime

            if is_atomic_update:
                # Se è un aggiornamento atomico ($set, $inc, etc.), aggiungi updated_at a $set
                update_doc.setdefault("$set", {})["metadata.updated_at"] = now
            else:
                # Se è un documento di sostituzione, assicurati che metadata e updated_at siano presenti
                # Questo caso non dovrebbe verificarsi con la chiamata da update_diameter_handler,
                # ma è più robusto gestirlo.
                if "metadata" in update_doc:
                    update_doc["metadata"]["updated_at"] = now
                else:
                    # Se manca metadata nel documento di sostituzione, potresti volerlo aggiungere
                    update_doc["metadata"] = {"updated_at": now}
                    # Considera se devi aggiungere anche created_at se manca

            # Passa update_doc direttamente a update_one
            result = collection.update_one({"_id": dr_id}, update_doc)

            if result.matched_count == 0:
                # Considera di loggare o sollevare un errore se il documento non viene trovato
                # logger.warning(f"Digital Replica not found for update: {dr_id}")
                raise ValueError(f"Digital Replica not found: {dr_id}")
            # Puoi controllare result.modified_count se l'aggiornamento ha effettivamente cambiato qualcosa

        except Exception as e:
            # Rilancia un'eccezione più informativa
            # logger.error(f"Failed to update DR {dr_id}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to update Digital Replica: {e}, full error: {getattr(e, 'details', '')}") from e







    def delete_dr(self, dr_type: str, dr_id: str) -> None:
        if not self.is_connected():
            raise ConnectionError("Not connected to MongoDB")

        try:
            collection_name = self.schema_registry.get_collection_name(dr_type)
            result = self.db[collection_name].delete_one({"_id": dr_id})

            if result.deleted_count == 0:
                raise ValueError(f"Digital Replica not found: {dr_id}")
        except Exception as e:
            raise Exception(f"Failed to delete Digital Replica: {str(e)}")

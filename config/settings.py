import os
from dotenv import load_dotenv
from .config_loader import ConfigLoader # <-- Importa ConfigLoader

# Load environment variables
load_dotenv()

# Bot Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not found in .env file")

# Ngrok Configuration
NGROK_TOKEN = os.getenv("NGROK_TOKEN")
# Rimuovi l'errore se NGROK_TOKEN non è obbligatorio
if not NGROK_TOKEN:
    print("Warning: NGROK_TOKEN not found in .env file. Ngrok will not be used.")
else:
    print("NGROK_TOKEN found.")

# Server Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 88

# Webhook Configuration
WEBHOOK_PATH = "/telegram"

# --- Database Configuration ---
try:
    # Carica la configurazione dal file YAML
    db_config = ConfigLoader.load_database_config() # Usa il percorso predefinito
    # Costruisci la stringa di connessione
    DB_CONNECTION_STRING = ConfigLoader.build_connection_string(db_config)
    # Ottieni il nome del database
    DB_NAME = db_config.get("settings", {}).get("name")
    if not DB_NAME:
        raise ValueError("Database name ('name') not found in database.yaml under settings")
    print(f"Database configuration loaded: DB_NAME='{DB_NAME}'") # Log per conferma
except FileNotFoundError:
    raise ValueError("Database configuration file (database.yaml) not found.")
except ValueError as e:
    raise ValueError(f"Error in database configuration: {e}")
except Exception as e:
    raise RuntimeError(f"Failed to load database configuration: {e}")
# -----------------------------
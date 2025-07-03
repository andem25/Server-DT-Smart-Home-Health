import os
from dotenv import load_dotenv
from .config_loader import ConfigLoader # <-- Importa ConfigLoader

# Load environment variables
load_dotenv(override=True)  # Scommenta questa riga

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

MQTT_BROKER = os.getenv("MQTT_BROKER", "f1d601b5c9184556910bdc2b4e6dfe17.s1.eu.hivemq.cloud")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "test0")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "Prova12345")


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

# MQTT Topics
MQTT_TOPIC_TAKEN = os.getenv("MQTT_TOPIC_TAKEN", "taken")
MQTT_TOPIC_DOOR = os.getenv("MQTT_TOPIC_DOOR", "door")
MQTT_TOPIC_EMERGENCY = os.getenv("MQTT_TOPIC_EMERGENCY", "emergency")
MQTT_TOPIC_ENVIRONMENTAL = os.getenv("MQTT_TOPIC_ENVIRONMENTAL", "environmental_data")
MQTT_TOPIC_ASSOC = os.getenv("MQTT_TOPIC_ASSOC", "assoc")
MQTT_TOPIC_LED_STATES = os.getenv("MQTT_TOPIC_LED_STATES", "all_devices/led_states")
MQTT_TOPIC_NOTIFICATION = os.getenv("MQTT_TOPIC_NOTIFICATION", "notification")

# Debug: stampa i valori letti per verifica
print(f"MQTT Topics caricati: ASSOC={MQTT_TOPIC_ASSOC}, ENV={MQTT_TOPIC_ENVIRONMENTAL}")
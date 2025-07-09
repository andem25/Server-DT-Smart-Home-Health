import asyncio
import nest_asyncio
from flask import Flask
from pyngrok import ngrok, conf
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

# Load environment variables first
load_dotenv(override=True)



from src.application.mqtt import send_mqtt_message, MqttSubscriber
import threading
# Aggiungi dopo l'inizializzazione di mqtt_subscriber
from src.digital_twin.dt_factory import DTFactory
from src.digital_twin.dt_manager import DTManager

from src.application.bot.handlers.dt_handlers import create_dt_handler, list_dt_handler, show_dt_telegram_ids_handler, delete_dt_handler
from src.application.bot.handlers.dispenser_dt_handlers import add_dispenser_to_dt_handler, list_dt_devices_handler, check_irregularities_handler
from src.application.bot.handlers.message_handlers import send_message_to_dispenser_handler
from src.services.scheduler_service import SchedulerService


# Import configurations and handlers
from config.settings import (
    TELEGRAM_TOKEN,
    NGROK_TOKEN,
    SERVER_HOST,
    SERVER_PORT,
    WEBHOOK_PATH,
    # Assicurati che la variabile MQTT_TOPIC_ENVIRONMENTAL sia importata correttamente
    # e che le variabili MQTT_TOPIC_TEMP e MQTT_TOPIC_HUMIDITY siano rimosse o commentate
)

from src.application.bot.handlers.command_filter import restrict_patient_commands
from src.application.bot.handlers.user_handler import create_patient_handler
from src.application.bot.handlers.base_handlers import start_handler, help_handler, echo_handler
from src.application.bot.handlers.user_handler import register_handler, login_handler, logout_handler, status_handler, create_patient_handler
from src.application.bot.routes.webhook_routes import webhook, init_routes
from src.application.bot.handlers.medicine_handlers import (
    create_medicine_handler,
    list_my_medicines_handler,
    show_weekly_adherence_handler,
    set_medicine_time_handler,
    delete_dispenser_handler,  # Aggiungi questa riga
)

from src.services.database_service import DatabaseService 
from src.application.user_service import UserService
from src.virtualization.digital_replica.schema_registry import SchemaRegistry 
from config.config_loader import ConfigLoader


# Apply nest_asyncio (useful when mixing Flask and asyncio)
nest_asyncio.apply()

# Global variables for cleanup
http_tunnel = None
public_url = None

    

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.register_blueprint(webhook)
    return app

def setup_handlers(application):
    """Setup all the bot command handlers"""
    # Applica il decoratore restrict_patient_commands a tutti gli handler di comando
    
    # Base handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    
    # User management handlers
    application.add_handler(CommandHandler("register", register_handler))
    application.add_handler(CommandHandler("login", login_handler))
    application.add_handler(CommandHandler("logout", logout_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("create_patient", create_patient_handler))
    
    # Applica il filtro a tutti i comandi per limitare l'accesso dei pazienti
    # Usa un middleware per filtrare i comandi in base al ruolo dell'utente
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(
        filters.COMMAND & ~filters.Command(["start", "help", "login", "logout", "status"]),
        restrict_patient_commands(lambda update, context: update.message.reply_text(
            "❌ Come paziente, non hai accesso a questo comando."
        ))
    ), group=0)  # Gruppo 0 per dare priorità a questo handler
    
    # Dispenser handlers (rinominati da medicine)
    application.add_handler(CommandHandler("add_dispenser", create_medicine_handler))
    application.add_handler(CommandHandler("my_dispensers", list_my_medicines_handler))
    application.add_handler(CommandHandler("set_dispenser_time", set_medicine_time_handler))
    application.add_handler(CommandHandler("dispenser_adherence", show_weekly_adherence_handler))
    application.add_handler(CommandHandler("delete_dispenser", delete_dispenser_handler))  # Aggiungi questa riga
    
    # Nuovo handler per l'invio di messaggi
    application.add_handler(CommandHandler("send_dispenser_message", send_message_to_dispenser_handler))
    
    # Smart Home Health handlers (rinominati da dt)
    application.add_handler(CommandHandler("create_smart_home", create_dt_handler))
    application.add_handler(CommandHandler("list_smart_homes", list_dt_handler))
    application.add_handler(CommandHandler("link_dispenser", add_dispenser_to_dt_handler))
    application.add_handler(CommandHandler("smart_home_devices", list_dt_devices_handler))
    application.add_handler(CommandHandler("check_smart_home_alerts", check_irregularities_handler))
    application.add_handler(CommandHandler("smart_home_telegrams", show_dt_telegram_ids_handler))
    application.add_handler(CommandHandler("delete_smart_home", delete_dt_handler))  # Aggiungi questa riga
    
    # Handler per dati ambientali e eventi porta
    from src.application.bot.handlers.environmental_handlers import show_environmental_data_handler, set_environmental_limits_handler
    from src.application.bot.handlers.door_handlers import show_door_events_handler
    application.add_handler(CommandHandler("environment_data", show_environmental_data_handler))
    application.add_handler(CommandHandler("set_environment_limits", set_environmental_limits_handler))
    application.add_handler(CommandHandler("door_history", show_door_events_handler))
    
    # Echo handler (non-command messages)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler))
    

    

def main():
    global http_tunnel, public_url
    
    # Verify essential variables
    
    # Create a persistent event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create Flask app prima di usarla
    app = create_app()
    
    # Initialize bot application with persistence
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    # Utilizziamo un solo loop principale per tutte le operazioni
    application.loop = loop
    
    # Ora che app è definita, possiamo usare app.config
    app.config['TELEGRAM_BOT'] = application.bot
    app.config['TELEGRAM_LOOP'] = loop
    
    # Inizializza prima l'applicazione
    loop.run_until_complete(application.initialize())
    
    # Poi configura gli handlers
    setup_handlers(application)
    
    webhook_url = None
    if NGROK_TOKEN:
        try:
            conf.get_default().auth_token = NGROK_TOKEN
            conf.get_default().region = "eu"  # Set your region
            http_tunnel = ngrok.connect(SERVER_PORT, "http")
            public_url = http_tunnel.public_url
            webhook_url = f"{public_url}{WEBHOOK_PATH}"
        except Exception as e:
            webhook_url = f"http://{SERVER_HOST}:{SERVER_PORT}{WEBHOOK_PATH}"
    else:
        webhook_url = f"http://{SERVER_HOST}:{SERVER_PORT}{WEBHOOK_PATH}"
    
    # Set webhook
    if webhook_url:
        loop.run_until_complete(application.bot.set_webhook(webhook_url))
    else:
        return
    
    # Ora configura le routes passando l'applicazione Telegram
    init_routes(application)
    
    try:
        # Load database configuration
        db_config = ConfigLoader.load_database_config(".\\config\\database.yaml")
        connection_string = ConfigLoader.build_connection_string(db_config)
        
        # Initialize schema registry and load schemas
        schema_registry = SchemaRegistry()
        schema_registry.load_schema(
            schema_type="dispenser_medicine",
            yaml_path=".\\src\\virtualization\\templates\\dispenser_medicine.yaml"
        )
        schema_registry.load_schema(
            schema_type="user", 
            yaml_path=".\\src\\virtualization\\templates\\user.yaml"
        )
        
        # Initialize database service
        db_service = DatabaseService(
            connection_string=connection_string,
            db_name=db_config["settings"]["name"],
            schema_registry=schema_registry
        )
        db_service.connect()
        user_service = UserService(db_service)
        
        # Initialize and start MQTT subscriber
        mqtt_subscriber = MqttSubscriber(db_service=db_service, app=app)
        mqtt_subscriber.start()
        
        # Store services in both Flask app config and Telegram bot data
        app.config['DB_SERVICE'] = db_service
        app.config['USER_SERVICE'] = user_service
        app.config['MQTT_SUBSCRIBER'] = mqtt_subscriber
        dt_factory = DTFactory(db_service, schema_registry)
        dt_manager = DTManager(dt_factory)
        
        # Collega MQTT_SUBSCRIBER con DTFactory
        mqtt_subscriber.set_dt_factory(dt_factory)
        
        # Memorizza configurazioni in modo coerente e rimuovi il doppio loop
        app.config['DT_FACTORY'] = dt_factory
        app.config['DT_MANAGER'] = dt_manager
        application.bot_data['dt_factory'] = dt_factory
        application.bot_data['dt_manager'] = dt_manager
        
        # Memorizza configurazioni in modo coerente e rimuovi il doppio loop
        application.bot_data['db_service'] = db_service
        application.bot_data['user_service'] = user_service
        application.bot_data['schema_registry'] = schema_registry

        # Inizializza e avvia lo scheduler dei servizi DT
        scheduler_service = SchedulerService(dt_factory, db_service, interval=60)  # Aumenta a 60 secondi
        scheduler_service.start()
        
        # Memorizza lo scheduler nella configurazione dell'app
        app.config['SCHEDULER_SERVICE'] = scheduler_service
    
    except Exception as e:
        if db_service and hasattr(db_service, 'is_connected') and db_service.is_connected():
            db_service.disconnect()
        if http_tunnel and public_url:
            ngrok.disconnect(public_url)
            ngrok.kill()
        return
    
    # Run Flask app
    try:
        print(f"Starting Flask server on {SERVER_HOST}:{SERVER_PORT}")
        app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)
        
    except KeyboardInterrupt:
        # Shutdown Telegram application
        print("Shutting down Telegram application...")
        try:
            loop.run_until_complete(application.stop())
            loop.run_until_complete(application.shutdown())
            print("Telegram application shut down.")
        except Exception as e:
            print(f"Error shutting down Telegram application: {repr(e)}")
        
        # Close database connection
        if db_service and hasattr(db_service, 'is_connected') and db_service.is_connected():
            print("Closing database connection...")
            db_service.disconnect()
            print("Database connection closed.")
        
        # Close event loop
        if loop.is_running():
            print("Stopping event loop...")
            loop.call_soon_threadsafe(loop.stop)
            print("Event loop stopped.")
        loop.close()
        
        
        if 'mqtt_subscriber' in locals() and mqtt_subscriber:
            mqtt_subscriber.stop()
        if hasattr(app.config, 'MQTT_SUBSCRIBER') and app.config['MQTT_SUBSCRIBER']:
            print("Stopping MQTT subscriber...")
            app.config['MQTT_SUBSCRIBER'].stop()
            print("MQTT subscriber stopped.")
            
        # Arresta anche lo scheduler
        if 'scheduler_service' in locals() and scheduler_service:
            print("Stopping DT service scheduler...")
            scheduler_service.stop()
            print("DT service scheduler stopped.")
            
        
        
        # Disconnect ngrok
        if http_tunnel and public_url:
            print("Disconnecting ngrok tunnel...")
            try:
                ngrok.disconnect(public_url)
                print("ngrok tunnel disconnected.")
            except Exception as e:
                print(f"Error disconnecting ngrok: {repr(e)}")
            try:
                ngrok.kill()
                print("ngrok process terminated.")
            except Exception as e:
                print(f"Error terminating ngrok process: {repr(e)}")
        
        print("Cleanup completed.")

if __name__ == "__main__":
    main()
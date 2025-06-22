import asyncio
import nest_asyncio
from flask import Flask
from pyngrok import ngrok, conf
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
from src.services.mqtt.mqtt_service import send_mqtt_message, MqttSubscriber
import threading
# Aggiungi dopo l'inizializzazione di mqtt_subscriber
from src.digital_twin.dt_factory import DTFactory
from src.digital_twin.dt_manager import DTManager

from src.application.bot.handlers.dt_handlers import create_dt_handler, list_dt_handler
from src.application.bot.handlers.dispenser_dt_handlers import add_dispenser_to_dt_handler, list_dt_devices_handler

# Load environment variables first
load_dotenv()

# Import configurations and handlers
from config.settings import (
    TELEGRAM_TOKEN,
    NGROK_TOKEN,
    SERVER_HOST,
    SERVER_PORT,
    WEBHOOK_PATH,
)
from src.application.bot.handlers.base_handlers import start_handler, help_handler, echo_handler
from src.application.bot.handlers.user_handler import register_handler, login_handler, logout_handler, status_handler
from src.application.bot.routes.webhook_routes import webhook, init_routes
from src.application.bot.handlers.medicine_handlers import (
    create_medicine_handler,
    list_my_medicines_handler,
    set_interval_handler,
    show_regularity_handler,
)

from src.services.database_service import DatabaseService 
from src.services.user_service import UserService
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
    # Base handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    
    # User management handlers
    application.add_handler(CommandHandler("register", register_handler))
    application.add_handler(CommandHandler("login", login_handler))
    application.add_handler(CommandHandler("logout", logout_handler))
    application.add_handler(CommandHandler("status", status_handler))
    
    # Medicine handlers
    application.add_handler(CommandHandler("add_medicine", create_medicine_handler))
    application.add_handler(CommandHandler("my_medicines", list_my_medicines_handler))
    application.add_handler(CommandHandler("set_interval", set_interval_handler))
    application.add_handler(CommandHandler("regularity", show_regularity_handler))
    
    # Digital Twin handlers
    application.add_handler(CommandHandler("create_dt", create_dt_handler))
    application.add_handler(CommandHandler("list_dt", list_dt_handler))
    application.add_handler(CommandHandler("add_dispenser_dt", add_dispenser_to_dt_handler))
    application.add_handler(CommandHandler("dt_devices", list_dt_devices_handler))
    
    # Echo handler (non-command messages)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_handler))
    

    

def main():
    global http_tunnel, public_url
    
    # Verify essential variables
    
    # Create a persistent event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    
    # Initialize bot application with persistence (RIMUOVI LA DUPLICAZIONE)
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.loop = loop  # Store loop reference for webhook routes
    
    
        
    application.telegram_loop = asyncio.new_event_loop()
    
    
    # Inizializza prima l'applicazione
    loop.run_until_complete(application.initialize())
    
    # Poi configura gli handlerss
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
    
    # Create Flask app
    app = create_app()
    init_routes(application)  # Pass the telegram application to the routes
    
    
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
        
        # Memorizza nelle configurazioni
        app.config['DT_FACTORY'] = dt_factory
        app.config['DT_MANAGER'] = dt_manager
        application.bot_data['dt_factory'] = dt_factory
        application.bot_data['dt_manager'] = dt_manager
        
        app.config["TELEGRAM_LOOP"] = application.telegram_loop
        
        
        
        # IMPORTANT: Store services in application.bot_data for Telegram handlers
        application.bot_data['db_service'] = db_service
        application.bot_data['user_service'] = user_service
        application.bot_data['schema_registry'] = schema_registry
        threading.Thread(target=application.telegram_loop.run_forever, daemon=True).start()
        
        app.config['TELEGRAM_BOT'] = application.bot
        print(f"🚀 Loop Telegram INSIDE attivo? {application.telegram_loop.is_running()}")

        
    
    except Exception as e:
        # print(f"Error during service initialization: {repr(e)}", exc_info=True)
        # Clean up resources before exiting
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
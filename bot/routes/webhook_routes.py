from flask import Blueprint, request
from telegram import Update
webhook = Blueprint("webhook", __name__)
application = None

def init_routes(app):
    """Initialize the routes with the Telegram application instance"""
    global application
    application = app

@webhook.route("/telegram", methods=["POST"])
def telegram_webhook():
    """Webhook endpoint for receiving updates from Telegram"""
    if request.method == "POST":
        update = Update.de_json(request.get_json(), application.bot)
        application.loop.run_until_complete(application.process_update(update))
    return "OK"

@webhook.route("/")
def index():
    """Root endpoint to check if the bot is active"""
    return "Bot is up and running!"
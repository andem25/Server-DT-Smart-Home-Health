from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import numpy as np
import matplotlib.dates as mdates
import re

async def show_door_events_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mostra gli eventi di apertura/chiusura della porta di un dispenser
    Uso:
        /door_events <dispenser_id> - Mostra gli ultimi 100 eventi
        /door_events <dispenser_id> <n> - Mostra gli ultimi n eventi (es: /door_events disp123 50)
        /door_events <dispenser_id> <data_inizio> <data_fine> - Mostra gli eventi in un intervallo specifico
                  (formato data: YYYY-MM-DD o DD-MM-YYYY)
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return
    
    # Verifica che sia fornito almeno l'ID del dispenser
    if len(context.args) < 1:
        await update.message.reply_text(
            "❗ **Uso corretto:**\n"
            "• `/door_events <dispenser_id>` - Mostra gli ultimi 100 eventi\n"
            "• `/door_events <dispenser_id> <n>` - Mostra gli ultimi n eventi\n"
            "• `/door_events <dispenser_id> <data_inizio> <data_fine>` - Mostra gli eventi in un intervallo\n\n"
            "📅 Formato data: YYYY-MM-DD o DD-MM-YYYY",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    dispenser_id = context.args[0]
    db_service = context.application.bot_data['db_service']
    
    # Verifica che l'utente abbia accesso a questo dispenser
    dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
    if not dispenser or dispenser.get("user_db_id") != user_db_id:
        await update.message.reply_text("❌ Dispenser non trovato o non hai i permessi per accedervi.")
        return
    
    # Recupera il nome del dispenser
    dispenser_name = dispenser.get("data", {}).get("name", f"Dispenser {dispenser_id}")
    
    # Ottieni i dati sugli eventi della porta
    door_events = dispenser.get("data", {}).get("door_events", [])
    if not door_events:
        await update.message.reply_text(f"ℹ️ Nessun evento di apertura/chiusura registrato per '{dispenser_name}'.")
        return
    
    # Gestione parametri aggiuntivi (numero di eventi o intervallo date)
    limit = 100  # Valore predefinito
    start_date = None
    end_date = None
    filter_message = "ultimi 100 eventi"
    
    if len(context.args) == 2:
        # Potrebbe essere un numero o una data
        try:
            limit = int(context.args[1])
            filter_message = f"ultimi {limit} eventi"
        except ValueError:
            # Prova a interpretarlo come data
            try:
                start_date = parse_date(context.args[1])
                end_date = datetime.now()
                filter_message = f"eventi dal {start_date.strftime('%d/%m/%Y')} a oggi"
            except ValueError:
                await update.message.reply_text("❌ Formato non valido. Usa un numero o una data (DD-MM-YYYY o YYYY-MM-DD).")
                return
    
    elif len(context.args) >= 3:
        # Dovrebbero essere due date
        try:
            start_date = parse_date(context.args[1])
            end_date = parse_date(context.args[2])
            filter_message = f"eventi dal {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}"
        except ValueError:
            await update.message.reply_text("❌ Formato date non valido. Usa DD-MM-YYYY o YYYY-MM-DD.")
            return
    
    # Converti le stringhe ISO in datetime objects per ordinamento e filtraggio
    for event in door_events:
        if isinstance(event.get("timestamp"), str):
            try:
                event["datetime"] = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
            except ValueError:
                # Fallback se il formato non è ISO
                try:
                    event["datetime"] = datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
                except:
                    event["datetime"] = datetime.now()  # Valore di fallback
        else:
            event["datetime"] = datetime.now()
    
    # Ordina per timestamp
    door_events.sort(key=lambda x: x["datetime"])
    
    # Filtra in base ai parametri
    if start_date and end_date:
        door_events = [e for e in door_events if start_date <= e["datetime"] <= end_date]
    
    # Limita il numero di eventi
    door_events = door_events[-limit:]
    
    if not door_events:
        await update.message.reply_text(f"ℹ️ Nessun evento trovato per '{dispenser_name}' con i filtri specificati.")
        return
    
    # Prepara il messaggio di testo con i dati sommari
    msg = f"🚪 *Eventi Porta - {dispenser_name}*\n\n"
    
    # Analisi degli eventi
    open_count = sum(1 for e in door_events if e.get("state") == "open")
    closed_count = sum(1 for e in door_events if e.get("state") == "closed")
    
    msg += f"📊 *Statistiche:*\n"
    msg += f"  • Aperture: {open_count}\n"
    msg += f"  • Chiusure: {closed_count}\n"
    
    if door_events:
        first_event = door_events[0]["datetime"].strftime("%d/%m/%Y %H:%M:%S")
        last_event = door_events[-1]["datetime"].strftime("%d/%m/%Y %H:%M:%S")
        msg += f"  • Periodo: dal {first_event} al {last_event}\n"
    
    msg += f"\n*{filter_message}*"
    
    # Invia il messaggio di testo
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    # Genera e invia il grafico se ci sono dati sufficienti
    if len(door_events) > 1:
        # Notifica l'utente che stiamo generando il grafico
        chart_msg = await update.message.reply_text("⏳ Generazione grafico in corso...")
        
        try:
            # Crea il grafico
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.suptitle(f'Eventi Porta - {dispenser_name}', fontsize=16)
            
            # Prepara dati per il grafico
            times = [e["datetime"] for e in door_events]
            states = [1 if e.get("state") == "open" else 0 for e in door_events]
            
            # Crea il grafico a barre verticali
            ax.stem(times, states, basefmt=' ', linefmt='b-', markerfmt='bo')
            ax.set_yticks([0, 1])
            ax.set_yticklabels(['Chiusa', 'Aperta'])
            ax.set_xlabel('Orario')
            ax.set_title('Stato Porta')
            ax.grid(True)
            
            # Formattazione asse x
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M\n%d/%m'))
            plt.gcf().autofmt_xdate(rotation=0, ha='center')
            
            # Salva il grafico in un buffer di memoria
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            
            # Invia il grafico
            await update.message.reply_photo(photo=InputFile(buf, 'door_events.png'))
            await chart_msg.delete()
            
        except Exception as e:
            await chart_msg.edit_text(f"❌ Errore nella generazione del grafico: {str(e)}")
            print(f"Errore nel grafico: {e}")

def parse_date(date_str):
    """Funzione helper per parsare le date in vari formati"""
    date_formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Se siamo qui, nessun formato ha funzionato
    raise ValueError(f"Formato data non valido: {date_str}")
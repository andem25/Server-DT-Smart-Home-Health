from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import numpy as np
import matplotlib.dates as mdates
import re
import matplotlib.patches as mpatches

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
    
    # Ottieni medicine_time per riferimento
    medicine_time = dispenser.get("data", {}).get("medicine_time", {})
    if medicine_time:
        start_time = medicine_time.get("start", "non impostato")
        end_time = medicine_time.get("end", "non impostato")
        msg += f"⏰ *Orario assunzione configurato:* {start_time} - {end_time}\n\n"
    
    # Analisi degli eventi
    open_count = sum(1 for e in door_events if e.get("state") == "open")
    closed_count = sum(1 for e in door_events if e.get("state") == "closed")
    
    # Conteggio eventi regolari e irregolari
    regular_count = sum(1 for e in door_events if e.get("regularity") == "regular")
    irregular_count = len(door_events) - regular_count
    
    msg += f"📊 *Statistiche:*\n"
    msg += f"  • Aperture: {open_count}\n"
    msg += f"  • Chiusure: {closed_count}\n"
    msg += f"  • Eventi regolari: {regular_count} ✅\n"
    msg += f"  • Eventi irregolari: {irregular_count} ⚠️\n"
    
    if door_events:
        first_event = door_events[0]["datetime"].strftime("%d/%m/%Y %H:%M:%S")
        last_event = door_events[-1]["datetime"].strftime("%d/%m/%Y %H:%M:%S")
        msg += f"  • Periodo: dal {first_event} al {last_event}\n"
    
    msg += f"\n*{filter_message}*"
    
    # Aggiungi la tabella degli ultimi 10 eventi
    if door_events:
        msg += "\n\n*Ultimi eventi:*\n"
        last_events = door_events[-10:]  # Mostra solo gli ultimi 10 per evitare messaggi troppo lunghi
        
        for i, event in enumerate(last_events):
            state = "🔓 Apertura" if event.get("state") == "open" else "🔒 Chiusura"
            time_str = event["datetime"].strftime("%H:%M:%S")
            date_str = event["datetime"].strftime("%d/%m/%Y")
            
            # Mostra la regolarità con emoji
            is_regular = event.get("regularity") == "regular"
            reg_emoji = "✅" if is_regular else "⚠️"
            
            msg += f"{i+1}. {state} {reg_emoji} - {date_str} {time_str}\n"
    
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
            
            # Aggiungi linea per l'intervallo di tempo configurato se disponibile
            if medicine_time and medicine_time.get("start") and medicine_time.get("end"):
                start_time = medicine_time.get("start")
                end_time = medicine_time.get("end")
                
                # Crea rettangolo che rappresenta l'intervallo di tempo corretto
                today = datetime.now().strftime("%Y-%m-%d")
                start_dt = datetime.strptime(f"{today} {start_time}", "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(f"{today} {end_time}", "%Y-%m-%d %H:%M")
                
                # Estendi l'intervallo a tutti i giorni nel grafico
                for event in door_events:
                    event_date = event["datetime"].strftime("%Y-%m-%d")
                    event_time = event["datetime"].strftime("%H:%M")
                    
                    # Crea datetime per questo giorno con orario di inizio e fine
                    day_start = datetime.strptime(f"{event_date} {start_time}", "%Y-%m-%d %H:%M")
                    day_end = datetime.strptime(f"{event_date} {end_time}", "%Y-%m-%d %H:%M")
                    
                    # Aggiungi rettangolo evidenziato per questo giorno
                    ax.axvspan(day_start, day_end, alpha=0.2, color='green', label='Orario regolare')
            
            # Separa eventi regolari e irregolari per diversa visualizzazione
            regular_opens = [e["datetime"] for e in door_events if e.get("state") == "open" and e.get("regularity") == "regular"]
            regular_closes = [e["datetime"] for e in door_events if e.get("state") == "closed" and e.get("regularity") == "regular"]
            
            irregular_opens = [e["datetime"] for e in door_events if e.get("state") == "open" and e.get("regularity") != "regular"]
            irregular_closes = [e["datetime"] for e in door_events if e.get("state") == "closed" and e.get("regularity") != "regular"]
            
            # Crea il grafico con colori diversi per eventi regolari e irregolari
            # Plot eventi regolari
            if regular_opens:
                ax.stem(regular_opens, [1] * len(regular_opens), linefmt='g-', markerfmt='go', basefmt=" ", label='Aperture regolari')
            if regular_closes:
                ax.stem(regular_closes, [0] * len(regular_closes), linefmt='b-', markerfmt='bo', basefmt=" ", label='Chiusure regolari')
                
            # Plot eventi irregolari
            if irregular_opens:
                ax.stem(irregular_opens, [1] * len(irregular_opens), linefmt='r-', markerfmt='ro', basefmt=" ", label='Aperture irregolari')
            if irregular_closes:
                ax.stem(irregular_closes, [0] * len(irregular_closes), linefmt='r-', markerfmt='rs', basefmt=" ", label='Chiusure irregolari')
            
            # Configurazione asse y
            ax.set_yticks([0, 1])
            ax.set_yticklabels(['Chiusa', 'Aperta'])
            ax.set_xlabel('Orario')
            ax.set_title('Stato Porta')
            ax.grid(True)
            
            # Crea legenda manualmente per evitare duplicati
            legend_elements = [
                mpatches.Patch(color='green', alpha=0.2, label='Orario regolare assunzione'),
                plt.Line2D([0], [0], marker='o', color='g', label='Apertura regolare', markerfacecolor='g'),
                plt.Line2D([0], [0], marker='o', color='b', label='Chiusura regolare', markerfacecolor='b'),
                plt.Line2D([0], [0], marker='o', color='r', label='Apertura irregolare', markerfacecolor='r'),
                plt.Line2D([0], [0], marker='s', color='r', label='Chiusura irregolare', markerfacecolor='r')
            ]
            ax.legend(handles=legend_elements, loc='upper right')
            
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
            import traceback
            traceback.print_exc()

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
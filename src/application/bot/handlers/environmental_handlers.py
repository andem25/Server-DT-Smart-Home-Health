from telegram import Update, InputFile
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import numpy as np
import matplotlib.dates as mdates
import re

async def show_environmental_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mostra i dati ambientali (temperatura e umidità) di un dispenser
    Uso:
        /env_data <dispenser_id> - Mostra gli ultimi 100 valori
        /env_data <dispenser_id> <n> - Mostra gli ultimi n valori (es: /env_data disp123 50)
        /env_data <dispenser_id> <data_inizio> <data_fine> - Mostra i dati in un intervallo specifico
                   (formato data: YYYY-MM-DD o DD-MM-YYYY)
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return
    
    # Verifica che sia fornito almeno l'ID del dispenser
    if len(context.args) < 1:
        await update.message.reply_text(
            "❗ Uso: `/env_data <dispenser_id> [numero_valori|data_inizio data_fine]`\n\n"
            "Esempi:\n"
            "- `/env_data disp123` - Mostra gli ultimi 100 valori\n"
            "- `/env_data disp123 50` - Mostra gli ultimi 50 valori\n"
            "- `/env_data disp123 2023-06-20 2023-06-27` - Mostra i dati nell'intervallo specificato\n\n"
            "Usa `/my_medicines` per vedere i tuoi dispensers disponibili.", 
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    dispenser_id = context.args[0]
    
    # Parametri opzionali per il numero di valori o intervallo di date
    num_values = 100  # Default: ultimi 100 valori
    start_date = None
    end_date = None
    
    # Analisi parametri aggiuntivi
    if len(context.args) == 2:
        # Caso in cui è specificato solo il numero di valori
        try:
            num_values = int(context.args[1])
            if num_values <= 0:
                await update.message.reply_text("❌ Il numero di valori deve essere positivo.")
                return
        except ValueError:
            await update.message.reply_text("❌ Il secondo parametro deve essere un numero intero positivo.")
            return
    
    elif len(context.args) >= 3:
        # Caso in cui è specificato un intervallo di date
        try:
            date_formats = ["%Y-%m-%d", "%d-%m-%Y"]
            
            # Prova i formati di data supportati
            for date_format in date_formats:
                try:
                    start_date = datetime.strptime(context.args[1], date_format).date()
                    end_date = datetime.strptime(context.args[2], date_format).date()
                    
                    # Se le date sono invertite, le scambia
                    if start_date > end_date:
                        start_date, end_date = end_date, start_date
                        
                    # Aggiungi un giorno alla end_date per includere tutti i dati di quel giorno
                    end_date = end_date + timedelta(days=1)
                    break
                except ValueError:
                    continue
            
            if not start_date or not end_date:
                await update.message.reply_text(
                    "❌ Formato data non valido. Usa YYYY-MM-DD o DD-MM-YYYY."
                )
                return
                
        except Exception as e:
            await update.message.reply_text(f"❌ Errore nell'analisi delle date: {e}")
            return
    
    try:
        # Ottieni i servizi necessari
        db_service = context.application.bot_data.get('db_service')
        if not db_service:
            await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
            return
        
        # Ottieni il dispenser
        dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
        if not dispenser:
            await update.message.reply_text(f"❌ Dispenser con ID `{dispenser_id}` non trovato.")
            return
        
        if dispenser.get("user_db_id") != user_db_id:
            await update.message.reply_text("❌ Non sei autorizzato a visualizzare questo dispenser.")
            return
        
        # Ottieni i dati ambientali
        env_data = dispenser.get("data", {}).get("environmental_data", [])
        dispenser_name = dispenser.get("data", {}).get("name", dispenser_id)
        
        if not env_data:
            await update.message.reply_text(f"ℹ️ Nessun dato ambientale disponibile per '{dispenser_name}' (ID: `{dispenser_id}`).")
            return
        
        # Filtra per tipo
        temp_data = [m for m in env_data if m.get("type") == "temperature"]
        humidity_data = [m for m in env_data if m.get("type") == "humidity"]
        
        # Converti le stringhe ISO in datetime objects per ordinamento e filtraggio
        for data_list in [temp_data, humidity_data]:
            for item in data_list:
                if isinstance(item.get("timestamp"), str):
                    try:
                        item["datetime"] = datetime.fromisoformat(item["timestamp"].replace('Z', '+00:00'))
                    except ValueError:
                        # Fallback se il formato non è ISO
                        try:
                            item["datetime"] = datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")
                        except:
                            item["datetime"] = datetime.now()  # Valore di fallback
                else:
                    item["datetime"] = datetime.now()
        
        # Ordina per timestamp
        temp_data.sort(key=lambda x: x.get("datetime", datetime.now()))
        humidity_data.sort(key=lambda x: x.get("datetime", datetime.now()))
        
        # Filtra per intervallo di date se specificato
        if start_date and end_date:
            temp_data = [m for m in temp_data if start_date <= m.get("datetime").date() < end_date]
            humidity_data = [m for m in humidity_data if start_date <= m.get("datetime").date() < end_date]
            filter_message = f"Filtraggio per intervallo: dal {start_date.strftime('%d/%m/%Y')} al {(end_date - timedelta(days=1)).strftime('%d/%m/%Y')}"
        else:
            # Altrimenti prendi gli ultimi N valori
            temp_data = temp_data[-num_values:] if len(temp_data) > num_values else temp_data
            humidity_data = humidity_data[-num_values:] if len(humidity_data) > num_values else humidity_data
            filter_message = f"Mostrando gli ultimi {min(num_values, len(temp_data))} valori di temperatura e {min(num_values, len(humidity_data))} di umidità"
        
        # Prepara il messaggio
        msg = f"📊 *Dati ambientali per '{dispenser_name}'*\n\n"
        
        # Ultima temperatura
        if temp_data:
            last_temp = temp_data[-1]
            temp_value = last_temp.get("value", "N/A")
            temp_time = last_temp.get("datetime").strftime("%d/%m/%Y %H:%M:%S")
            msg += f"🌡️ *Temperatura*: {temp_value}°C (aggiornata: {temp_time})\n"
        else:
            msg += "🌡️ *Temperatura*: Dati non disponibili\n"
        
        # Ultima umidità
        if humidity_data:
            last_humidity = humidity_data[-1]
            humidity_value = last_humidity.get("value", "N/A")
            humidity_time = last_humidity.get("datetime").strftime("%d/%m/%Y %H:%M:%S")
            msg += f"💧 *Umidità*: {humidity_value}% (aggiornata: {humidity_time})\n\n"
        else:
            msg += "💧 *Umidità*: Dati non disponibili\n\n"
        
        # Statistiche sui dati
        if temp_data:
            temp_values = [m.get("value", 0) for m in temp_data if isinstance(m.get("value"), (int, float))]
            if temp_values:
                avg_temp = sum(temp_values) / len(temp_values)
                min_temp = min(temp_values)
                max_temp = max(temp_values)
                msg += f"📈 *Statistiche Temperatura*:\n"
                msg += f"  • Media: {avg_temp:.1f}°C\n"
                msg += f"  • Min: {min_temp:.1f}°C (in questo periodo)\n"
                msg += f"  • Max: {max_temp:.1f}°C (in questo periodo)\n"
        
        if humidity_data:
            humidity_values = [m.get("value", 0) for m in humidity_data if isinstance(m.get("value"), (int, float))]
            if humidity_values:
                avg_humidity = sum(humidity_values) / len(humidity_values)
                min_humidity = min(humidity_values)
                max_humidity = max(humidity_values)
                msg += f"\n📊 *Statistiche Umidità*:\n"
                msg += f"  • Media: {avg_humidity:.1f}%\n"
                msg += f"  • Min: {min_humidity:.1f}% (in questo periodo)\n"
                msg += f"  • Max: {max_humidity:.1f}% (in questo periodo)\n"
        
        msg += f"\n*{filter_message}*"
        
        # Invia il messaggio di testo
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        
        # Genera e invia il grafico se ci sono dati sufficienti
        if (len(temp_data) > 1 or len(humidity_data) > 1):
            # Notifica l'utente che stiamo generando il grafico
            chart_msg = await update.message.reply_text("⏳ Generazione grafico in corso...")
            
            # Ottieni i limiti personalizzati
            custom_temp_limits = dispenser.get("data", {}).get("temperature_limits", [18.0, 30.0])
            custom_humidity_limits = dispenser.get("data", {}).get("humidity_limits", [30.0, 70.0])
            
            # Crea il grafico
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
            fig.suptitle(f'Dati Ambientali - {dispenser_name}', fontsize=16)
            
            # Plot temperatura
            if len(temp_data) > 1:
                temp_times = [m.get("datetime") for m in temp_data]
                temp_values = [m.get("value") for m in temp_data]
                ax1.plot(temp_times, temp_values, 'r-', label='Temperatura')
                ax1.set_ylabel('Temperatura (°C)')
                ax1.set_title('Temperatura')
                ax1.grid(True)
                
                # Aggiungi linee orizzontali per i limiti personalizzati
                ax1.axhline(y=custom_temp_limits[0], color='blue', linestyle='--', alpha=0.7, 
                          label=f'Min ({custom_temp_limits[0]}°C)')
                ax1.axhline(y=custom_temp_limits[1], color='red', linestyle='--', alpha=0.7, 
                          label=f'Max ({custom_temp_limits[1]}°C)')
                ax1.legend()
            
            # Plot umidità
            if len(humidity_data) > 1:
                hum_times = [m.get("datetime") for m in humidity_data]
                hum_values = [m.get("value") for m in humidity_data]
                ax2.plot(hum_times, hum_values, 'b-', label='Umidità')
                ax2.set_ylabel('Umidità (%)')
                ax2.set_xlabel('Data/Ora')
                ax2.set_title('Umidità')
                ax2.grid(True)
                
                # Aggiungi linee orizzontali per i limiti personalizzati
                ax2.axhline(y=custom_humidity_limits[0], color='blue', linestyle='--', alpha=0.7, 
                          label=f'Min ({custom_humidity_limits[0]}%)')
                ax2.axhline(y=custom_humidity_limits[1], color='red', linestyle='--', alpha=0.7, 
                          label=f'Max ({custom_humidity_limits[1]}%)')
                ax2.legend()
            
            # Formatta l'asse x per mostrare date/ore in modo leggibile
            fig.autofmt_xdate()
            plt.gcf().autofmt_xdate()
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
            
            # Aggiungi una griglia secondaria per migliorare la leggibilità
            ax1.grid(which='minor', alpha=0.2)
            ax2.grid(which='minor', alpha=0.2)
            
            plt.tight_layout()
            
            # Salva il grafico in un buffer di memoria
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            
            # Chiudi la figura per liberare memoria
            plt.close(fig)
            
            # Invia il grafico
            await update.message.reply_photo(
                photo=buf,
                caption=f"📊 Grafico dati ambientali per '{dispenser_name}'\n{filter_message}"
            )
            
            # Elimina il messaggio di caricamento
            await chart_msg.delete()
            
        else:
            await update.message.reply_text("ℹ️ Dati insufficienti per generare un grafico.")
        
    except Exception as e:
        print(f"Errore in show_environmental_data_handler: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Si è verificato un errore durante il recupero dei dati ambientali: {e}")

async def set_environmental_limits_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Imposta limiti personalizzati per temperatura e umidità di un dispenser.
    
    Uso:
        /set_env_limits <dispenser_id> temp <min> <max> - Imposta limiti di temperatura
        /set_env_limits <dispenser_id> humidity <min> <max> - Imposta limiti di umidità
    """
    user_db_id = context.user_data.get('user_db_id')
    if not user_db_id:
        await update.message.reply_text("❌ Devi prima effettuare il login con /login <username> <password>.")
        return
        
    # Verifica che siano forniti tutti i parametri necessari
    if len(context.args) < 4:
        await update.message.reply_text(
            "❗ Uso: \n"
            "- `/set_env_limits <dispenser_id> temp <min> <max>` - per impostare limiti di temperatura\n"
            "- `/set_env_limits <dispenser_id> humidity <min> <max>` - per impostare limiti di umidità\n\n"
            "Esempi:\n"
            "- `/set_env_limits disp123 temp 18 30` - imposta temperatura tra 18°C e 30°C\n"
            "- `/set_env_limits disp123 humidity 30 70` - imposta umidità tra 30% e 70%",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    dispenser_id = context.args[0]
    limit_type = context.args[1].lower()
    
    # Verifica che il tipo sia valido
    if limit_type not in ["temp", "temperatura", "temperature", "humidity", "umidità", "umidita"]:
        await update.message.reply_text(
            "❌ Tipo di limite non valido. Usa 'temp' per temperatura o 'humidity' per umidità."
        )
        return
        
    # Normalizza i tipi
    if limit_type in ["temperatura", "temperature"]:
        limit_type = "temp"
    elif limit_type in ["umidità", "umidita"]:
        limit_type = "humidity"
        
    # Controlla i valori min e max
    try:
        min_value = float(context.args[2])
        max_value = float(context.args[3])
        
        if min_value >= max_value:
            await update.message.reply_text("❌ Il valore minimo deve essere inferiore al valore massimo.")
            return
            
        # Controlli specifici per temperatura e umidità
        if limit_type == "temp":
            if min_value < -10 or min_value > 40:
                await update.message.reply_text("⚠️ Il valore minimo di temperatura dovrebbe essere tra -10°C e 40°C.")
                return
            if max_value < 0 or max_value > 50:
                await update.message.reply_text("⚠️ Il valore massimo di temperatura dovrebbe essere tra 0°C e 50°C.")
                return
                
        elif limit_type == "humidity":
            if min_value < 0 or min_value > 100:
                await update.message.reply_text("⚠️ Il valore minimo di umidità deve essere tra 0% e 100%.")
                return
            if max_value < 0 or max_value > 100:
                await update.message.reply_text("⚠️ Il valore massimo di umidità deve essere tra 0% e 100%.")
                return
                
    except ValueError:
        await update.message.reply_text("❌ I valori minimo e massimo devono essere numeri.")
        return
        
    try:
        # Ottieni i servizi necessari
        db_service = context.application.bot_data.get('db_service')
        if not db_service:
            await update.message.reply_text("❌ Errore interno: Servizi non disponibili.")
            return
            
        # Ottieni il dispenser
        dispenser = db_service.get_dr("dispenser_medicine", dispenser_id)
        if not dispenser:
            await update.message.reply_text(f"❌ Dispenser con ID `{dispenser_id}` non trovato.")
            return
            
        if dispenser.get("user_db_id") != user_db_id:
            await update.message.reply_text("❌ Non sei autorizzato a modificare questo dispenser.")
            return
            
        # Prepara l'aggiornamento
        update_field = None
        limit_name = None
        
        if limit_type == "temp":
            update_field = "temperature_limits"
            limit_name = "temperatura"
        else:  # humidity
            update_field = "humidity_limits"
            limit_name = "umidità"
            
        # Aggiorna il dispenser
        update_operation = {
            "$set": {
                f"data.{update_field}": [min_value, max_value],
                "metadata.updated_at": datetime.now().isoformat()
            }
        }
        
        db_service.update_dr("dispenser_medicine", dispenser_id, update_operation)
        
        # Aggiorna anche eventuali Digital Twin associati
        try:
            dt_factory = context.application.bot_data.get('dt_factory')
            if dt_factory:
                # Trova tutti i DT collegati a questo dispenser
                dts_with_dispenser = _find_dts_with_dr(dt_factory, "dispenser_medicine", dispenser_id)
                
                for dt_id in dts_with_dispenser:
                    dt_instance = dt_factory.get_dt_instance(dt_id)
                    if dt_instance:
                        env_service = dt_instance.get_service("EnvironmentalMonitoringService")
                        if env_service:
                            # Aggiorna la configurazione del servizio
                            if limit_type == "temp":
                                env_service.temperature_range = [min_value, max_value]
                            else:
                                env_service.humidity_range = [min_value, max_value]
        except Exception as e:
            print(f"Errore nell'aggiornamento dei servizi DT: {e}")
            # Non interrompiamo il flusso principale se questo fallisce
            
        # Ottieni il nome del dispenser
        dispenser_name = dispenser.get("data", {}).get("name", dispenser_id)
        
        # Rispondi all'utente
        unit = "°C" if limit_type == "temp" else "%"
        await update.message.reply_text(
            f"✅ Limiti di {limit_name} per '{dispenser_name}' impostati a:\n"
            f"- Minimo: {min_value}{unit}\n"
            f"- Massimo: {max_value}{unit}\n\n"
            f"I nuovi limiti verranno utilizzati per le notifiche di allarme."
        )
        
    except Exception as e:
        print(f"Errore in set_environmental_limits_handler: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Si è verificato un errore durante l'aggiornamento dei limiti: {e}")
        
# Funzione di utilità per trovare i DT con una specifica DR
def _find_dts_with_dr(dt_factory, dr_type, dr_id):
    """
    Trova tutti i Digital Twin che contengono una specifica Digital Replica
    
    Args:
        dt_factory: Istanza di DTFactory
        dr_type (str): Tipo della Digital Replica
        dr_id (str): ID della Digital Replica
        
    Returns:
        list: Lista di ID dei Digital Twin contenenti la DR
    """
    matching_dts = []
    
    try:
        # Assumiamo che db_service sia disponibile nel dt_factory
        dt_collection = dt_factory.db_service.db["digital_twins"]
        
        # Cerca tutti i DT che contengono questa DR
        cursor = dt_collection.find({
            "digital_replicas": {
                "$elemMatch": {
                    "type": dr_type,
                    "id": dr_id
                }
            }
        })
        
        for dt in cursor:
            matching_dts.append(str(dt["_id"]))
            
    except Exception as e:
        print(f"Errore nella ricerca di DTs con DR: {e}")
        
    return matching_dts
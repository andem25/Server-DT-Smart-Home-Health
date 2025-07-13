# Digital Twin System – Smart Home Health

Un framework flessibile ed estensibile per la creazione di Digital Twin dedicati alla salute domestica intelligente. Il sistema consente di virtualizzare dispositivi fisici (es. dispenser medicinali), monitorare parametri ambientali, gestire promemoria terapeutici, notifiche di emergenza e molto altro, tramite una piattaforma modulare e multiutente.

<img width="1000" height="620" alt="image" src="https://github.com/user-attachments/assets/4dcceb02-4633-4f9b-ac6f-7544f8e6c321" />


---

## Architettura a Livelli

Il sistema è progettato secondo una architettura a livelli per garantire modularità e separazione delle responsabilità:

```
├── Application Layer (Interfacce & API)
│   └─ Bot Telegram, REST API, Visualizzazione dati
├── Digital Twin Layer (Core Logic)
│   └─ Gestione ciclo di vita DT, orchestrazione servizi
├── Services Layer (Business Logic)
│   └─ Servizi plug-in: promemoria, monitoraggio, notifiche
└── Virtualization Layer (Digital Replicas)
    └─ Gestione repliche digitali, validazione schemi
```

---

<img width="1454" height="1097" alt="image" src="https://github.com/user-attachments/assets/0d44e4e1-e2e8-4a1a-93c4-237323f02486" />


## Funzionalità Principali

- **Gestione Digital Twin**: Creazione, configurazione e cancellazione di Digital Twin per ogni utente/smart home.
- **Repliche Digitali**: Ogni dispositivo fisico (es. dispenser) ha una rappresentazione digitale con stato, eventi e dati storici.
- **Servizi Modulari**:
  - **Promemoria Terapie**: Notifiche automatiche per assunzione farmaci, verifica aderenza, gestione dosi mancate.
  - **Monitoraggio Ambientale**: Rilevamento temperatura e umidità, soglie personalizzabili, allarmi in tempo reale.
  - **Monitoraggio Porte**: Rilevamento apertura/chiusura dispenser, verifica regolarità rispetto agli orari configurati, notifiche di irregolarità.
  - **Gestione Emergenze**: Pulsante SOS, invio richieste di aiuto e notifiche ai supervisori.
- **Notifiche Multi-canale**: Integrazione con Telegram Bot per notifiche push, messaggi personalizzati e gestione utenti.
- **Visualizzazione Dati**: Grafici automatici di eventi e dati ambientali direttamente su Telegram.
- **Gestione Utenti e Ruoli**: Supervisori e pazienti, login sicuro, gestione multiutente.
- **Configurazione Dinamica**: Limiti ambientali, orari terapie, dispositivi e servizi configurabili via bot.
- **Scheduler Integrato**: Esecuzione periodica di controlli e servizi DT.
- **Integrazione MQTT**: Comunicazione real-time con dispositivi fisici tramite broker MQTT (HiveMQ Cloud).

---

## Comandi Principali (Telegram Bot)

- `/start`, `/help` – Avvio e guida dettagliata
- `/register`, `/login`, `/logout`, `/status` – Gestione account
- `/create_smart_home <nome>` – Crea una nuova casa smart (DT)
- `/list_smart_homes` – Elenca le case smart dell’utente
- `/add_dispenser <id> <nome>` – Registra un nuovo dispenser fisico
- `/my_dispensers` – Elenca i dispenser associati
- `/set_dispenser_time <id> <inizio> <fine>` – Imposta orari terapia
- `/delete_dispenser <id>` – Rimuove un dispenser
- `/link_dispenser <dt_id> <dispenser_id>` – Collega dispenser a DT
- `/environment_data <id> [n|inizio fine]` – Visualizza dati ambientali
- `/set_environment_limits <id> <tipo> <min> <max>` – Imposta soglie allarmi
- `/door_history <id> [n|inizio fine]` – Cronologia eventi porta
- `/check_smart_home_alerts` – Controlla tutte le irregolarità attive
- `/send_dispenser_message <id> <msg>` – Invia messaggio al display dispenser

---

## Tecnologie Utilizzate

- **Python 3.8+**
- **Flask** – Web server e webhook
- **python-telegram-bot** – Bot Telegram
- **Pymongo** – Database MongoDB
- **pyYAML** – Gestione template e schemi
- **MQTT (HiveMQ Cloud)** – Comunicazione IoT
- **ngrok** – Tunneling per webhook pubblici
- **Matplotlib** – Generazione grafici

---

## Avvio Rapido

1. **Prerequisiti**
   - Python 3.8+, MongoDB, HiveMQ account, Telegram Bot Token

2. **Setup Ambiente**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configurazione**
   - Compila `.env` con credenziali MQTT, Telegram, ecc.
   - Configura `config/database.yaml` con i parametri MongoDB

4. **Avvio**
   ```bash
   python app.py
   ```

---

## Estendibilità

- **Aggiunta Servizi**: Implementa una nuova classe in `src/services/`, eredita da `BaseService`, registra il servizio nel DT.
- **Nuovi Tipi di Entità**: Definisci uno schema YAML in `src/virtualization/templates/`, registra tramite `SchemaRegistry`.
- **API REST**: Endpoints per gestione DT e DR (vedi sezione API nel README originale).

---

## Struttura Principale del Progetto

- `app.py` – Entry point, avvio server e bot
- `src/application/` – Bot, API, visualizzazione
- `src/digital_twin/` – Gestione Digital Twin e factory
- `src/services/` – Servizi modulari (monitoraggio, notifiche, ecc.)
- `src/virtualization/` – Gestione repliche digitali e template
- `firmware_device/` – Firmware Arduino/ESP per dispenser fisici
- `config/` – Configurazioni e parametri ambiente

---
## Schema elettrico dispositivo
I componenti del sistema digitale del sistema sono:
* Microcontrollore Wi-Fi: NodeMCU v2 (ESP8266 @ 80MHz, 4MB flash) – gestisce logica locale e comunicazione.
* Sensore temperatura/umidità: DHT11 (collegato al pin D6 del NodeMCU) –
fornisce T e RH ambientali, alimentato a 3.3V.
* Sensore stato sportello: Reed switch magnetico NC – collegato al pin D7 e a
+3.3V (con resistenza pull-down 10 kΩ a GND) in configurazione da rilevare LOGIC
HIGH quando sportello chiuso (magnete vicino, contatto chiuso).
* Display LCD: Modulo LCD 16x2 alfanumerico, con interfaccia I2C (PCF8574)
– collegato a SDA (D2) e SCL (D1) del NodeMCU, alimentato a 5V (il PCF8574
opera con livelli 5V ma accetta input 3.3V come dall’ESP).
* Buzzer piezoelettrico attivo: collegato al pin D5 (NOTIFICATION_PIN) e
GND. Il pin D5 pilotato HIGH emette un suono (buzzer attivo a 3.3V).
* LED rosso: collegato anch’esso al pin D5 (in parallelo al buzzer, con resistenza
limitatrice da 220 Ω) – si illumina quando D5 è HIGH. (In alternativa, avremmo
potuto usare il LED blu onboard del NodeMCU sul pin D0, ma si è preferito un
LED esterno di colore rosso più visibile).
* Pulsante “Conferma”: pulsante normally aperto collegato tra il pin D0 e +3.3V,
con resistenza pull-down 10 kΩ verso GND – fornisce un impulso HIGH quando
premuto. (Nel firmware chiamato AUTH_BUTTON).

Lo schema elettrico del dispositivo è il seguente:
![Immagine WhatsApp 2025-07-07 ore 18 15 34_d6883059](https://github.com/user-attachments/assets/8e2b94d6-1d03-4156-b2be-afd6124042d4)


## Note

- Il sistema è progettato per essere multiutente e multi-dispositivo.
- Tutte le operazioni critiche sono tracciate e gestite con logging e notifiche.

---

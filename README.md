# Digital Twin System – Smart Home Health

Un framework flessibile ed estensibile per la creazione di Digital Twin dedicati alla salute domestica intelligente. Il sistema consente di virtualizzare dispositivi fisici (es. dispenser medicinali), monitorare parametri ambientali, gestire promemoria terapeutici, notifiche di emergenza e molto altro, tramite una piattaforma modulare e multiutente.

<img width="1200" height="720" alt="image" src="https://github.com/user-attachments/assets/4dcceb02-4633-4f9b-ac6f-7544f8e6c321" />


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

## Note

- Il sistema è progettato per essere multiutente e multi-dispositivo.
- Tutte le operazioni critiche sono tracciate e gestite con logging e notifiche.

---

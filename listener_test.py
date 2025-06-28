import paho.mqtt.client as mqtt
import ssl # Importato per una migliore gestione di TLS

# --- Configurazione ---

# L'indirizzo IP o il nome host del tuo server HiveMQ
broker_address = "0467b214296349a08f4092ceb0acd55c.s1.eu.hivemq.cloud"

# La porta standard per MQTT su TLS/SSL è 8883
port = 8883

# Le tue credenziali di accesso
username = "12345"
password = "a12345678B"

# Il topic a cui iscriversi ('#' per tutti)
topic_to_subscribe = "#"

# (Opzionale ma raccomandato) Percorso al file del certificato della CA
# Se il tuo server usa un certificato autofirmato o una CA privata,
# decommenta e imposta il percorso corretto. Altrimenti, lascialo come None.
ca_certificate_path = None # Esempio: "/etc/ssl/certs/my_ca.crt"


# --- Funzioni di Callback (Invariate) ---

def on_connect(client, userdata, flags, rc, properties=None):
    """
    Callback eseguita quando il client si connette con successo al broker.
    """
    if rc == 0:
        print(f"Connesso con successo al broker MQTT con connessione sicura (TLS)! (Codice: {rc})")
        client.subscribe(topic_to_subscribe)
        print(f"Iscritto al topic: '{topic_to_subscribe}'")
    else:
        print(f"Connessione fallita, codice di ritorno: {rc}")
        if rc == 4:
            print("-> Causa probabile: Username o Password non corretti.")
        elif rc == 5:
            print("-> Causa probabile: Non autorizzato a connettersi.")
        else:
            print("-> Controlla l'indirizzo del server, la porta e le impostazioni TLS/SSL.")


def on_message(client, userdata, msg):
    """
    Callback eseguita ogni volta che un messaggio viene ricevuto.
    """
    try:
        payload_str = msg.payload.decode("utf-8")
        print(f"Messaggio ricevuto -> Topic: [{msg.topic}] | Messaggio: '{payload_str}'")
    except UnicodeDecodeError:
        print(f"Messaggio ricevuto -> Topic: [{msg.topic}] | Payload (non-UTF8): {msg.payload}")


# --- Script Principale ---

if __name__ == "__main__":
    # Crea l'istanza del client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    # Assegna le funzioni di callback
    client.on_connect = on_connect
    client.on_message = on_message

    # 1. Imposta le credenziali per l'autenticazione
    client.username_pw_set(username, password)

    # 2. Abilita la crittografia TLS/SSL
    # Questa è la riga che attiva la connessione sicura.
    try:
        client.tls_set(ca_certs=ca_certificate_path, tls_version=ssl.PROTOCOL_TLS)
        print("Impostazioni TLS/SSL caricate correttamente.")
    except Exception as e:
        print(f"Errore durante l'impostazione di TLS: {e}")
        # Interrompe lo script se le impostazioni TLS non sono valide
        exit()


    print(f"Tentativo di connessione sicura (TLS) al broker: {broker_address}:{port}...")

    try:
        # 3. Connetti al broker
        client.connect(broker_address, port, 60)

        # 4. Avvia il loop per mantenere la connessione e ascoltare i messaggi
        client.loop_forever()

    except KeyboardInterrupt:
        print("\nScript interrotto dall'utente.")
        client.disconnect()
        print("Disconnesso dal broker.")
    except ConnectionRefusedError:
         print("Errore: Connessione rifiutata. Verifica che le credenziali, l'indirizzo e la porta siano corretti.")
    except ssl.SSLError as e:
        print(f"Errore SSL: {e}. Controlla i certificati e le impostazioni TLS del server e del client.")
    except OSError as e:
        print(f"Errore di rete: {e}. Verifica che il broker sia raggiungibile e non ci siano firewall che bloccano la connessione.")
    except Exception as e:
        print(f"Si è verificato un errore inaspettato: {e}")
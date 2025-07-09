#include <ESP8266HTTPClient.h>

// --- Pin Definitions ---
#define LIGHT_PIN A0                 // Analog input pin for ambient light sensor
#define AUTH_BUTTON D0               // Digital pin for authorization button
#define EMERGENCY_BUTTON D8          // Digital pin for emergency stop button
#define NOTIFICATION_PIN D5          // Digital pin for notification LED or buzzer
#define DHTPIN D6                    // Digital pin for DHT temperature/humidity sensor
#define REED_PIN D7                  // Digital pin for magnetic reed switch

#define LCD_WIDTH 16                 // Number of characters per LCD row
#define DHTTYPE DHT11                // Type of DHT sensor model
#define MAX_BUFFER 50                // Maximum number of buffered MQTT messages

// --- Library Includes ---
#include <ESP8266WiFi.h>                    // Core ESP8266 WiFi functions
#include <ESP8266HTTPClient.h>              // Library to simplify HTTP requests (GET, POST, etc.) on ESP8266, supports both HTTP and HTTPS
#include <ESP8266httpUpdate.h>              // Library for Over-The-Air (OTA) firmware updates via HTTP/HTTPS on ESP8266
#include <ArduinoJson.h>                    // JSON parsing and serialization
#include <MQTT.h>                           // MQTT client library
#include <WiFiClientSecureBearSSL.h>        // Secure (TLS) WiFi client
#include <WiFiUdp.h>                        // UDP support for NTP
#include <NTPClient.h>                      // Network Time Protocol client
#include <Wire.h>                           // I2C communication
#include "DHT.h"                            // DHT sensor library
#include "LiquidCrystal_PCF8574.h"          // I2C LCD backpack library

// --- LCD and Sensor Objects ---
LiquidCrystal_PCF8574 lcd(0x27);           // I2C address 0x27 for the LCD backpack
DHT dht(DHTPIN, DHTTYPE);                  // Instantiate DHT sensor on DHTPIN

// --- Root CA Certificate (ISRG Root X1) for TLS ---
static const char root_ca[] = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)EOF";


// --- Secure MQTT Setup ---
BearSSL::X509List certs(root_ca);
BearSSL::WiFiClientSecure espClient;
MQTTClient mqtt(256);                       // MQTT client with 256-byte buffer

// --- NTP (Network Time Protocol) Client ---
WiFiUDP ntpUDP;                             // Underlying UDP client for NTP
NTPClient timeClient(ntpUDP,                // NTP client using UDP
                     "pool.ntp.org",        // NTP server pool
                     7200,                  // Time offset in seconds (UTC+2)
                     60000);                // Update interval in milliseconds

// --- WiFi and MQTT Credentials ---
const char* ssid           = "HOTSPOT";
const char* password       = "pasta123";
const char* mqtt_server    = "0467b214296349a08f4092ceb0acd55c.s1.eu.hivemq.cloud";
const char* mqtt_username  = "12345";
const char* mqtt_password  = "a12345678B";
const int   mqtt_port      = 8883;          // Secure MQTT over TLS
const char* device_id      = "b_123456789a"; // Unique client identifier

// --- Reed Switch Debounce Parameters ---
const unsigned long DEBOUNCE_DELAY = 250;    // Minimum stable time (ms) to confirm state change
int lastReading = -1;                        // Last raw reading from REED_PIN
unsigned long lastDebounceTime = 0;          // Timestamp of last state change check

// --- Button Debounce Parameters ---
const unsigned long debounceDelay = 50;      // Debounce period for buttons (ms)

int  lastAuthReading      = LOW;             // Last raw reading from AUTH_BUTTON
unsigned long lastAuthDebounce = 0;          // Timestamp for AUTH_BUTTON debounce
unsigned long lastAuthTime     = 0;          // Timestamp of last valid auth press

int  lastEmergencyReading      = LOW;        // Last raw reading from EMERGENCY_BUTTON
unsigned long lastEmergencyDebounce = 0;     // Timestamp for emergency debounce
unsigned long lastEmergencyTime     = 0;     // Timestamp of last valid emergency press

// --- MQTT Reconnection Timing ---
unsigned long lastReconnectAttempt = 0;       // Timestamp of last reconnect attempt
const unsigned long reconnectInterval = 5000;// Interval between reconnect attempts (ms)

// --- Sensor Measurement Scheduling ---
const unsigned long measureInterval = 10000; // Time between sensor reads (ms)
unsigned long lastMeasureTime = 0;           // Timestamp of last measurement
int measureCount = 0;                        // Counter of measurements taken
float tempSum = 0;                           // Accumulated temperature for averaging
float humSum = 0;                            // Accumulated humidity for averaging

// --- Reed Switch State Tracking ---
int lastReedState = -1;                      // Last debounced state of the reed switch

// --- MQTT Message Buffers ---
String bufferTopics[MAX_BUFFER];             // Circular buffer for outgoing topics
String bufferMessages[MAX_BUFFER];           // Circular buffer for outgoing payloads
int bufferCount = 0;                         // Number of buffered messages waiting

// --- MQTT Publish Helpers ---
char topic[128];                             // Working buffer for topic strings
char mqtt_message[128];                      // Working buffer for message payloads

// --- Formatted Time String ---
String formattedTime = "";                   // Human-readable time, e.g., "14:23:45"

// --- LCD Display Lines ---
String displayLine1;                         // Top line of LCD
String displayLine2 = "Waiting for message"; // Bottom line default text

// --- Blinking Notification Settings ---
bool blinkNotification = false;              // Enable/disable blinking mode
unsigned long blinkStartTime = 0;            // When blinking began
const unsigned long blinkInterval = 300;     // Blink toggle interval (ms)
unsigned long lastBlinkTime = 0;             // Timestamp of last blink toggle
bool notificationState = false;              // Current output state for notification

// --- Firmware URL for updaptes
//String firmwareURL = "https://raw.githubusercontent.com/mpPistis12356/arduinotest/main/ver2.bin";
String protocol = "https";
String host = "raw.githubusercontent.com";
String path = "/mpPistis12356/arduinotest/main/ver2.bin";
uint16_t port = 443;
bool update_status = false;

void setup() {
  // ——————————————————————————————————————————————
  // 1. Serial & GPIO Initialization
  // ——————————————————————————————————————————————
  Serial.begin(115200);                      // Start serial for debugging
  pinMode(AUTH_BUTTON, INPUT);               // Auth button input
  pinMode(EMERGENCY_BUTTON, INPUT);          // Emergency button input
  pinMode(NOTIFICATION_PIN, OUTPUT);         // Notification LED/buzzer output
  digitalWrite(NOTIFICATION_PIN, LOW);       // Ensure notification is off at start
  pinMode(REED_PIN, INPUT_PULLUP);           // Reed switch with internal pull‑up
  lastReedState = digitalRead(REED_PIN);     // Read initial reed state

  // ——————————————————————————————————————————————
  // 2. Sensor & Display Setup
  // ——————————————————————————————————————————————
  dht.begin();                               // Initialize DHT sensor
  Wire.begin(D2, D1);                        // I2C on D2=SDA, D1=SCL
  lcd.begin(LCD_WIDTH, 2);                   // Initialize 16×2 LCD
  lcd.clear();                               // Clear any stray characters
  lcd.setBacklight(255);                     // Turn backlight fully on
  lcd.setCursor(0, 0);
  handleLCD("Setting up...", "");            // Show a startup message

  // ——————————————————————————————————————————————
  // 3. Wi‑Fi Connection
  // ——————————————————————————————————————————————
  Serial.println(">> Setup start");
  setup_wifi();                              // Connect to Wi‑Fi (blocking)
  Serial.println(">> Wi‑Fi connected");

  // ——————————————————————————————————————————————
  // 4. NTP Time Synchronization
  // ——————————————————————————————————————————————
  timeClient.begin();                        // Start NTP client
  int retry = 0;
  delay(200);
  while (!timeClient.update() && retry < 50) {
    Serial.println("Waiting for NTP...");
    timeClient.forceUpdate();               // Try to force a sync
    delay(200);
    retry++;
  }
  if (retry >= 50) {
    Serial.println("NTP sync failed — TLS may not work");
  } else {
    Serial.println("NTP synchronized");
  }

  // Apply NTP time to TLS client for certificate validation
  // Imposto la catena di certificati trusted
  espClient.setTrustAnchors(&certs);
  espClient.setX509Time(timeClient.getEpochTime());

  // ——————————————————————————————————————————————
  // 5. MQTT Client Initialization
  // ——————————————————————————————————————————————
  mqtt.begin(mqtt_server, mqtt_port, espClient); // Configure MQTT over TLS
  mqtt.onMessage(callback);                      // Set incoming‑message handler
  mqtt.setOptions(30,    // Keep‑alive in seconds
                  false, // Clean session?
                  10000 // Timeout for operations
  );

  // Attempt initial connect
  if (mqtt.connect(device_id, mqtt_username, mqtt_password)) {
    Serial.println(">> MQTT connected");

    // Subscribe to all topics under this device’s namespace
    String topicFilter = String(device_id) + "/#";
    mqtt.subscribe(topicFilter.c_str(), 2);
  } else {
    Serial.println(">> MQTT connect failed");
  }

  Serial.println(">> Setup complete");
  // --- Reed Switch Handling (Door Sensor) with Debounce ---
  int reading = digitalRead(REED_PIN);  // Read current reed switch state
  lastReading = reading;
  // Prepare door state message
  DynamicJsonDocument doc(256);
  doc["door"] = reading;
  doc["time"] = formattedTime;
  serializeJson(doc, mqtt_message);
  buildTopic("/door");

  if (mqtt.connected()) {
    publishMessage(topic, mqtt_message, false);
  } 
}

// Forward declaration
void bufferMessage(const String &topic, const String &message, const char *label = "");


void loop() {  
  // Maintain MQTT connection and update NTP time
  mqtt.loop();
  timeClient.update();
  String formattedTime = timeClient.getFormattedTime();
  unsigned long now = millis();

  // --- MQTT Reconnection Logic (Non-blocking) ---
  if (!mqtt.connected()) {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.print("Wi-Fi connection failed");
      displayLine2 = "WiFi lost!";  // Show message on LCD
    } else if (now - lastReconnectAttempt >= reconnectInterval) {
      // Attempt to reconnect if enough time has passed
      lastReconnectAttempt = now;
      attemptReconnect();
    }
  } 

  // --- AUTH Button Handling with Debounce ---
  int authReading = digitalRead(AUTH_BUTTON);  // Read AUTH button state

  if (authReading != lastAuthReading) {
    lastAuthDebounce = now;  // Reset debounce timer on state change
  }
  lastAuthReading = authReading;

  if (now - lastAuthDebounce > debounceDelay) {
    // If state is stable and at least 5 seconds passed since last AUTH
    if (authReading == HIGH && now - lastAuthTime > 5000) {
      lastAuthTime = now;

      // Prepare and publish AUTH message
      DynamicJsonDocument doc(256);
      doc.set(1);
      serializeJson(doc, mqtt_message);
      buildTopic("/auth");
      publishMessage(topic, mqtt_message, false);
      mqtt.loop();  // Ensure immediate MQTT handling
    }
  }

  // --- EMERGENCY Button Handling with Debounce ---
  int emergencyReading = digitalRead(EMERGENCY_BUTTON);  // Read EMERGENCY button state

  if (emergencyReading != lastEmergencyReading) {
    lastEmergencyDebounce = now;  // Reset debounce timer on state change
  }
  lastEmergencyReading = emergencyReading;

  if (now - lastEmergencyDebounce > debounceDelay) {
    // If stable and 5 seconds passed since last emergency message
    if (emergencyReading == HIGH && now - lastEmergencyTime > 5000) {
      lastEmergencyTime = now;

      // Prepare EMERGENCY message
      DynamicJsonDocument doc(256);
      doc.set(1);
      serializeJson(doc, mqtt_message);
      buildTopic("/emergency");

      if (mqtt.connected()) {
        // If connected, publish immediately
        publishMessage(topic, mqtt_message, false);
        mqtt.loop();
      } else {
        // Otherwise buffer the message for later delivery
        bufferMessage(String(topic), String(mqtt_message), "Emergency");
      }
    }
  }

  // --- Periodic Temperature and Humidity Measurements ---
  if (now - lastMeasureTime >= measureInterval) {
    lastMeasureTime = now;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (!isnan(h) && !isnan(t)) {
      displayLine1 = "T: " + String(t, 1) + "\xDF" + "C H: " + String(h, 0) + "%";
      tempSum += t;
      humSum += h;
      measureCount++;

      if (measureCount >= 30) {
        // Compute average values
        float avgT = tempSum / 30;
        float avgH = humSum / 30;

        // Prepare JSON payload
        DynamicJsonDocument doc(256);
        doc["avg_temperature"] = avgT;
        doc["avg_humidity"]    = avgH;
        doc["time"]            = formattedTime;
        serializeJson(doc, mqtt_message);

        buildTopic("/average");

        if (mqtt.connected()) {
          publishMessage(topic, mqtt_message, false);
          mqtt.loop();
        } else {
          bufferMessage(String(topic), String(mqtt_message), "Emergency");
        }

        // Reset for next batch
        tempSum = humSum = 0;
        measureCount = 0;
      }
    }
  }

  // --- Reed Switch Handling (Door Sensor) with Debounce ---
  int reading = digitalRead(REED_PIN);  // Read current reed switch state

  if (reading != lastReading) {
    lastDebounceTime = millis();  // Reset debounce timer on change
  }
  lastReading = reading;

  if (millis() - lastDebounceTime > DEBOUNCE_DELAY) {
    if (reading != lastReedState) {
      // If blinking notification was active and door just closed
      if (blinkNotification == true && lastReedState == HIGH && reading == LOW) {
        blinkNotification = false;
        digitalWrite(NOTIFICATION_PIN, LOW);  // Turn off blinking
      }

      lastReedState = reading;

      // Prepare door state message
      DynamicJsonDocument doc(256);
      doc["door"] = reading;
      doc["time"] = formattedTime;
      serializeJson(doc, mqtt_message);
      buildTopic("/door");

      if (mqtt.connected()) {
        publishMessage(topic, mqtt_message, false);
      } else {
        bufferMessage(topic, mqtt_message);  // Fallback to buffer
      }
    }
  }

  // --- LED Notification Blinking Logic ---
  if (blinkNotification) {
    unsigned long currentMillis = millis();
    if (currentMillis - lastBlinkTime >= blinkInterval) {
      lastBlinkTime = currentMillis;
      notificationState = !notificationState;  // Toggle state
      digitalWrite(NOTIFICATION_PIN, notificationState);  // Blink LED
    }
  }

  // --- LCD Display Update ---
  handleLCD(displayLine1, displayLine2);  // Refresh display with latest messages
  if (update_status) {  // Check if an OTA update has been requested
    update_status = false;  // Reset the update flag to prevent multiple updates

    espClient.setInsecure();  // Disable TLS certificate validation (not secure, for testing only)

    Serial.println("Starting OTA...");  // Log message to indicate OTA process is starting

    // 1) Sync time for TLS
    timeClient.update();  // Fetch current time from NTP server
    espClient.setX509Time(timeClient.getEpochTime());  // Set TLS client's internal clock (required for certificate validation)

    // 2) Start the OTA process
    ESPhttpUpdate.setFollowRedirects(HTTPC_FORCE_FOLLOW_REDIRECTS);  // Automatically follow HTTP redirects (useful for GitHub URLs)

    // Launch the OTA update: provide HTTPS client, host, port, and path to firmware
    t_httpUpdate_return ret = ESPhttpUpdate.update(espClient, host.c_str(), port, path.c_str());

    // Handle OTA result
    switch (ret) {
      case HTTP_UPDATE_FAILED:
        // OTA failed: print the error code and message
        Serial.printf("OTA failed (%d): %s\n",
                      ESPhttpUpdate.getLastError(),
                      ESPhttpUpdate.getLastErrorString().c_str());
        break;
      case HTTP_UPDATE_NO_UPDATES:
        // No update available on the server
        Serial.println("No updates available.");
        break;
      case HTTP_UPDATE_OK:
        // OTA successful: the device will reboot automatically
        Serial.println("OTA OK — device will reboot");
        break;
    }
  }
}


// Sends all messages that were queued in the static buffers
void flushBuffer() {
  // If there are no buffered messages, exit immediately
  if (bufferCount <= 0) return;

  Serial.println("Flushing buffer...");

  // Iterate through each buffered topic/message pair
  for (int i = 0; i < bufferCount; ++i) {
    // Try to publish with QoS 2 (exactly-once delivery)
    bool ok = mqtt.publish(
      bufferTopics[i].c_str(),
      bufferMessages[i].c_str(),
      false,   // retained = false
      2        // QoS = 2
    );

    if (ok) {
      // Log successful flush
      Serial.println("Flushed [" + bufferTopics[i] + "]: " + bufferMessages[i]);
    } else {
      // Log failure, will remain in buffer until next flush attempt
      Serial.println("Failed to flush [" + bufferTopics[i] + "]");
    }
  }

  // After attempting to send all, clear the buffer
  bufferCount = 0;
}


// Attempts a one-off, non-blocking MQTT connection
bool attemptReconnect() {
  Serial.println("Attempting MQTT connection...");

  // Try to connect using stored credentials over TLS
  if (mqtt.connect(device_id, mqtt_username, mqtt_password)) {
    Serial.println("MQTT connected");
    displayLine2 = "Waiting for message";  // Update LCD status line

    // Subscribe to all topics under the device ID namespace
    String topicFilter = String(device_id) + "/#";
    mqtt.subscribe(topicFilter.c_str(), 2);

    // Once connected, send any buffered messages
    flushBuffer();

    return true;  // Connection succeeded
  } else {
    // If connect fails, print error code and update display
    Serial.print("MQTT connect failed, rc=");
    Serial.println(mqtt.lastError());
    displayLine2 = "MQTT Failed";
    return false;
  }
}


/************* Wi‑Fi Connection Setup ***********/
void setup_wifi() {
  Serial.print("\nConnecting to ");
  Serial.println(ssid);

  // Show “Connecting…” on the LCD
  lcd.clear();
  lcd.setBacklight(255);
  lcd.setCursor(0, 0);
  lcd.print("Connecting...");

  // Begin station mode Wi‑Fi connection
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  bool firstTry = true;
  // Block until connected, updating status once
  while (WiFi.status() != WL_CONNECTED) {
    if (firstTry) {
      Serial.println("Waiting WiFi...");
      lcd.clear();
      lcd.setBacklight(255);
      lcd.setCursor(0, 0);
      lcd.print("Waiting WiFi...");
      firstTry = false;
    }
    timeClient.forceUpdate();  // keep NTP client alive while waiting
  }

  // Seed random number generator (used later for MQTT client ID, etc.)
  randomSeed(micros());

  Serial.println("\nWiFi connected\nIP address:");
  Serial.println(WiFi.localIP());
}


/************* MQTT Incoming Message Callback ***********/
void callback(String &topic, String &payload) {
  // 1) Print a clean log of topic + payload
  Serial.println("[" + topic + "] " + payload);

  // 2) Build the device namespace prefix
  String dev = String(device_id);

  // 3) Handle specific topics
  if (topic == dev + "/notification" && !blinkNotification) {
    // Start LED blink notification
    blinkStartTime = millis();
    lastBlinkTime = millis();
    blinkNotification = true;
  }
  else if (topic == dev + "/message") {
    // Display arbitrary text on the second LCD line
    displayLine2 = purify(payload);
  }else if (topic == dev + "/update" ) {
    if (payload == "1") {              // If the message payload is "1"
      update_status = true;           // Set the flag to trigger OTA update on the next cycle
    }
}
}


/**** Publish an MQTT message with QoS 2 **********/
void publishMessage(const char* topic, const String &payload, bool retained) {
  // Try to send with QoS = 2 (exactly once)
  if (mqtt.publish(topic, payload, retained, 2)) {
    Serial.println(String("Message published [") + topic + "]: " + payload);
  } else {
    Serial.println(String("Publish failed [") + topic + "]");
  }
}


/**** Build topic **********/
void buildTopic(const char* suffix) {
  // Concatenate the device identifier and the given suffix
  // into the global `topic` buffer, e.g. "device123/average"
  snprintf(topic,               // destination buffer
           sizeof(topic),       // its size
           "%s%s",              // format: device_id followed by suffix
           device_id,
           suffix);
}

/********** OTHER METHODS **********/

// Remove unwanted whitespace and line breaks from an incoming payload
String purify(String input) {
  input.trim();        // Remove leading/trailing spaces and tabs
  input.replace("\n", "");  // Strip newline characters
  input.replace("\r", "");  // Strip carriage returns
  return input;        // Return the cleaned string
}

// Display two lines on the LCD, with optional scrolling for long text
void handleLCD(const String& line1, const String& line2) {
  static unsigned long lastScrollTime = 0; // Last time we updated the scroll
  static int scrollIndex1 = 0, scrollIndex2 = 0; // Current scroll positions
  static String prevLine1 = "", prevLine2 = "";  // Previous content, to detect changes

  unsigned long currentTime = millis();
  const unsigned long scrollDelay = 300;   // ms between scroll steps

  // If either line changed, reset scroll indices and clear the display
  if (line1 != prevLine1 || line2 != prevLine2) {
    prevLine1 = line1;
    prevLine2 = line2;
    scrollIndex1 = scrollIndex2 = 0;
    lastScrollTime = currentTime;

    lcd.clear();               // Clear any old text
    lcd.setBacklight(255);     // Ensure backlight is on
    lcd.setCursor(0, 0);       // Position cursor at start of first line
  }

  // Only update the display when enough time has passed
  if (currentTime - lastScrollTime >= scrollDelay) {
    lastScrollTime = currentTime;

    // —————— LINE 1 ——————
    lcd.setCursor(0, 0);
    if (line1.length() <= LCD_WIDTH) {
      // If it fits, print it statically
      lcd.print(line1);
    } else {
      // Otherwise, scroll by creating a looping buffer
      String buffer1 = line1 + "   " + line1;
      String view1 = buffer1.substring(scrollIndex1, scrollIndex1 + LCD_WIDTH);
      lcd.print(view1);
      scrollIndex1++;
      if (scrollIndex1 >= line1.length() + 3) {
        scrollIndex1 = 0;  // Wrap around when reaching the end
      }
    }

    // —————— LINE 2 ——————
    lcd.setCursor(0, 1);
    if (line2.length() <= LCD_WIDTH) {
      lcd.print(line2);
    } else {
      String buffer2 = line2 + "   " + line2;
      String view2 = buffer2.substring(scrollIndex2, scrollIndex2 + LCD_WIDTH);
      lcd.print(view2);
      scrollIndex2++;
      if (scrollIndex2 >= line2.length() + 3) {
        scrollIndex2 = 0;
      }
    }
  }
}

// Queue a message for later transmission if MQTT is offline
void bufferMessage(const String &topic, 
                   const String &message, 
                   const char *label) {
  if (bufferCount < MAX_BUFFER) {
    // Add topic and message to the circular buffers
    bufferTopics[bufferCount] = topic;
    bufferMessages[bufferCount] = message;
    bufferCount++;
  } else {
    // Buffer is full: log and drop the message, optionally noting its label
    Serial.print(">> Buffer full");
    if (label[0]) {
      Serial.print(" (");
      Serial.print(label);
      Serial.print(")");
    }
    Serial.println(" — message discarded");
  }
}

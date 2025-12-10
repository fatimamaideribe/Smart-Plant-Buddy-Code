// Smart Plant Buddy 

#include <WiFi.h>
#include <HTTPClient.h>
#include "DHT.h"
#include <time.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WebSocketsServer.h>

//Pins 
#define SOIL_PIN 34  
#define LDR_PIN  35  
#define DHT_PIN  4
#define DHTTYPE  DHT11

// OLED Display 
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

//  OBJECTS 
DHT dht(DHT_PIN, DHTTYPE);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
WebSocketsServer webSocket(81);  // WebSocket on port 81

// WIFI & FIREBASE 
const char* WIFI_SSID = "*****";
const char* WIFI_PASS = "*****"; // redacted for privacy
const char* FIREBASE_DB_URL = "https://smartplantsensor-default-rtdb.europe-west1.firebasedatabase.app";

//  TIMING 
unsigned long lastPost = 0;
unsigned long lastOLEDUpdate = 0;
const unsigned long POST_INTERVAL_MS = 900000;  // 15 minutes
const unsigned long OLED_UPDATE_MS = 2000;       // 2 seconds

//  STATE 
String currentMood = "ok";
int currentSoil = 0;

//  MOOD FACES 
const char* getMoodFace(const String& mood) {
  if (mood == "happy") return "  ^_^  ";
  if (mood == "thirsty") return "  O_O  ";
  if (mood == "drowning") return " @_@  ";
  if (mood == "hot") return "  >_<  ";
  return "  -_-  ";
}

const char* getMoodText(const String& mood) {
  if (mood == "happy") return "I'm Happy!";
  if (mood == "thirsty") return "I'm Thirsty";
  if (mood == "drowning") return "Too Wet!";
  if (mood == "hot") return "Too Hot!";
  return "I'm OK";
}

//  HELPER FUNCTIONS 

long long getEpochMillis() {
  time_t now = time(nullptr);
  return (long long)now * 1000;
}

// OLED Display initialization
bool initOLED() {
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println("SSD1306 allocation failed");
    return false;
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Plant Buddy");
  display.println("Starting...");
  display.display();
  Serial.println("OLED initialized!");
  return true;
}

// Update OLED with plant status
void updateOLED(int soil, float temp, float hum, const String& mood) {
  display.clearDisplay();
  
  // Title
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("Smart Plant Buddy");
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);
  
  // Mood face (large)
  display.setTextSize(2);
  display.setCursor(20, 15);
  display.print(getMoodFace(mood));
  
  // Mood text
  display.setTextSize(1);
  display.setCursor(20, 35);
  display.println(getMoodText(mood));
  
  // Sensor readings
  display.setCursor(0, 48);
  display.print("S:");
  display.print(soil);
  display.print(" T:");
  display.print(temp, 0);
  display.print("C");
  
  display.setCursor(0, 56);
  display.print("H:");
  display.print(hum, 0);
  display.print("%");
  
  display.display();
}

// WiFi connection
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 20);
  display.println("Connecting WiFi...");
  display.display();

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    Serial.print(".");
    delay(500);
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected! IP: ");
    Serial.println(WiFi.localIP());
    
    display.clearDisplay();
    display.setCursor(0, 10);
    display.println("WiFi Connected!");
    display.setCursor(0, 25);
    display.print("IP: ");
    display.println(WiFi.localIP());
    display.display();
    delay(2000);
  } else {
    Serial.println("WiFi failed!");
  }

  // NTP time sync
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Syncing time");
  time_t now = time(nullptr);
  while (now < 8 * 3600 * 2) {
    delay(500);
    Serial.print(".");
    now = time(nullptr);
  }
  Serial.println("\nTime synced!");
}

// Post to Firebase
bool postToFirebase(int soil, int ldr, float tempC, float hum, const String &mood) {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  String url = String(FIREBASE_DB_URL) + "/plants/plant1/logs.json";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  long long timestampMs = getEpochMillis();

  String json = "{";
  json += "\"timestamp\":" + String(timestampMs) + ",";
  json += "\"soil_raw\":" + String(soil) + ",";
  json += "\"light_raw\":" + String(ldr) + ",";
  json += "\"temp_c\":" + String(tempC, 1) + ",";
  json += "\"hum\":" + String(hum, 0) + ",";
  json += "\"mood\":\"" + mood + "\"";
  json += "}";

  int code = http.POST(json);
  Serial.print("Firebase POST: ");
  Serial.println(code);

  http.end();
  return (code > 0 && code < 400);
}

// Infer plant mood
String inferMood(int soil, int ldr, float tempC) {
  // For RESISTIVE sensors
  bool tooDry = soil < 1500;
  bool goodSoil = (soil >= 1500 && soil <= 3100);
  bool tooWet = soil > 3500;
  bool tooBright = ldr > 2500;
  bool tooHot = tempC >= 27.0;

  if (tooDry) return "thirsty";
  if (tooWet) return "drowning";
  if (tooBright || tooHot) return "hot";
  if (goodSoil) return "happy";
  return "ok";
}

// WebSocket event handler
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.printf("[%u] Disconnected!\n", num);
      break;
    case WStype_CONNECTED:
      {
        IPAddress ip = webSocket.remoteIP(num);
        Serial.printf("[%u] Connected from %d.%d.%d.%d\n", num, ip[0], ip[1], ip[2], ip[3]);
      }
      break;
  }
}

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  Serial.println("\n\nSmart Plant Buddy - Simple Version");
  Serial.println("===================================");
  
  // start I2C for OLED
  Wire.begin();
  
  // start OLED
  if (!initOLED()) {
    Serial.println("OLED not found, continuing without display");
  }
  
  // start DHT
  dht.begin();
  
  // Connectz to WiFi
  connectWiFi();
  
  // Start WebSocket server
  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  Serial.println("WebSocket server started on port 81");
  
  // Ready screen
  display.clearDisplay();
  display.setTextSize(2);
  display.setCursor(10, 20);
  display.println("READY!");
  display.display();
  delay(1000);
  
  Serial.println("✅ Setup complete!");
  Serial.println("📊 Dashboard: http://" + WiFi.localIP().toString());
}

// The main loop
void loop() {
  // Handle WebSocket
  webSocket.loop();
  
  // Auto reconnect WiFi
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // Read sensors with averaging for stability
  int soil = 0;
  for(int i = 0; i < 10; i++) {
    soil += analogRead(SOIL_PIN);
    delay(10);
  }
  soil = soil / 10;
  
  int ldr = analogRead(LDR_PIN);
  float hum = dht.readHumidity();
  float tempC = dht.readTemperature();

  if (isnan(hum) || isnan(tempC)) {
    Serial.println("DHT11 read failed");
    hum = -1;
    tempC = -100;
  }

  // Determine mood
  String mood = inferMood(soil, ldr, tempC);
  currentMood = mood;
  currentSoil = soil;

  // Print to serial
  Serial.printf("Soil=%d Light=%d Temp=%.1fC Hum=%.0f%% Mood=%s\n",
                soil, ldr, tempC, hum, mood.c_str());

  // Update OLED display every 2 seconds
  if (millis() - lastOLEDUpdate > OLED_UPDATE_MS) {
    updateOLED(soil, tempC, hum, mood);
    lastOLEDUpdate = millis();
  }

  // Send real-time data via WebSocket
  String wsData = "{";
  wsData += "\"soil\":" + String(soil) + ",";
  wsData += "\"light\":" + String(ldr) + ",";
  wsData += "\"temp\":" + String(tempC, 1) + ",";
  wsData += "\"hum\":" + String(hum, 0) + ",";
  wsData += "\"mood\":\"" + mood + "\"";
  wsData += "}";
  webSocket.broadcastTXT(wsData);

  // Post to Firebase every 15 minutes
  if (millis() - lastPost > POST_INTERVAL_MS) {
    bool ok = postToFirebase(soil, ldr, tempC, hum, mood);
    Serial.println(ok ? "✓ Posted to Firebase" : "✗ Post failed");
    lastPost = millis();
  }

  delay(1000);
}
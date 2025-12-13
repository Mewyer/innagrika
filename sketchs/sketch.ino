#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h> // Необходимо добавить библиотеку ArduinoJson в Wokwi

// --- НАСТРОЙКИ ---
#define DHTPIN 15     // Пин подключения датчика
#define DHTTYPE DHT22

const char* ssid = "Wokwi-GUEST"; // Виртуальный WiFi Wokwi
const char* password = "";
const char* mqtt_server = "test.mosquitto.org"; // Публичный брокер

// Уникальные топики (чтобы не пересекаться с другими)
const char* topic_temp = "innagrika/field/raw/temperature";
const char* topic_humid = "innagrika/field/raw/humidity";
const char* topic_soil = "innagrika/field/raw/soil_moisture"; // Симулируем случайным числом

DHT dht(DHTPIN, DHTTYPE);
WiFiClient espClient;
PubSubClient client(espClient);

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP32Client-";
    clientId += String(random(0xffff), HEX);
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  setup_wifi();
  client.setServer(mqtt_server, 1883);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Чтение данных (раз в 5 секунд)
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  // Проверка на ошибки чтения
  if (isnan(h) || isnan(t)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
  }

  // --- Отправка Температуры ---
  // Формируем JSON: {"sensor_id": "dht22_01", "value": 24.5}
  String payloadTemp = "{\"sensor_id\": \"dht22_01\", \"value\": " + String(t) + "}";
  client.publish(topic_temp, payloadTemp.c_str());
  
  // --- Отправка Влажности ---
  String payloadHumid = "{\"sensor_id\": \"dht22_01\", \"value\": " + String(h) + "}";
  client.publish(topic_humid, payloadHumid.c_str());

  // --- Симуляция Влажности Почвы (для модели) ---
  // В реальности здесь был бы аналоговый датчик
  float soil = random(30, 60); 
  String payloadSoil = "{\"sensor_id\": \"soil_01\", \"value\": " + String(soil) + "}";
  client.publish(topic_soil, payloadSoil.c_str());

  Serial.print("Sent: Temp="); Serial.print(t);
  Serial.print(" Hum="); Serial.print(h);
  Serial.print(" Soil="); Serial.println(soil);

  delay(5000); // Пауза 5 секунд
}
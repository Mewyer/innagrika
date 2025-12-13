import json
import time
import threading
import numpy as np
from datetime import datetime
from collections import deque
import logging
from typing import Dict, List, Optional
import paho.mqtt.client as mqtt
import websocket

# --- НАСТРОЙКИ ---
class Config:
    # MQTT (Вход данных от Wokwi)
    MQTT_BROKER = "test.mosquitto.org"
    MQTT_PORT = 1883
    MQTT_TOPICS = [
        "innagrika/field/raw/temperature",
        "innagrika/field/raw/humidity", 
        "innagrika/field/raw/soil_moisture"
    ]
    
    # WebSocket (Выход данных на Cloud Server)
    # Убедитесь, что cloud_server.py запущен!
    WEBSOCKET_SERVER = "ws://localhost:8000/ws/edge-data"
    
    # Настройки агрегации (для тестов уменьшили время)
    AGGREGATION_WINDOW = 10  # Агрегация каждые 10 секунд
    MAX_BUFFER_SIZE = 100

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EdgeServer")

# --- МОДЕЛИ ДАННЫХ ---
class DataBuffer:
    def __init__(self):
        self.buffers = {
            "temperature": deque(maxlen=Config.MAX_BUFFER_SIZE),
            "humidity": deque(maxlen=Config.MAX_BUFFER_SIZE),
            "soil_moisture": deque(maxlen=Config.MAX_BUFFER_SIZE)
        }

    def add(self, sensor_type, value):
        if sensor_type in self.buffers:
            self.buffers[sensor_type].append(value)
            logger.debug(f"Buffer add: {sensor_type}={value}")

    def get_aggregate(self):
        """Считаем среднее по накопленным данным"""
        result = {}
        for key, buffer in self.buffers.items():
            if buffer:
                vals = list(buffer)
                result[key] = {
                    "avg": float(np.mean(vals)),
                    "min": float(np.min(vals)),
                    "max": float(np.max(vals))
                }
            # Очищаем буфер после агрегации, чтобы данные не дублировались
            buffer.clear() 
        return result

# --- МАТЕМАТИЧЕСКАЯ МОДЕЛЬ ---
class AgroModel:
    def __init__(self):
        # Параметры модели
        self.soil_water_content = 0.3 # 30%
        self.params = {"evaporation_rate": 0.001, "rain_factor": 0.05}

    def predict(self, inputs: Dict):
        """
        Простой расчет: Влажность почвы = (Текущая + Осадки) - Испарение
        Испарение зависит от Температуры.
        """
        temp = 20.0
        if "temperature" in inputs:
            temp = inputs["temperature"]["avg"]
            
        # Симуляция изменения влажности
        # Чем жарче, тем быстрее сохнет
        evaporation = self.params["evaporation_rate"] * (temp / 10.0)
        self.soil_water_content -= evaporation
        
        # Если есть данные реального датчика почвы, делаем "коррекцию" (фильтр Калмана упрощенно)
        if "soil_moisture" in inputs:
            measured = inputs["soil_moisture"]["avg"] / 100.0 # приводим к 0.0-1.0
            self.soil_water_content = (self.soil_water_content * 0.8) + (measured * 0.2)

        # Ограничения
        self.soil_water_content = max(0.0, min(1.0, self.soil_water_content))
        
        return self.soil_water_content

    def get_forecast(self):
        """Генерируем прогноз на 24 часа вперед (линейное падение)"""
        forecast = []
        val = self.soil_water_content
        for _ in range(24):
            val -= (self.params["evaporation_rate"] * 2) # Прогноз высыхания
            val = max(0, val)
            forecast.append(val)
        return forecast

# --- ГЛАВНЫЙ КЛАСС ---
class EdgeServer:
    def __init__(self):
        self.buffer = DataBuffer()
        self.model = AgroModel()
        self.mqtt_client = mqtt.Client()
        self.ws_app = None
        self.running = True

    # MQTT Callbacks
    def on_mqtt_connect(self, client, userdata, flags, rc):
        logger.info(f"Connected to MQTT Broker (rc={rc})")
        for topic in Config.MQTT_TOPICS:
            client.subscribe(topic)
            logger.info(f"Subscribed to: {topic}")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            # Парсим топик: innagrika/field/raw/temperature -> temperature
            sensor_type = msg.topic.split("/")[-1]
            payload = json.loads(msg.payload.decode())
            value = float(payload.get("value", 0))
            
            logger.info(f"MQTT IN: {sensor_type} = {value}")
            self.buffer.add(sensor_type, value)
        except Exception as e:
            logger.error(f"Error parsing MQTT: {e}")

    # WebSocket Logic
    def send_to_cloud(self, data):
        if self.ws_app and self.ws_app.sock and self.ws_app.sock.connected:
            try:
                self.ws_app.send(json.dumps(data))
                logger.info("--> Sent aggregated data to Cloud")
            except Exception as e:
                logger.error(f"WS Send error: {e}")
        else:
            logger.warning("Cloud WebSocket not connected. Data skipped.")

    def processing_loop(self):
        """Цикл агрегации и моделирования"""
        while self.running:
            time.sleep(Config.AGGREGATION_WINDOW)
            
            # 1. Агрегация
            inputs = self.buffer.get_aggregate()
            
            if not inputs:
                logger.info("No new data to process...")
                continue

            # 2. Моделирование
            current_moisture = self.model.predict(inputs)
            forecast = self.model.get_forecast()

            # 3. Подготовка пакета для облака
            payload = {
                "timestamp": datetime.now().isoformat(),
                "source": "Edge_01",
                "aggregated_data": inputs,
                "model_parameters": self.model.params,
                "predictions": {
                    "current_soil_moisture": current_moisture,
                    "next_24h": forecast
                }
            }

            # 4. Отправка
            self.send_to_cloud(payload)

    def start(self):
        # 1. Запуск MQTT
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        try:
            self.mqtt_client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, 60)
            threading.Thread(target=self.mqtt_client.loop_forever, daemon=True).start()
        except Exception as e:
            logger.error(f"MQTT Connection failed: {e}")
            return

        # 2. Запуск цикла обработки
        threading.Thread(target=self.processing_loop, daemon=True).start()

        # 3. Запуск WebSocket (Блокирует основной поток, поэтому в конце)
        logger.info(f"Connecting to Cloud: {Config.WEBSOCKET_SERVER}")
        # websocket.enableTrace(True) # Раскомментировать для отладки
        self.ws_app = websocket.WebSocketApp(Config.WEBSOCKET_SERVER,
                                             on_open=lambda ws: logger.info("WebSocket Connected to Cloud"),
                                             on_error=lambda ws, err: logger.error(f"WS Error: {err}"),
                                             on_close=lambda ws, status, msg: logger.info("WS Closed"))
        
        # Бесконечный реконнект
        while self.running:
            try:
                self.ws_app.run_forever()
                time.sleep(2) # Пауза перед реконнектом
            except KeyboardInterrupt:
                self.running = False

if __name__ == "__main__":
    edge = EdgeServer()
    try:
        edge.start()
    except KeyboardInterrupt:
        print("Stopping...")
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import json
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CloudServer")

app = FastAPI()

# Менеджер соединений
class ConnectionManager:
    def __init__(self):
        # Подключение Edge-сервера (источник данных)
        self.edge_connection: WebSocket = None
        # Подключения клиентов (браузеры, Varwin)
        self.active_connections: List[WebSocket] = []

    async def connect_edge(self, websocket: WebSocket):
        await websocket.accept()
        self.edge_connection = websocket
        logger.info("Edge-сервер подключен")

    async def connect_client(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Новый веб-клиент подключен")

    def disconnect_edge(self):
        self.edge_connection = None
        logger.info("Edge-сервер отключился")

    def disconnect_client(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("Веб-клиент отключился")

    async def broadcast_to_clients(self, message: str):
        """Пересылка данных от Edge всем клиентам"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Ошибка отправки клиенту: {e}")

manager = ConnectionManager()

# Раздача статики (HTML/CSS/JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get():
    # Отдаем главную страницу
    with open("C:/Users/mewye/Desktop/Иннагрика лол/Edge/static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# Эндпоинт для Edge-сервера (как в конфиге main.py)
@app.websocket("/ws/edge-data")
async def websocket_edge_endpoint(websocket: WebSocket):
    await manager.connect_edge(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Логируем для отладки
            # logger.info(f"Получено от Edge: {data[:100]}...") 
            
            # Сразу пересылаем всем веб-клиентам
            await manager.broadcast_to_clients(data)
    except WebSocketDisconnect:
        manager.disconnect_edge()

# Эндпоинт для Браузера
@app.websocket("/ws/client")
async def websocket_client_endpoint(websocket: WebSocket):
    await manager.connect_client(websocket)
    try:
        while True:
            # Клиент может отправлять команды (опционально), но пока просто слушаем
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_client(websocket)

if __name__ == "__main__":
    # Запуск сервера на порту 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)

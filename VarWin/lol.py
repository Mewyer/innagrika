import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import json
import random
import time
from PIL import Image
import os
import sys

# --- 1. МОДУЛЬ РАБОТЫ С ДАННЫМИ (Генерация или Загрузка) ---
class DataHandler:
    """
    Отвечает за получение данных: либо генерация случайного шума,
    либо чтение файла с диска.
    """
    @staticmethod
    def generate_random_data(num_points=1000, area_size=200):
        print(f">> Генерация случайного ландшафта ({num_points} точек)...")
        data = {
            "type": "scattered_points",
            "timestamp": time.time(),
            "points": []
        }
        
        for _ in range(num_points):
            x = random.uniform(0, area_size)
            y = random.uniform(0, area_size)
            # Сложная функция рельефа
            z = (np.sin(x / 15) + np.cos(y / 20)) * 5 + \
                (np.sin(x / 5) * np.cos(y / 5)) * 2 + 10
            z += random.uniform(-0.5, 0.5)
            
            data["points"].append({
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2)
            })
        return json.dumps(data)

    @staticmethod
    def load_from_file(filepath):
        print(f">> Загрузка данных из файла: {filepath}...")
        if not os.path.exists(filepath):
            print(f"!! Ошибка: Файл {filepath} не найден.")
            sys.exit(1)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = json.load(f)
            return content

# --- 2. ЯДРО ОБРАБОТКИ РЕЛЬЕФА ---
class TerrainCore:
    """
    Преобразует входные данные (точки или матрицы) в единый формат сетки (Grid).
    """
    def __init__(self, resolution=100, height_multiplier=30.0):
        self.resolution = resolution
        self.height_multiplier = height_multiplier # Масштабирование высоты (для 0..1 данных)
        self.grid_x = None
        self.grid_y = None
        self.grid_z = None
        self.extent = None

    def process_data(self, raw_data):
        # 1. Сценарий: Входные данные - это матрица (Список списков), как в вашем файле
        if isinstance(raw_data, list):
            print(">> Обнаружен формат: Матрица высот (Heightmap Matrix).")
            z_matrix = np.array(raw_data)
            
            # Применяем множитель высоты, так как данные 0..1 слишком плоские для 3D
            self.grid_z = z_matrix * self.height_multiplier
            
            rows, cols = self.grid_z.shape
            
            # Создаем координатную сетку по размеру матрицы
            # Допустим, 1 ячейка = 1 метр
            xi = np.linspace(0, cols, cols)
            yi = np.linspace(0, rows, rows)
            self.grid_x, self.grid_y = np.meshgrid(xi, yi)
            self.extent = (0, cols, 0, rows)
            
        # 2. Сценарий: Входные данные - JSON с точками (старый вариант)
        elif isinstance(raw_data, str) or isinstance(raw_data, dict):
            print(">> Обнаружен формат: Облако точек (Scattered Points).")
            data = raw_data if isinstance(raw_data, dict) else json.loads(raw_data)
            
            # Если это JSON объект, но внутри матрица (на всякий случай)
            if isinstance(data, list):
                 return self.process_data(data) # Рекурсивный вызов для списка

            points = data.get("points", [])
            x = np.array([p['x'] for p in points])
            y = np.array([p['y'] for p in points])
            z = np.array([p['z'] for p in points])
            
            self.extent = (min(x), max(x), min(y), max(y))
            xi = np.linspace(min(x), max(x), self.resolution)
            yi = np.linspace(min(y), max(y), self.resolution)
            self.grid_x, self.grid_y = np.meshgrid(xi, yi)
            
            self.grid_z = griddata((x, y), z, (self.grid_x, self.grid_y), method='cubic')
            
            # Зачистка NaN
            mask = np.isnan(self.grid_z)
            self.grid_z[mask] = np.nanmean(self.grid_z)
        
        else:
            print("!! Неизвестный формат данных")
            sys.exit(1)

        print(f">> Рельеф построен. Размер сетки: {self.grid_z.shape}")
        return self.grid_z

# --- 3. ГИДРОЛОГИЯ И СИСТЕМЫ ---
class HydrologySim:
    def __init__(self, terrain_core):
        self.terrain = terrain_core
        self.moisture_map = None
        self.drainage_systems = []
        self.irrigation_systems = []
        
    def initialize_moisture(self):
        # Нормализация высот для расчета физики влаги
        z_min, z_max = np.nanmin(self.terrain.grid_z), np.nanmax(self.terrain.grid_z)
        z_norm = (self.terrain.grid_z - z_min) / (z_max - z_min) if z_max > z_min else self.terrain.grid_z
        
        # Чем ниже, тем влажнее
        self.moisture_map = (1.0 - z_norm) * 0.7 + 0.1 

    def plan_infrastructure(self):
        z = self.terrain.grid_z
        rows, cols = z.shape
        low_threshold = np.percentile(z, 15)
        high_threshold = np.percentile(z, 85)
        
        # Шаг сканирования (чтобы не ставить слишком часто)
        step_r = max(1, rows // 20)
        step_c = max(1, cols // 20)
        
        for r in range(0, rows, step_r):
            for c in range(0, cols, step_c):
                height = z[r, c]
                if height < low_threshold:
                    self.drainage_systems.append((c, r)) # Дренаж в низинах
                elif height > high_threshold:
                    self.irrigation_systems.append((c, r)) # Полив на верхах

    def run_simulation_step(self):
        self.moisture_map -= 0.01 # Испарение
        
        radius = 2
        rows, cols = self.moisture_map.shape
        
        # Эффект полива
        for (cx, cy) in self.irrigation_systems:
            y_min, y_max = max(0, cy-radius), min(rows, cy+radius)
            x_min, x_max = max(0, cx-radius), min(cols, cx+radius)
            self.moisture_map[y_min:y_max, x_min:x_max] += 0.06

        # Эффект дренажа
        for (cx, cy) in self.drainage_systems:
            y_min, y_max = max(0, cy-radius), min(rows, cy+radius)
            x_min, x_max = max(0, cx-radius), min(cols, cx+radius)
            self.moisture_map[y_min:y_max, x_min:x_max] -= 0.09
            
        self.moisture_map = np.clip(self.moisture_map, 0.0, 1.0)

# --- 4. ЭКСПОРТ (OBJ + PNG + JSON) ---
class VarwinExporter:
    @staticmethod
    def export(terrain_core, hydro_sim, output_dir="varwin_export"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # 1. Heightmap PNG
        z = terrain_core.grid_z
        z_norm = (z - np.nanmin(z)) / (np.nanmax(z) - np.nanmin(z))
        img_array = (z_norm * 255).astype(np.uint8)
        Image.fromarray(img_array, mode='L').save(f"{output_dir}/terrain_heightmap.png")
        
        # 2. 3D Model OBJ
        VarwinExporter._generate_obj(terrain_core, f"{output_dir}/terrain_model.obj")
        
        # 3. JSON Config
        objects_manifest = {
            "info": "Y is UP in Unity/Varwin",
            "drainage_points": [],
            "irrigation_points": []
        }
        
        # Координаты для Varwin (X, Y=Height, Z=Depth)
        for (c, r) in hydro_sim.drainage_systems:
            world_x = float(terrain_core.grid_x[r, c])
            world_z = float(terrain_core.grid_y[r, c])
            world_y = float(terrain_core.grid_z[r, c])
            objects_manifest["drainage_points"].append({"x": world_x, "y": world_y, "z": world_z})
            
        for (c, r) in hydro_sim.irrigation_systems:
            world_x = float(terrain_core.grid_x[r, c])
            world_z = float(terrain_core.grid_y[r, c])
            world_y = float(terrain_core.grid_z[r, c])
            objects_manifest["irrigation_points"].append({"x": world_x, "y": world_y, "z": world_z})
            
        with open(f"{output_dir}/scene_manifest.json", "w") as f:
            json.dump(objects_manifest, f, indent=4)
            
        print(f">> Экспорт завершен в папку '{output_dir}'")

    @staticmethod
    def _generate_obj(terrain, filename):
        grid_x = terrain.grid_x
        grid_y = terrain.grid_y 
        grid_z = terrain.grid_z 
        rows, cols = grid_z.shape
        
        print(f">> Генерация OBJ модели ({rows}x{cols} полигонов)...")
        
        with open(filename, 'w') as f:
            f.write(f"# Varwin Terrain {rows}x{cols}\n")
            
            # Вершины (X, Z-height -> Y, Y-depth -> Z)
            for r in range(rows):
                for c in range(cols):
                    vx = grid_x[r, c]
                    vy = grid_z[r, c] 
                    vz = grid_y[r, c]
                    f.write(f"v {vx:.3f} {vy:.3f} {vz:.3f}\n")
            
            # UV
            for r in range(rows):
                for c in range(cols):
                    u = c / (cols - 1)
                    v = r / (rows - 1)
                    f.write(f"vt {u:.3f} {v:.3f}\n")

            # Грани
            for r in range(rows - 1):
                for c in range(cols - 1):
                    i1 = r * cols + c + 1
                    i2 = r * cols + (c + 1) + 1
                    i3 = (r + 1) * cols + c + 1
                    i4 = (r + 1) * cols + (c + 1) + 1
                    f.write(f"f {i1}/{i1} {i3}/{i3} {i2}/{i2}\n")
                    f.write(f"f {i2}/{i2} {i3}/{i3} {i4}/{i4}\n")

# --- 5. ВИЗУАЛИЗАЦИЯ ---
def visualize_simulation(terrain, hydro):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    # Рельеф
    im1 = axes[0].imshow(terrain.grid_z, origin='lower', cmap='terrain')
    axes[0].set_title("Карта высот")
    plt.colorbar(im1, ax=axes[0])
    
    # Влажность
    im2 = axes[1].imshow(hydro.moisture_map, origin='lower', cmap='Blues', vmin=0, vmax=1)
    axes[1].set_title("Влажность почвы")
    plt.colorbar(im2, ax=axes[1])
    
    # Оборудование
    axes[2].imshow(terrain.grid_z, origin='lower', cmap='gray', alpha=0.5)
    
    # Преобразуем индексы в координаты для scatter plot
    dx, dy = [], []
    for (c, r) in hydro.drainage_systems:
        dx.append(c)
        dy.append(r)
        
    ix, iy = [], []
    for (c, r) in hydro.irrigation_systems:
        ix.append(c)
        iy.append(r)
        
    axes[2].scatter(dx, dy, c='red', marker='x', label='Дренаж (Низины)')
    axes[2].scatter(ix, iy, c='blue', marker='o', label='Полив (Верха)')
    axes[2].set_title("Схема оборудования")
    axes[2].legend()
    
    plt.tight_layout()
    plt.show()

# --- MAIN ---
if __name__ == "__main__":
    print("=== DIGITAL TWIN GENERATOR ===")
    print("1. Сгенерировать случайный ландшафт")
    print("2. Загрузить из файла (например, 'map.json')")
    
    choice = input("Выберите действие (1 или 2): ").strip()
    
    raw_data = None
    
    if choice == "2":
        fpath = input("Введите имя файла (по умолчанию 'Кейс №3 - карта высот.json'): ").strip()
        if not fpath:
            fpath = "Кейс №3 - карта высот.json"
        
        # Загрузка
        try:
            raw_data = DataHandler.load_from_file(fpath)
        except Exception as e:
            print(f"Ошибка чтения: {e}")
            sys.exit(1)
            
    else:
        # Генерация
        raw_data = DataHandler.generate_random_data(num_points=1000, area_size=200)

    # Инициализация ядра (height_multiplier=30 сделает карту из 0..1 в 0..30 метров)
    terrain = TerrainCore(height_multiplier=50.0) 
    terrain.process_data(raw_data)
    
    hydro = HydrologySim(terrain)
    hydro.initialize_moisture()
    hydro.plan_infrastructure()
    
    print(">> Симуляция гидрологии...")
    for _ in range(3):
        hydro.run_simulation_step()
        
    VarwinExporter.export(terrain, hydro)
    visualize_simulation(terrain, hydro)
    print("=== ГОТОВО ===")
import json
import numpy as np
import matplotlib.pyplot as plt
from scipy import interpolate
import trimesh

def load_height_data(file_path):
    """Загрузка данных высот из JSON файла"""
    with open(file_path, 'r') as f:
        height_data = json.load(f)
    return np.array(height_data)

def create_dem_grid(height_data, grid_size=(100, 100)):
    """Создание цифровой модели рельефа с интерполяцией"""
    # Получаем размеры исходных данных
    y_len, x_len = height_data.shape
    
    # Создаем координатную сетку для исходных данных
    x_original = np.linspace(0, 1, x_len)
    y_original = np.linspace(0, 1, y_len)
    
    # Создаем интерполятор
    interp_func = interpolate.RectBivariateSpline(
        y_original, x_original, height_data, kx=3, ky=3
    )
    
    # Создаем новую сетку с заданным разрешением
    x_new = np.linspace(0, 1, grid_size[1])
    y_new = np.linspace(0, 1, grid_size[0])
    
    # Интерполируем данные на новую сетку
    dem_grid = interp_func(y_new, x_new)
    
    return dem_grid, (x_new, y_new)

def visualize_heatmap(dem_grid, output_path='heightmap_heatmap.png'):
    """Визуализация тепловой карты рельефа"""
    plt.figure(figsize=(12, 10))
    
    # Создаем тепловую карту
    plt.imshow(dem_grid, cmap='terrain', aspect='auto', 
               extent=[0, 1, 0, 1], origin='lower')
    plt.colorbar(label='Высота (нормализованная)')
    plt.title('Карта высот рельефа', fontsize=16)
    plt.xlabel('Координата X')
    plt.ylabel('Координата Y')
    
    # Сохраняем изображение
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    return output_path

def visualize_3d_surface(dem_grid, output_path='heightmap_3d.png'):
    """Визуализация 3D поверхности рельефа"""
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Создаем координатную сетку для 3D отображения
    x = np.linspace(0, 1, dem_grid.shape[1])
    y = np.linspace(0, 1, dem_grid.shape[0])
    X, Y = np.meshgrid(x, y)
    
    # Отображаем поверхность
    surf = ax.plot_surface(X, Y, dem_grid, cmap='terrain', 
                          linewidth=0, antialiased=True, 
                          alpha=0.8)
    
    ax.set_xlabel('Координата X')
    ax.set_ylabel('Координата Y')
    ax.set_zlabel('Высота')
    ax.set_title('3D модель рельефа', fontsize=16)
    
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label='Высота')
    
    # Сохраняем 3D визуализацию
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    return output_path

def export_to_obj(dem_grid, output_path='heightmap.obj', scale=1.0):
    """Экспорт модели рельефа в формат OBJ (совместимый с Varwin XRMS)"""
    height, width = dem_grid.shape
    
    # Создаем координаты вершин
    vertices = []
    for i in range(height):
        for j in range(width):
            x = j / (width - 1) * scale
            y = i / (height - 1) * scale
            z = dem_grid[i, j] * scale
            vertices.append([x, y, z])
    
    # Создаем грани (треугольники)
    faces = []
    for i in range(height - 1):
        for j in range(width - 1):
            # Индексы вершин для текущего квадрата
            v1 = i * width + j
            v2 = i * width + (j + 1)
            v3 = (i + 1) * width + j
            v4 = (i + 1) * width + (j + 1)
            
            # Два треугольника для квадрата
            faces.append([v1 + 1, v2 + 1, v3 + 1])  # +1 потому что OBJ индексы начинаются с 1
            faces.append([v2 + 1, v4 + 1, v3 + 1])
    
    # Записываем в файл OBJ
    with open(output_path, 'w') as f:
        # Вершины
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        
        # Грани
        for face in faces:
            f.write(f"f {face[0]} {face[1]} {face[2]}\n")
    
    print(f"3D модель экспортирована в {output_path}")
    return output_path

def export_to_stl(dem_grid, output_path='heightmap.stl', scale=1.0):
    """Экспорт модели рельефа в формат STL"""
    height, width = dem_grid.shape
    
    # Создаем координаты вершин
    vertices = []
    for i in range(height):
        for j in range(width):
            x = j / (width - 1) * scale
            y = i / (height - 1) * scale
            z = dem_grid[i, j] * scale
            vertices.append([x, y, z])
    
    # Создаем грани
    faces = []
    for i in range(height - 1):
        for j in range(width - 1):
            v1 = i * width + j
            v2 = i * width + (j + 1)
            v3 = (i + 1) * width + j
            v4 = (i + 1) * width + (j + 1)
            
            # Треугольник 1
            faces.append([v1, v2, v3])
            # Треугольник 2
            faces.append([v2, v4, v3])
    
    # Создаем mesh
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    # Экспортируем в STL
    mesh.export(output_path)
    
    print(f"3D модель экспортирована в {output_path}")
    return output_path

def normalize_height_data(height_data):
    """Нормализация данных высот для лучшей визуализации"""
    min_val = height_data.min()
    max_val = height_data.max()
    
    # Нормализуем к диапазону 0-1
    normalized = (height_data - min_val) / (max_val - min_val)
    
    return normalized

def main():
    # Путь к файлу с данными
    input_file = 'Кейс №3 - карта высот.json'
    
    try:
        # 1. Загрузка данных
        print("Загрузка данных высот...")
        height_data = load_height_data(input_file)
        print(f"Размерность данных: {height_data.shape}")
        
        # 2. Нормализация данных
        print("Нормализация данных...")
        normalized_data = normalize_height_data(height_data)
        
        # 3. Создание цифровой модели рельефа
        print("Создание цифровой модели рельефа...")
        dem_grid, coords = create_dem_grid(normalized_data, grid_size=(200, 200))
        
        # 4. Визуализация тепловой карты
        print("Создание тепловой карты...")
        heatmap_path = visualize_heatmap(dem_grid, 'heightmap_heatmap.png')
        
        # 5. Визуализация 3D поверхности
        print("Создание 3D визуализации...")
        surface_3d_path = visualize_3d_surface(dem_grid, 'heightmap_3d.png')
        
        # 6. Экспорт в 3D форматы
        print("Экспорт в 3D форматы...")
        obj_path = export_to_obj(dem_grid, 'heightmap.obj', scale=10.0)
        stl_path = export_to_stl(dem_grid, 'heightmap.stl', scale=10.0)
        
        print("\n" + "="*50)
        print("ОБРАБОТКА ЗАВЕРШЕНА!")
        print("="*50)
        print(f"Тепловая карта сохранена: {heatmap_path}")
        print(f"3D визуализация сохранена: {surface_3d_path}")
        print(f"3D модель (OBJ) сохранена: {obj_path}")
        print(f"3D модель (STL) сохранена: {stl_path}")
        print("\nФормат OBJ и STL совместим с Varwin XRMS и большинством 3D редакторов.")
        
    except Exception as e:
        print(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    main()
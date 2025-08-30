#!/usr/bin/env python3
"""
Скрипт для автоматического обновления версии приложения.
Автоматическое увеличение номера версии в соответствии с семантическим версионированием.
Использование: python update_version.py [major|minor|patch]
"""


import re # Импорт модуля для работы с регулярными выражениями
import sys # Импорт модуля для работы с системными функциями
from pathlib import Path # Импорт модуля для работы с файловыми путями

def update_version(update_type):
    """
    Функция обновления версии приложения в файле version.py.
    
    Args:
        update_type (str): Тип обновления - major, minor или patch
    
    Returns:
        str | bool: Новая версия или False при ошибке
    """
    # Создание объекта Path для файла version.py
    version_file = Path('version.py')
    # Чтение содержимого файла version.py в строку
    content = version_file.read_text()
    
    # Поиск шаблона версии в формате X.X.X с использованием регулярного выражения
    match = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', content)
    # Проверка наличия совпадения с шаблоном версии
    if not match:
        # Вывод сообщения об ошибке при неверном формате версии
        print("Ошибка: Неверный формат версии в version.py")
        # Возврат False при ошибке
        return False
    
    # Преобразование найденных групп в целые числа
    major, minor, patch = map(int, match.groups())
    
    # Увеличение major версии и сброс minor и patch версий
    if update_type == 'major':
        # Увеличение major версии на 1
        major += 1
        # Сброс minor версии до 0
        minor = 0
        # Сброс patch версии до 0
        patch = 0
    # Увеличение minor версии и сброс patch версии
    elif update_type == 'minor':
        # Увеличение minor версии на 1
        minor += 1
        # Сброс patch версии до 0
        patch = 0
    # Увеличение только patch версии
    elif update_type == 'patch':
        # Увеличение patch версии на 1
        patch += 1
    # Обработка неверного типа обновления
    else:
        # Вывод сообщения об ошибке при неверном типе обновления
        print("Ошибка: Неверный тип обновления. Используйте major, minor или patch")
        # Возврат False при ошибке
        return False
    
    # Формирование строки новой версии
    new_version = f"{major}.{minor}.{patch}"
    
    # Замена старой версии на новую в содержимом файла
    new_content = re.sub(
        # Шаблон для поиска старой версии
        r'__version__ = "\d+\.\d+\.\d+"',
        # Строка с новой версией
        f'__version__ = "{new_version}"',
        # Исходное содержимое файла
        content
    )
    
    # Запись обновленного содержимого обратно в файл
    version_file.write_text(new_content)
    # Вывод сообщения об успешном обновлении версии
    print(f"Версия обновлена до {new_version}")
    # Возврат новой версии
    return new_version

# Проверка запуска скрипта напрямую, а не через импорт
if __name__ == "__main__":
    # Проверка количества аргументов командной строки и их корректности
    if len(sys.argv) != 2 or sys.argv[1] not in ['major', 'minor', 'patch']:
        # Вывод сообщения о правильном использовании скрипта
        print("Использование: python update_version.py [major|minor|patch]")
        # Завершение работы скрипта с кодом ошибки 1
        sys.exit(1)
    
    # Вызов функции обновления версии с переданным аргументом
    update_version(sys.argv[1])
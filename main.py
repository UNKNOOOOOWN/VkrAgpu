# main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    """
    Основная функция приложения.
    Создание и запуск главного окна приложения.
    """
    app = QApplication(sys.argv)
    
    # Загрузка стилей приложения
    try:
        with open('ui/styles.qss', 'r') as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Файл стилей не найден. Используются стандартные стили.")
    
    # Создание и отображение главного окна
    window = MainWindow()
    window.show()
    
    # Запуск основного цикла приложения
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt

# Импортируем нашу версию для User-Agent
from ui.main_window import MainWindow
from version import __version__

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pulse_currency.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def setup_application():
    """
    Настройка приложения Qt.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("PulseCurrency")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("PulseCurrency")
    
    # Настройка шрифта по умолчанию
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Установка иконки приложения (если есть)
    try:
        icon_path = Path("resources/icon.png")
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception as e:
        logger.debug(f"Не удалось установить иконку приложения: {e}")
    
    return app

def load_styles(app):
    """
    Загрузка стилей приложения.
    """
    try:
        styles_path = Path("ui/styles.qss")
        if styles_path.exists():
            with open(styles_path, 'r', encoding='utf-8') as f:
                app.setStyleSheet(f.read())
            logger.info("Стили приложения успешно загружены")
        else:
            logger.warning("Файл стилей не найден. Используются стандартные стили Qt.")
    except Exception as e:
        logger.error(f"Ошибка загрузки стилей: {e}")
        QMessageBox.warning(
            None,
            "Ошибка стилей",
            f"Не удалось загрузить стили приложения:\n{str(e)}\n\n"
            "Приложение будет использовать стандартные стили Qt."
        )

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Глобальный обработчик исключений.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.error("Необработанное исключение:", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Показываем сообщение об ошибке пользователю
    try:
        error_msg = f"""Произошла непредвиденная ошибка:

Тип: {exc_type.__name__}
Сообщение: {str(exc_value)}

Подробности записаны в лог-файл."""
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Ошибка приложения")
        msg_box.setText("Произошла непредвиденная ошибка")
        msg_box.setInformativeText(error_msg)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    except Exception:
        # Если даже обработчик ошибок сломался
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

def main():
    """
    Основная функция приложения.
    Создание и запуск главного окна приложения.
    """
    try:
        logger.info(f"Запуск PulseCurrency версии {__version__}")
        logger.info(f"Python версия: {sys.version}")
        logger.info(f"Платформа: {sys.platform}")
        
        # Установка глобального обработчика исключений
        sys.excepthook = handle_exception
        
        # Настройка приложения
        app = setup_application()
        
        # Загрузка стилей
        load_styles(app)
        
        # Создание и отображение главного окна
        logger.info("Создание главного окна...")
        window = MainWindow()
        window.show()
        
        logger.info("Приложение успешно запущено")
        
        # Запуск основного цикла приложения
        exit_code = app.exec()
        
        logger.info(f"Приложение завершено с кодом: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        
        # Показываем сообщение об ошибке
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"Не удалось запустить приложение:\n{str(e)}\n\n"
            "Проверьте лог-файл для получения дополнительной информации."
        )
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
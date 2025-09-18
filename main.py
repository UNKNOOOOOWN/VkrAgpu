import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtCore import Qt, QTimer

# Импортируем утилиты из core
from core import load_config, setup_logging_from_config, get_config_value
from version import __version__

# Инициализируем логирование с минимальными настройками
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_application(config: dict):
    """
    Настройка приложения Qt с учетом конфигурации.
    """
    app = QApplication(sys.argv)
    
    # Принудительно устанавливаем темную тему
    config['ui']['theme'] = 'dark'
    
    # Устанавливаем метаданные приложения из конфига
    app_name = get_config_value(config, 'app.name', 'PulseCurrency')
    app_version = get_config_value(config, 'app.version', __version__)
    
    app.setApplicationName(app_name)
    app.setApplicationVersion(app_version)
    app.setOrganizationName("PulseCurrency")
    
    # Настройка шрифта по умолчанию
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    return app

def load_styles(app: QApplication, config: dict):
    """
    Загрузка стилей приложения с учетом темы из конфига.
    """
    try:
        styles_path = Path("ui/styles.qss")
        if styles_path.exists():
            with open(styles_path, 'r', encoding='utf-8') as f:
                styles = f.read()
                
                # Применяем темную тему
                styles += "\n/* Dark theme applied */"
                
                # Удаляем проблемные свойства анимации
                styles = styles.replace('animation: progressAnimation 2s infinite;', '')
                styles = styles.replace('@keyframes progressAnimation', '/* @keyframes progressAnimation */')
                
                app.setStyleSheet(styles)
            logger.info("Стили приложения успешно загружены")
        else:
            logger.warning("Файл стилей не найден. Используются стандартные стили Qt.")
    except Exception as e:
        logger.error(f"Ошибка загрузки стилей: {e}")

def show_splash_screen(config: dict):
    """
    Показывает экран загрузки с информацией из конфига.
    """
    try:
        splash_pix = QPixmap(300, 200)
        splash_pix.fill(Qt.GlobalColor.darkGray)
        
        splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
        splash.setFont(QFont("Segoe UI", 10))
        
        app_name = get_config_value(config, 'app.name', 'PulseCurrency')
        app_version = get_config_value(config, 'app.version', __version__)
        
        splash.showMessage(f"Загрузка {app_name} v{app_version}...\nПодождите пожалуйста", 
                          Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                          Qt.GlobalColor.white)
        splash.show()
        
        QApplication.processEvents()
        return splash
    except Exception as e:
        logger.error(f"Ошибка создания splash screen: {e}")
        return None

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
        # Установка глобального обработчика исключений
        sys.excepthook = handle_exception
        
        # Загружаем конфигурацию
        config = load_config("config.json")
        
        # Настраиваем логирование на основе конфига
        setup_logging_from_config(config)
        
        app_name = get_config_value(config, 'app.name', 'PulseCurrency')
        app_version = get_config_value(config, 'app.version', __version__)
        app_description = get_config_value(config, 'app.description', 'Анализатор динамики курсов валют')
        
        logger.info(f"Запуск {app_name} версии {app_version}")
        logger.info(f"Описание: {app_description}")
        logger.info(f"Python версия: {sys.version}")
        logger.info(f"Платформа: {sys.platform}")
        
        # Настройка приложения
        app = setup_application(config)
        
        # Показываем экран загрузки
        splash = show_splash_screen(config)
        
        # Загрузка стилей
        load_styles(app, config)
        
        if splash:
            splash.showMessage("Инициализация данных...", 
                             Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                             Qt.GlobalColor.white)
            QApplication.processEvents()
        
        # Создание главного окна с передачей конфига
        from ui.main_window import MainWindow
        window = MainWindow(config=config, load_data=False)
        
        if splash:
            splash.finish(window)
        
        # Устанавливаем размер окна из конфига
        window_width = get_config_value(config, 'ui.default_window_width', 1200)
        window_height = get_config_value(config, 'ui.default_window_height', 800)
        window.resize(window_width, window_height)
        
        window.show()
        
        # Откладываем загрузку данных на после показа окна
        QTimer.singleShot(100, window.load_initial_data)
        
        logger.info("Приложение успешно запущено")
        
        # Запуск основного цикла приложения
        exit_code = app.exec()
        
        logger.info(f"Приложение завершено с кодом: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        
        if 'splash' in locals():
            splash.hide()
            
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
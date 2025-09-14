import sys
import logging
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtCore import Qt, QTimer

# Импортируем нашу версию для User-Agent
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

def load_config():
    """
    Загрузка конфигурации из config.json с значениями по умолчанию.
    """
    config_path = Path("config.json")
    default_config = {
        "app": {
            "name": "PulseCurrency",
            "version": "0.5.2",
            "author": "PulseCurrency Team",
            "description": "Анализатор динамики курсов валют"
        },
        "api": {
            "base_url": "https://www.cbr-xml-daily.ru",
            "timeout": 10,
            "max_retries": 3,
            "retry_delay": 2,
            "user_agent": f"PulseCurrency/{__version__} (https://github.com/UNKNOOOOOWN/VkrAgpu)"
        },
        "data": {
            "initial_load_days": 3,
            "max_chart_days": 7,
            "default_chart_days": 3,
            "cache_enabled": True,
            "cache_duration_hours": 12,
            "daily_cache_duration_hours": 1
        },
        "ui": {
            "auto_refresh_minutes": 30,
            "table_show_volatility": False,
            "default_window_width": 1200,
            "default_window_height": 800,
            "theme": "light"
        },
        "performance": {
            "max_concurrent_requests": 2,
            "request_timeout": 15,
            "enable_preloading": True,
            "preload_currencies": ["USD", "EUR", "GBP", "CNY"]
        },
        "logging": {
            "level": "INFO",
            "log_to_file": True,
            "log_filename": "pulse_currency.log",
            "max_log_size_mb": 10,
            "backup_count": 3
        }
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                logger.info("Конфигурационный файл успешно загружен")
                
                # Глубокое объединение конфигов
                def deep_merge(default, user):
                    for key, value in user.items():
                        if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                            deep_merge(default[key], value)
                        else:
                            default[key] = value
                    return default
                
                return deep_merge(default_config, user_config)
                
        except Exception as e:
            logger.error(f"Ошибка загрузки config.json: {e}")
            logger.info("Используются настройки по умолчанию")
            return default_config
    else:
        logger.warning("Файл config.json не найден. Используются настройки по умолчанию")
        return default_config

def setup_application(config):
    """
    Настройка приложения Qt с учетом конфигурации.
    """
    app = QApplication(sys.argv)
    app.setApplicationName(config['app']['name'])
    app.setApplicationVersion(config['app']['version'])
    app.setOrganizationName("PulseCurrency")
    
    # Настройка шрифта по умолчанию
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Установка размеров окна из конфига
    window_width = config['ui'].get('default_window_width', 1200)
    window_height = config['ui'].get('default_window_height', 800)
    
    return app

def setup_logging(config):
    """
    Настройка логирования на основе конфигурации.
    """
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    
    # Очищаем существующие обработчики
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Настраиваем логирование
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_config.get('log_to_file', True):
        log_filename = log_config.get('log_filename', 'pulse_currency.log')
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

def load_styles(app, config):
    """
    Загрузка стилей приложения с учетом темы из конфига.
    """
    try:
        styles_path = Path("ui/styles.qss")
        if styles_path.exists():
            with open(styles_path, 'r', encoding='utf-8') as f:
                styles = f.read()
                
                # Применяем тему из конфига
                theme = config['ui'].get('theme', 'light')
                if theme == 'dark':
                    # Можно добавить преобразование в темную тему
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

def show_splash_screen(config):
    """
    Показывает экран загрузки.
    """
    try:
        splash_pix = QPixmap(300, 200)
        splash_pix.fill(Qt.GlobalColor.white)
        
        splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
        splash.setFont(QFont("Segoe UI", 10))
        
        app_name = config['app']['name']
        version = config['app']['version']
        
        splash.showMessage(f"Загрузка {app_name} v{version}...\nПодождите пожалуйста", 
                          Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                          Qt.GlobalColor.black)
        splash.show()
        
        QApplication.processEvents()
        return splash
    except Exception:
        return None

def main():
    """
    Основная функция приложения.
    Создание и запуск главного окна приложения.
    """
    try:
        # Загружаем конфигурацию первым делом
        config = load_config()
        
        # Настраиваем логирование на основе конфига
        setup_logging(config)
        
        logger.info(f"Запуск {config['app']['name']} версии {config['app']['version']}")
        logger.info(f"Описание: {config['app']['description']}")
        
        # Настройка приложения
        app = setup_application(config)
        
        # Показываем экран загрузки
        splash = show_splash_screen(config)
        
        # Загрузка стилей
        load_styles(app, config)
        
        if splash:
            splash.showMessage("Инициализация данных...", 
                             Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, 
                             Qt.GlobalColor.black)
            QApplication.processEvents()
        
        # Создание главного окна с передачей конфига
        from ui.main_window import MainWindow
        window = MainWindow(config=config, load_data=False)
        
        if splash:
            splash.finish(window)
        
        # Устанавливаем размер окна из конфига
        window_width = config['ui'].get('default_window_width', 1200)
        window_height = config['ui'].get('default_window_height', 800)
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
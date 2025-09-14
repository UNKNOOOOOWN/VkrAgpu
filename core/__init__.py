"""
Утилиты для работы с конфигурацией и общие вспомогательные функции.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

def get_config_value(config: Dict, keys: Union[str, List[str]], default: Any = None) -> Any:
    """
    Безопасное получение значения из конфига по цепочке ключей.
    
    Args:
        config: Словарь с конфигурацией
        keys: Ключ или список ключей для доступа к значению
        default: Значение по умолчанию если ключ не найден
        
    Returns:
        Значение из конфига или default
        
    Examples:
        >>> config = {'api': {'timeout': 10}}
        >>> get_config_value(config, ['api', 'timeout'], 5)
        10
        >>> get_config_value(config, 'api.timeout', 5)
        10
        >>> get_config_value(config, ['api', 'retries'], 3)
        3
    """
    if not config or not keys:
        return default
    
    # Поддерживаем как строку с точками, так и список ключей
    if isinstance(keys, str):
        keys = keys.split('.')
    
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def deep_merge(default_config: Dict, user_config: Dict) -> Dict:
    """
    Глубокое объединение двух конфигов. Приоритет у user_config.
    
    Args:
        default_config: Конфиг по умолчанию
        user_config: Пользовательский конфиг
        
    Returns:
        Объединенный конфиг
    """
    result = default_config.copy()
    
    for key, value in user_config.items():
        if (key in result and 
            isinstance(result[key], dict) and 
            isinstance(value, dict)):
            # Рекурсивное объединение вложенных словарей
            result[key] = deep_merge(result[key], value)
        else:
            # Замена или добавление значения
            result[key] = value
    
    return result

def load_config(config_path: Union[str, Path] = "config.json") -> Dict:
    """
    Загрузка конфигурации из JSON файла.
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        Словарь с конфигурацией
    """
    config_path = Path(config_path)
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
            "retry_delay": 2
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
                logger.info(f"Конфигурационный файл загружен: {config_path}")
                
                # Объединяем с дефолтными значениями
                return deep_merge(default_config, user_config)
                
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в {config_path}: {e}")
            return default_config
        except Exception as e:
            logger.error(f"Ошибка загрузки конфига {config_path}: {e}")
            return default_config
    else:
        logger.warning(f"Файл конфигурации {config_path} не найден. Используются настройки по умолчанию.")
        return default_config

def save_config(config: Dict, config_path: Union[str, Path] = "config.json") -> bool:
    """
    Сохранение конфигурации в файл.
    
    Args:
        config: Словарь с конфигурацией
        config_path: Путь для сохранения файла
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        config_path = Path(config_path)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False, sort_keys=True)
        logger.info(f"Конфигурация сохранена в {config_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения конфига {config_path}: {e}")
        return False

def validate_config(config: Dict) -> List[str]:
    """
    Валидация конфигурации. Проверяет обязательные поля и типы.
    
    Args:
        config: Словарь с конфигурацией для проверки
        
    Returns:
        Список ошибок валидации (пустой если ошибок нет)
    """
    errors = []
    
    # Проверяем обязательные секции
    required_sections = ['api', 'data', 'ui']
    for section in required_sections:
        if section not in config:
            errors.append(f"Отсутствует обязательная секция: {section}")
    
    # Проверяем типы значений
    if 'api' in config:
        api_config = config['api']
        if not isinstance(api_config.get('timeout', 10), (int, float)):
            errors.append("api.timeout должен быть числом")
        if not isinstance(api_config.get('max_retries', 3), int):
            errors.append("api.max_retries должен быть целым числом")
    
    if 'data' in config:
        data_config = config['data']
        if not isinstance(data_config.get('max_chart_days', 7), int):
            errors.append("data.max_chart_days должен быть целым числом")
        if not isinstance(data_config.get('cache_enabled', True), bool):
            errors.append("data.cache_enabled должен быть boolean")
    
    return errors

def get_cache_dir() -> Path:
    """
    Возвращает путь к директории кэша.
    
    Returns:
        Path объект директории кэша
    """
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)
    return cache_dir

def get_data_dir() -> Path:
    """
    Возвращает путь к директории данных.
    
    Returns:
        Path объект директории данных
    """
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir

def setup_logging_from_config(config: Dict) -> None:
    """
    Настройка логирования на основе конфигурации.
    
    Args:
        config: Словарь с конфигурацией
    """
    log_config = get_config_value(config, 'logging', {})
    
    # Уровень логирования
    log_level = getattr(logging, log_config.get('level', 'INFO'), logging.INFO)
    
    # Очищаем существующие обработчики
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Обработчики
    handlers = []
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # Файловый обработчик если включен
    if log_config.get('log_to_file', True):
        try:
            from logging.handlers import RotatingFileHandler
            
            log_filename = log_config.get('log_filename', 'pulse_currency.log')
            max_size = log_config.get('max_log_size_mb', 10) * 1024 * 1024
            backup_count = log_config.get('backup_count', 3)
            
            file_handler = RotatingFileHandler(
                log_filename, 
                maxBytes=max_size, 
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception as e:
            logger.error(f"Ошибка создания файлового обработчика: {e}")
    
    # Настраиваем корневой логгер
    logging.basicConfig(level=log_level, handlers=handlers)

# Экспортируем основные утилиты для удобного импорта
__all__ = [
    'get_config_value',
    'deep_merge',
    'load_config',
    'save_config',
    'validate_config',
    'get_cache_dir',
    'get_data_dir',
    'setup_logging_from_config'
]
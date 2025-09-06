"""
Модуль для работы с API Центрального Банка России.
Предоставляет функционал для получения актуальных курсов валют с кэшированием.
"""

# Стандартные библиотеки Python
import sys
import os
import requests
from datetime import datetime, date, timedelta
import json
import logging
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from version import __version__

# Настройка системы логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CBRApiClient:
    """
    Клиент для работы с API Центрального Банка России.
    Обеспечивает получение актуальных курсов валют с обработкой ошибок и кэшированием.
    """
    
    BASE_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self):
        """
        Инициализация клиента API с настройками подключения и кэширования.
        """
        self.last_update = None
        self.session = requests.Session()
        self.session.timeout = (5, 10)
        self.session.headers.update({
            'User-Agent': f'PulseCurrency/{__version__} (https://github.com/UNKNOOOOOWN/VkrAgpu)'
        })
        
        # Инициализация кэширования
        self.cache_dir = "cache"
        self._ensure_cache_dir()
        
        logger.info(f"Установлен User-Agent: {self.session.headers['User-Agent']}")

    def _ensure_cache_dir(self):
        """Создает папку для кэша если её нет"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info(f"Создана директория кэша: {self.cache_dir}")
    
    def _get_cache_filename(self, target_date: date) -> str:
        """Генерирует имя файла для кэша на основе даты"""
        return os.path.join(self.cache_dir, f"rates_{target_date.strftime('%Y%m%d')}.json")
    
    def _load_from_cache(self, target_date: date):
        """Загружает данные из кэша для указанной даты"""
        cache_file = self._get_cache_filename(target_date)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Данные загружены из кэша: {target_date}")
                    return data
            except Exception as e:
                logger.error(f"Ошибка загрузки из кэша {cache_file}: {e}")
        return None
    
    def _save_to_cache(self, data: dict, target_date: date):
        """Сохраняет данные в кэш для указанной даты"""
        cache_file = self._get_cache_filename(target_date)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Данные сохранены в кэш: {target_date}")
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш {cache_file}: {e}")
    
    def _get_cache_date_from_data(self, data: dict) -> date:
        """Извлекает дату из данных API и преобразует в объект date"""
        if 'Date' in data:
            try:
                # Преобразуем строку даты из API в объект datetime
                date_str = data['Date'].split('T')[0]  # Берем только часть с датой
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка парсинга даты из API: {e}")
        return date.today()
    
    def _get_last_available_cached_data(self):
        """Пытается найти последние доступные данные в кэше"""
        try:
            # Проверяем последние 7 дней
            for days_back in range(0, 8):
                check_date = date.today() - timedelta(days=days_back)
                cached_data = self._load_from_cache(check_date)
                if cached_data:
                    logger.info(f"Найдены кэшированные данные за: {check_date}")
                    return cached_data
        except Exception as e:
            logger.error(f"Ошибка поиска в кэше: {e}")
        return None

    def get_rates(self):
        """
        Получение актуальных курсов валют с API ЦБ РФ с использованием кэширования.
        
        Returns:
            dict | None: Данные о курсах валют или None в случае ошибки
        """
        # Сначала проверяем кэш на сегодняшнюю дату
        cached_data = self._load_from_cache(date.today())
        if cached_data:
            logger.info("Используются кэшированные данные за сегодня")
            self.last_update = datetime.now()
            return cached_data
        
        # Если в кэше нет данных за сегодня, делаем запрос к API
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Запрос данных с API ЦБ РФ (попытка {attempt + 1}/{self.MAX_RETRIES})")
                
                response = self.session.get(self.BASE_URL)
                response.raise_for_status()
                
                data = response.json()
                
                if not self._validate_data(data):
                    raise ValueError("Неверная структура данных от API")
                
                # Определяем дату данных и сохраняем в кэш
                data_date = self._get_cache_date_from_data(data)
                self._save_to_cache(data, data_date)
                
                self.last_update = datetime.now()
                logger.info(f"Данные успешно получены и сохранены в кэш, время: {self.last_update}")
                
                return data

            except requests.exceptions.RequestException as e:
                logger.warning(f"Ошибка сети при попытке {attempt + 1}: {e}")
                
                if attempt == self.MAX_RETRIES - 1:
                    logger.warning("Все попытки подключения к API завершились ошибкой, пробуем использовать кэш")
                    # При полном сбое сети пытаемся использовать последние доступные кэшированные данные
                    return self._get_last_available_cached_data()
                
                time.sleep(self.RETRY_DELAY * (2 ** attempt))
                
            except ValueError as e:
                logger.error(f"Ошибка обработки данных: {e}")
                return self._get_last_available_cached_data()
                
            except Exception as e:
                logger.error(f"Непредвиденная ошибка: {e}")
                return self._get_last_available_cached_data()
        
        return None

    def _validate_data(self, data):
        """
        Проверка корректности и полноты полученных данных от API.
        """
        required_keys = ['Date', 'PreviousDate', 'Valute']
        if not all(key in data for key in required_keys):
            logger.error("Отсутствуют обязательные ключи в ответе API")
            return False
        
        required_currencies = ['USD', 'EUR', 'GBP', 'CNY']
        valute_data = data.get('Valute', {})
        
        for currency in required_currencies:
            if currency not in valute_data:
                logger.error(f"Отсутствуют данные по валюте: {currency}")
                return False
                
            currency_data = valute_data[currency]
            required_currency_fields = ['ID', 'NumCode', 'CharCode', 'Nominal', 'Name', 'Value', 'Previous']
            if not all(field in currency_data for field in required_currency_fields):
                logger.error(f"Неполные данные по валюте: {currency}")
                return False
        
        return True
    
    def clear_old_cache(self, days_to_keep: int = 30):
        """
        Очищает старые файлы кэша.
        
        Args:
            days_to_keep (int): Количество дней для хранения кэша (по умолчанию 30)
        """
        try:
            deleted_count = 0
            for filename in os.listdir(self.cache_dir):
                if filename.startswith("rates_") and filename.endswith(".json"):
                    filepath = os.path.join(self.cache_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    if (datetime.now() - file_time).days > days_to_keep:
                        os.remove(filepath)
                        deleted_count += 1
            logger.info(f"Очищено файлов кэша: {deleted_count}")
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")


# Тестирование функционала модуля при прямом запуске
if __name__ == "__main__":
    client = CBRApiClient()
    
    rates = client.get_rates()
    
    if rates:
        print("Данные успешно получены!")
        print(f"Время обновления: {rates['Date']}")
        print(f"USD: {rates['Valute']['USD']['Value']} руб.")
        print(f"EUR: {rates['Valute']['EUR']['Value']} руб.")
        print(f"GBP: {rates['Valute']['GBP']['Value']} руб.")
        print(f"CNY: {rates['Valute']['CNY']['Value']} руб.")
        
        # Показываем информацию о кэше
        cache_file = client._get_cache_filename(date.today())
        print(f"\nДанные сохранены в кэш: {cache_file}")
    else:
        print("Не удалось получить данные от API ЦБ РФ")
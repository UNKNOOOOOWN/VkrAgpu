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
from typing import Optional, Dict, Any

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
    
    def _load_from_cache(self, target_date: date) -> Optional[Dict[str, Any]]:
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
    
    def _save_to_cache(self, data: Dict[str, Any], target_date: date):
        """Сохраняет данные в кэш для указанной даты"""
        cache_file = self._get_cache_filename(target_date)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Данные сохранены в кэш: {target_date}")
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш {cache_file}: {e}")
    
    def _get_cache_date_from_data(self, data: Dict[str, Any]) -> date:
        """Извлекает дату из данных API и преобразует в объект date"""
        if 'Date' in data:
            try:
                # Преобразуем строку даты из API в объект datetime
                date_str = data['Date'].split('T')[0]  # Берем только часть с датой
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка парсинга даты из API: {e}")
        return date.today()
    
    def _get_last_available_cached_data(self) -> Optional[Dict[str, Any]]:
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

    def _build_url_for_date(self, target_date: date) -> str:
        """Строит URL для запроса данных на определенную дату"""
        if target_date == date.today():
            return self.BASE_URL
        else:
            return f"https://www.cbr-xml-daily.ru/archive/{target_date.year}/{target_date.month:02d}/{target_date.day:02d}/daily_json.js"

    def get_rates(self, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """
        Получение актуальных курсов валют с API ЦБ РФ с использованием кэширования.
        
        Args:
            target_date (date, optional): Конкретная дата для получения курсов. 
                                         Если None - используется текущая дата.
        
        Returns:
            dict | None: Данные о курсах валют или None в случае ошибки
        """
        # Определяем дату для запроса
        if target_date is None:
            target_date = date.today()
        
        # Сначала проверяем кэш на указанную дату
        cached_data = self._load_from_cache(target_date)
        if cached_data:
            logger.info(f"Используются кэшированные данные за {target_date}")
            self.last_update = datetime.now()
            return cached_data
        
        # Формируем URL для запроса
        url = self._build_url_for_date(target_date)
        
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Запрос данных с API ЦБ РФ за {target_date} (попытка {attempt + 1}/{self.MAX_RETRIES})")
                logger.info(f"URL: {url}")
                
                response = self.session.get(url)
                response.raise_for_status()
                
                data = response.json()
                
                if not self._validate_data(data):
                    raise ValueError("Неверная структура данных от API")
                
                # Сохраняем в кэш
                data_date = self._get_cache_date_from_data(data)
                self._save_to_cache(data, data_date)
                
                self.last_update = datetime.now()
                logger.info(f"Данные за {data_date} успешно получены и сохранены в кэш")
                
                return data

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.warning(f"Данные за {target_date} не найдены на сервере")
                    return None
                else:
                    logger.warning(f"HTTP ошибка {e.response.status_code} при попытке {attempt + 1}: {e}")
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Ошибка подключения при попытке {attempt + 1}: {e}")
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"Таймаут подключения при попытке {attempt + 1}: {e}")
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Ошибка сети при попытке {attempt + 1}: {e}")
                
            except ValueError as e:
                logger.error(f"Ошибка обработки данных: {e}")
                # При ошибке валидации пробуем использовать кэш
                return self._get_last_available_cached_data()
                
            except Exception as e:
                logger.error(f"Непредвиденная ошибка при попытке {attempt + 1}: {e}")
                # При любой другой ошибке пробуем использовать кэш
                return self._get_last_available_cached_data()
            
            # Задержка перед повторной попыткой
            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_DELAY * (2 ** attempt)
                logger.info(f"Повторная попытка через {delay} секунд...")
                time.sleep(delay)
        
        # Если все попытки неудачны, пробуем использовать последние кэшированные данные
        logger.warning("Все попытки подключения к API завершились ошибкой, пробуем использовать кэш")
        return self._get_last_available_cached_data()

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Проверка корректности и полноты полученных данных от API.
        """
        required_keys = ['Date', 'PreviousDate', 'Valute']
        if not all(key in data for key in required_keys):
            logger.error("Отсутствуют обязательные ключи в ответе API")
            return False
        
        # Проверяем наличие основных валют
        valute_data = data.get('Valute', {})
        if not valute_data:
            logger.error("Отсутствуют данные о валютах")
            return False
            
        # Проверяем структуру данных для первой валюты (представительной проверки)
        first_currency = next(iter(valute_data.values()), None)
        if first_currency:
            required_currency_fields = ['ID', 'NumCode', 'CharCode', 'Nominal', 'Name', 'Value', 'Previous']
            if not all(field in first_currency for field in required_currency_fields):
                logger.error("Неполные данные по валютам")
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
            current_time = datetime.now()
            
            for filename in os.listdir(self.cache_dir):
                if filename.startswith("rates_") and filename.endswith(".json"):
                    filepath = os.path.join(self.cache_dir, filename)
                    
                    # Получаем время создания файла
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    
                    # Проверяем, нужно ли удалить файл
                    if (current_time - file_time).days > days_to_keep:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.debug(f"Удален старый файл кэша: {filename}")
            
            logger.info(f"Очищено файлов кэша: {deleted_count}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о кэше.
        
        Returns:
            dict: Информация о файлах кэша
        """
        cache_info = {
            'total_files': 0,
            'oldest_file': None,
            'newest_file': None,
            'total_size_kb': 0
        }
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.startswith("rates_") and filename.endswith(".json"):
                    filepath = os.path.join(self.cache_dir, filename)
                    cache_info['total_files'] += 1
                    cache_info['total_size_kb'] += os.path.getsize(filepath) / 1024
                    
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    
                    if cache_info['oldest_file'] is None or file_time < cache_info['oldest_file']:
                        cache_info['oldest_file'] = file_time
                    
                    if cache_info['newest_file'] is None or file_time > cache_info['newest_file']:
                        cache_info['newest_file'] = file_time
                        
        except Exception as e:
            logger.error(f"Ошибка получения информации о кэше: {e}")
        
        return cache_info


# Тестирование функционала модуля при прямом запуске
if __name__ == "__main__":
    client = CBRApiClient()
    
    # Тестируем получение текущих данных
    print("=== ТЕКУЩИЕ ДАННЫЕ ===")
    rates = client.get_rates()
    
    if rates:
        print("Данные успешно получены!")
        print(f"Время обновления: {rates['Date']}")
        print(f"USD: {rates['Valute']['USD']['Value']} руб.")
        print(f"EUR: {rates['Valute']['EUR']['Value']} руб.")
        print(f"GBP: {rates['Valute']['GBP']['Value']} руб.")
        print(f"CNY: {rates['Valute']['CNY']['Value']} руб.")
    else:
        print("Не удалось получить текущие данные")
    
    # Тестируем информацию о кэше
    print("\n=== ИНФОРМАЦИЯ О КЭШЕ ===")
    cache_info = client.get_cache_info()
    print(f"Файлов в кэше: {cache_info['total_files']}")
    print(f"Размер кэша: {cache_info['total_size_kb']:.2f} KB")
    
    if cache_info['oldest_file']:
        print(f"Самый старый файл: {cache_info['oldest_file']}")
    if cache_info['newest_file']:
        print(f"Самый новый файл: {cache_info['newest_file']}")
    
    # Очистка старых файлов (можно раскомментировать для тестирования)
    # client.clear_old_cache(7)
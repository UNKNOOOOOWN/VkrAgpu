"""
Модуль для работы с API Центрального Банка России.
Предоставляет функционал для получения актуальных курсов валют с кэшированием.
Поддерживает синхронные и асинхронные запросы.
"""

# Стандартные библиотеки Python
import sys
import os
import requests
from datetime import datetime, date, timedelta
import json
import logging
import time
from typing import Optional, Dict, Any, List

# PyQt6 для асинхронной работы
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from version import __version__

# Настройка системы логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApiSignals(QObject):
    """Сигналы для асинхронной работы API"""
    data_ready = pyqtSignal(dict, str)  # data, currency_code
    error_occurred = pyqtSignal(str, str)  # error_message, currency_code
    progress_updated = pyqtSignal(int, int, str)  # current, total, currency_code
    finished = pyqtSignal()


class AsyncApiWorker(QRunnable):
    """
    Асинхронный воркер для получения данных о курсах валют.
    Работает в отдельном потоке и не блокирует UI.
    """
    
    def __init__(self, currency_code: str, dates: List[date], cache_dir: str = "cache", config: Optional[Dict] = None):
        super().__init__()
        self.currency_code = currency_code
        self.dates = dates
        self.cache_dir = cache_dir
        self.config = config or {}
        self.signals = ApiSignals()
        self._is_running = False
        
        # Создаем директорию кэша если её нет
        os.makedirs(cache_dir, exist_ok=True)

    def run(self):
        """Основной метод выполнения воркера"""
        self._is_running = True
        try:
            total_dates = len(self.dates)
            result_data = {}
            
            for i, target_date in enumerate(self.dates):
                if not self._is_running:
                    break
                    
                # Обновляем прогресс
                self.signals.progress_updated.emit(i + 1, total_dates, self.currency_code)
                
                # Пытаемся получить данные из кэша
                cached_data = self._load_from_cache(target_date)
                if cached_data:
                    result_data[target_date.strftime('%Y-%m-%d')] = cached_data
                    continue
                
                # Если нет в кэше, запрашиваем из API
                api_data = self._fetch_from_api(target_date)
                if api_data:
                    result_data[target_date.strftime('%Y-%m-%d')] = api_data
                    self._save_to_cache(api_data, target_date)
            
            if self._is_running:
                self.signals.data_ready.emit(result_data, self.currency_code)
                
        except Exception as e:
            error_msg = f"Ошибка получения данных для {self.currency_code}: {str(e)}"
            logger.error(error_msg)
            if self._is_running:
                self.signals.error_occurred.emit(error_msg, self.currency_code)
        finally:
            self.signals.finished.emit()
            self._is_running = False

    def stop(self):
        """Остановка выполнения воркера"""
        self._is_running = False

    def _load_from_cache(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Загружает данные из кэша для указанной даты"""
        # Проверяем, включено ли кэширование в конфиге
        if not self.config.get('cache_enabled', True):
            return None
            
        # НЕ пытаемся загружать данные из будущего
        if target_date > datetime.now().date():
            logger.warning(f"Попытка загрузить данные из будущего: {target_date}")
            return None
            
        cache_file = os.path.join(self.cache_dir, f"rates_{target_date.strftime('%Y%m%d')}.json")
        if os.path.exists(cache_file):
            try:
                # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: файл не должен содержать данные из будущего
                file_date_str = os.path.basename(cache_file).split('_')[1].split('.')[0]
                file_date = datetime.strptime(file_date_str, '%Y%m%d').date()
                if file_date > datetime.now().date():
                    logger.warning(f"Файл кэша содержит данные из будущего: {file_date}")
                    return None
                
                # Проверяем свежесть кэша из конфига
                cache_duration = self.config.get('cache_duration_hours', 12) * 3600
                file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if (datetime.now() - file_time).total_seconds() < cache_duration:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        logger.debug(f"Данные загружены из кэша: {target_date}")
                        return data
            except Exception as e:
                logger.warning(f"Ошибка чтения кэша {cache_file}: {e}")
        return None

    def _save_to_cache(self, data: Dict[str, Any], target_date: date):
        """Сохраняет данные в кэш для указанной даты"""
        # Проверяем, включено ли кэширование в конфиге
        if not self.config.get('cache_enabled', True):
            return
            
        # НЕ сохраняем данные за будущие даты
        if target_date > datetime.now().date():
            logger.warning(f"Попытка сохранить данные за будущую дату: {target_date}")
            return
            
        cache_file = os.path.join(self.cache_dir, f"rates_{target_date.strftime('%Y%m%d')}.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Данные сохранены в кэш: {target_date}")
        except Exception as e:
            logger.warning(f"Ошибка записи в кэш {cache_file}: {e}")

    def _fetch_from_api(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Запрашивает данные с API для указанной даты"""
        # НЕ запрашиваем данные за будущие даты
        if target_date > datetime.now().date():
            logger.warning(f"Попытка запросить данные за будущую дату: {target_date}")
            return None
            
        session = requests.Session()
        
        # Настройки таймаута из конфига
        timeout = self.config.get('timeout', 10)
        session.timeout = (timeout, timeout + 5)
        
        # User-Agent из конфига
        user_agent = self.config.get('user_agent', f'PulseCurrency/{__version__} (https://github.com/UNKNOOOOOWN/VkrAgpu)')
        session.headers.update({'User-Agent': user_agent})
        
        # Базовый URL из конфига
        base_url = self.config.get('base_url', 'https://www.cbr-xml-daily.ru')
        
        # Формируем URL для запроса
        if target_date == date.today():
            url = f"{base_url}/daily_json.js"
        else:
            url = f"{base_url}/archive/{target_date.year}/{target_date.month:02d}/{target_date.day:02d}/daily_json.js"
        
        # Настройки повторных попыток из конфига
        max_retries = self.config.get('max_retries', 3)
        retry_delay = self.config.get('retry_delay', 2)
        
        for attempt in range(max_retries):
            try:
                if not self._is_running:
                    return None
                    
                logger.debug(f"Запрос данных с API за {target_date} (попытка {attempt + 1}/{max_retries})")
                
                response = session.get(url)
                response.raise_for_status()
                
                data = response.json()
                
                if not self._validate_data(data):
                    raise ValueError("Неверная структура данных от API")
                
                logger.debug(f"Данные за {target_date} успешно получены")
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
                
            except Exception as e:
                logger.error(f"Ошибка обработки данных: {e}")
                return None
            
            # Задержка перед повторной попыткой
            if attempt < max_retries - 1 and self._is_running:
                delay = retry_delay * (2 ** attempt)
                time.sleep(delay)
        
        return None

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """Проверка корректности данных от API"""
        required_keys = ['Date', 'PreviousDate', 'Valute']
        if not all(key in data for key in required_keys):
            logger.error("Отсутствуют обязательные ключи в ответе API")
            return False
        
        valute_data = data.get('Valute', {})
        if not valute_data:
            logger.error("Отсутствуют данные о валютах")
            return False
            
        return True


class CBRApiClient:
    """
    Клиент для работы с API Центрального Банка России.
    Обеспечивает получение актуальных курсов валют с обработкой ошибок и кэширование.
    Поддерживает синхронные и асинхронные запросы.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Инициализация клиента API с настройками подключения и кэширования.
        """
        self.config = config or {}
        self.last_update = None
        self.session = requests.Session()
        
        # Настройки из конфига
        timeout = self.config.get('timeout', 10)
        self.session.timeout = (timeout, timeout + 5)
        
        user_agent = self.config.get('user_agent', f'PulseCurrency/{__version__} (https://github.com/UNKNOOOOOWN/VkrAgpu)')
        self.session.headers.update({'User-Agent': user_agent})
        
        # Инициализация кэширования
        self.cache_dir = "cache"
        self._ensure_cache_dir()
        
        # Очистка проблемного кэша при инициализации
        self.cleanup_old_cache()
        
        # Пул потоков для асинхронной работы
        max_threads = self.config.get('max_concurrent_requests', 2)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max_threads)
        
        self.current_worker = None
        
        logger.info(f"Инициализирован API клиент с таймаутом {timeout}с и {max_threads} потоками")

    def _ensure_cache_dir(self):
        """Создает папку для кэша если её нет"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info(f"Создана директория кэша: {self.cache_dir}")
    
    def _get_cache_filename(self, target_date: date) -> str:
        """Генерирует имя файла для кэша на основе дата"""
        return os.path.join(self.cache_dir, f"rates_{target_date.strftime('%Y%m%d')}.json")
    
    def cleanup_old_cache(self):
        """Очистка устаревших файлов кэша"""
        try:
            current_date = datetime.now().date()
            cache_files = [f for f in os.listdir(self.cache_dir) 
                          if f.startswith("rates_") and f.endswith(".json")]
            
            for filename in cache_files:
                try:
                    # Извлекаем дату из имени файла
                    date_str = filename.split('_')[1].split('.')[0]
                    file_date = datetime.strptime(date_str, '%Y%m%d').date()
                    
                    # Удаляем файлы с будущими датами или очень старые
                    if file_date > current_date or (current_date - file_date).days > 30:
                        filepath = os.path.join(self.cache_dir, filename)
                        os.remove(filepath)
                        logger.info(f"Удален проблемный файл кэша: {filename}")
                except Exception as e:
                    logger.warning(f"Ошибка обработки файла {filename}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
    
    def _load_from_cache(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Загружает данные из кэша для указанной даты"""
        # Проверяем, включено ли кэширование в конфиге
        if not self.config.get('cache_enabled', True):
            return None
            
        # НЕ пытаемся загружать данные из будущего
        if target_date > datetime.now().date():
            logger.warning(f"Попытка загрузить данные из будущего: {target_date}")
            return None
            
        cache_file = self._get_cache_filename(target_date)
        if os.path.exists(cache_file):
            try:
                # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: файл не должен содержать данные из будущего
                file_date_str = os.path.basename(cache_file).split('_')[1].split('.')[0]
                file_date = datetime.strptime(file_date_str, '%Y%m%d').date()
                if file_date > datetime.now().date():
                    logger.warning(f"Файл кэша содержит данные из будущего: {file_date}")
                    return None
                
                # Проверяем свежесть кэша из конфига
                cache_duration = self.config.get('cache_duration_hours', 12) * 3600
                file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if (datetime.now() - file_time).total_seconds() < cache_duration:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        logger.info(f"Данные загружены из кэша: {target_date}")
                        return data
            except Exception as e:
                logger.error(f"Ошибка загрузки из кэша {cache_file}: {e}")
        return None
    
    def _save_to_cache(self, data: Dict[str, Any], target_date: date):
        """Сохраняет данные в кэш для указанной даты"""
        # Проверяем, включено ли кэширование в конфиге
        if not self.config.get('cache_enabled', True):
            return
            
        # НЕ сохраняем данные за будущие даты
        if target_date > datetime.now().date():
            logger.warning(f"Попытка сохранить данные за будущую дату: {target_date}")
            return
            
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
                api_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # ВАЖНОЕ ИСПРАВЛЕНИЕ: если API возвращает будущую дату,
                # используем текущую дату вместо даты из API
                if api_date > datetime.now().date():
                    logger.warning(f"API вернул данные с будущей датой {api_date}, используем текущую дату")
                    return datetime.now().date()
                    
                return api_date
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка парсинга даты из API: {e}")
        return datetime.now().date()
    
    def _get_last_available_cached_data(self) -> Optional[Dict[str, Any]]:
        """Пытается найти последние доступные данные в кэше"""
        try:
            # Проверяем последние 7 дней (только прошедшие даты)
            for days_back in range(0, 8):
                check_date = date.today() - timedelta(days=days_back)
                # Пропускаем будущие даты
                if check_date > datetime.now().date():
                    continue
                cached_data = self._load_from_cache(check_date)
                if cached_data:
                    logger.info(f"Найдены кэшированные данные за: {check_date}")
                    return cached_data
        except Exception as e:
            logger.error(f"Ошибка поиска в кэше: {e}")
        return None

    def _build_url_for_date(self, target_date: date) -> str:
        """Строит URL для запроса данных на определенную дату"""
        # НЕ формируем URL для будущих дат
        if target_date > datetime.now().date():
            logger.warning(f"Попытка сформировать URL для будущей дату: {target_date}")
            return ""
            
        base_url = self.config.get('base_url', 'https://www.cbr-xml-daily.ru')
        
        if target_date == date.today():
            return f"{base_url}/daily_json.js"
        else:
            return f"{base_url}/archive/{target_date.year}/{target_date.month:02d}/{target_date.day:02d}/daily_json.js"

    def get_rates_async(self, currency_code: str, dates: List[date]) -> AsyncApiWorker:
        """
        Создает асинхронный воркер для получения данных.
        """
        # Фильтруем даты: удаляем будущие даты
        valid_dates = [d for d in dates if d <= datetime.now().date()]
        if len(valid_dates) != len(dates):
            logger.warning("Удалены будущие даты из запроса")
        
        # Останавливаем предыдущий воркер для этой валюты, если есть
        if hasattr(self, 'current_worker') and self.current_worker:
            self.current_worker.stop()
        
        worker = AsyncApiWorker(currency_code, valid_dates, self.cache_dir, self.config)
        self.current_worker = worker
        return worker

    def get_rates(self, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """
        Получение актуальных курсов валют с API ЦБ РФ с использованием кэширования.
        """
        # Определяем дату для запроса
        if target_date is None:
            target_date = date.today()
        
        # НЕ обрабатываем будущие даты
        if target_date > datetime.now().date():
            logger.warning(f"Попытка получить данные за будущую дату: {target_date}")
            return self._get_last_available_cached_data()
        
        # Сначала проверяем кэш на указанную дату
        cached_data = self._load_from_cache(target_date)
        if cached_data:
            logger.info(f"Используются кэшированные данные за {target_date}")
            self.last_update = datetime.now()
            return cached_data
        
        # Формируем URL для запроса
        url = self._build_url_for_date(target_date)
        if not url:
            return self._get_last_available_cached_data()
        
        # Настройки повторных попыток из конфига
        max_retries = self.config.get('max_retries', 3)
        retry_delay = self.config.get('retry_delay', 2)
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Запрос данных с API ЦБ РФ за {target_date} (попытка {attempt + 1}/{max_retries})")
                logger.info(f"URL: {url}")
                
                response = self.session.get(url)
                response.raise_for_status()
                
                data = response.json()
                
                if not self._validate_data(data):
                    raise ValueError("Неверная структура данных от API")
                
                # ВАЖНОЕ ИСПРАВЛЕНИЕ: проверяем дату из API
                data_date = self._get_cache_date_from_data(data)
                
                # Сохраняем в кэш с корректной датой
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
            if attempt < max_retries - 1:
                delay = retry_delay * (2 ** attempt)
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
        Очищает старые файлов кэша.
        """
        try:
            deleted_count = 0
            current_time = datetime.now()
            
            for filename in os.listdir(self.cache_dir):
                if filename.startswith("rates_") and filename.endswith(".json"):
                    filepath = os.path.join(self.cache_dir, filename)
                    
                    try:
                        # Получаем время создания файла
                        file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                        
                        # Проверяем, нужно ли удалить файл
                        if (current_time - file_time).days > days_to_keep:
                            os.remove(filepath)
                            deleted_count += 1
                            logger.debug(f"Удален старый файл кэша: {filename}")
                    except Exception as e:
                        logger.warning(f"Ошибка обработки файла {filename}: {e}")
                        continue
            
            logger.info(f"Очищено файлов кэша: {deleted_count}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о кэше.
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

    def stop_current_worker(self):
        """Останавливает текущий выполняющийся воркер"""
        if hasattr(self, 'current_worker') and self.current_worker:
            self.current_worker.stop()


# Тестирование функционала модуля при прямом запуске
if __name__ == "__main__":
    # Тест с конфигом по умолчанию
    client = CBRApiClient()
    
    print("=== ТЕКУЩИЕ ДАННЫЕ ===")
    rates = client.get_rates()
    
    if rates:
        print("Данные успешно получены!")
        print(f"Время обновления: {rates['Date']}")
        print(f"USD: {rates['Valute']['USD']['Value']} руб.")
    else:
        print("Не удалось получить текущие данные")
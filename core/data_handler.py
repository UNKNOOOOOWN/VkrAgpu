import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np

# Импортируем наши модули
from core.api_client import CBRApiClient
from core.calculator import Calculator

# Настройка логирования
logger = logging.getLogger(__name__)

class DataHandler:
    """
    Класс для обработки и преобразования данных о курсах валют.
    Оптимизирован для быстрой работы и минимального количества запросов к API.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Инициализация обработчика данных с настройками из конфига.
        """
        self.config = config or {}
        self.data_config = self.config.get('data', {})
        self.api_config = self.config.get('api', {})
        
        # Инициализируем API клиент с конфигом
        self.api_client = CBRApiClient(config=self.api_config)
        self.calculator = Calculator()
        
        self.processed_data: List[Dict] = []  # Список обработанных данных для таблицы
        self.historical_cache: Dict[str, Dict] = {}  # Кэш исторических данных
        self.daily_cache: Dict[str, Dict] = {}  # Кэш дневных данных
        self.last_update: Optional[datetime] = None

        logger.info("Инициализирован DataHandler с конфигурацией")

    def fetch_and_process_data(self, target_date: Optional[date] = None) -> Optional[List[Dict]]:
        """
        Основной метод: получает и обрабатывает данные.
        Оптимизированная версия для быстрого запуска.
        """
        # Используем кэш, если данные актуальны
        cache_duration = self.data_config.get('cache_duration_hours', 12) * 3600
        if (self.last_update and 
            (datetime.now() - self.last_update).total_seconds() < cache_duration and
            self.processed_data):
            logger.info("Используем кэшированные данные (актуальны)")
            return self.processed_data

        logger.info(f"Запрос данных за {target_date or 'текущую дату'}")

        # 1. Получаем СЫРЫЕ данные через API-клиент
        raw_data = self.api_client.get_rates(target_date)
        if not raw_data:
            logger.error("DataHandler: не удалось получить сырые данные.")
            return None

        # 2. Парсим и обрабатываем сырые данные
        self.processed_data = self._parse_and_process(raw_data, target_date)
        self.last_update = datetime.now()
        
        logger.info(f"Данные обработаны. Получено записей: {len(self.processed_data)}")
        return self.processed_data

    def _parse_and_process(self, raw_data: Dict, target_date: Optional[date] = None) -> List[Dict]:
        """
        Быстрый парсинг сырого JSON от API.
        Оптимизирован для минимального времени обработки.
        """
        processed_list = []
        valute_dict = raw_data.get('Valute', {})
        actual_date = target_date or datetime.now().date()

        for char_code, currency_info in valute_dict.items():
            try:
                # Извлекаем только необходимые данные
                nominal = currency_info['Nominal']
                current_value = currency_info['Value']
                previous_value = currency_info['Previous']

                # Быстрый расчет без вызова внешних методов
                current_normalized = current_value / nominal
                previous_normalized = previous_value / nominal
                absolute_change = current_normalized - previous_normalized
                
                # Расчет процентного изменения с проверкой деления на ноль
                if previous_normalized != 0:
                    percent_change = (absolute_change / previous_normalized) * 100
                else:
                    percent_change = 0.0

                currency_entry = {
                    'char_code': char_code,
                    'name': currency_info['Name'],
                    'nominal': nominal,
                    'value': current_value,
                    'normalized_value': round(current_normalized, 4),
                    'previous': previous_value,
                    'normalized_previous': round(previous_normalized, 4),
                    'abs_change': round(absolute_change, 4),
                    'percent_change': round(percent_change, 2),
                    'date': actual_date.isoformat(),
                }
                processed_list.append(currency_entry)
                
            except (KeyError, ZeroDivisionError) as e:
                logger.debug(f"Пропущена валюта {char_code}: {e}")
                continue

        # Быстрая сортировка по коду валюты
        processed_list.sort(key=lambda x: x['char_code'])
        return processed_list

    def get_processed_data(self) -> List[Dict]:
        """Возвращает последние обработанные данные."""
        return self.processed_data

    def get_currency_by_code(self, char_code: str) -> Optional[Dict]:
        """Быстрый поиск данных по коду валюты."""
        if not self.processed_data:
            return None
            
        # Используем генератор для быстрого поиска
        return next((curr for curr in self.processed_data 
                    if curr['char_code'].upper() == char_code.upper()), None)

    def _get_cached_daily_data(self, target_date: date) -> Optional[Dict]:
        """
        Получает данные за день из кэша или API.
        Использует двухуровневое кэширование.
        """
        # Проверяем, включено ли кэширование в конфиге
        if not self.data_config.get('cache_enabled', True):
            return self.api_client.get_rates(target_date)
            
        cache_key = target_date.isoformat()
        daily_cache_duration = self.data_config.get('daily_cache_duration_hours', 1) * 3600
        
        # Проверяем кэш в памяти
        if cache_key in self.daily_cache:
            cached_data = self.daily_cache[cache_key]
            cache_time = datetime.fromisoformat(cached_data.get('cache_timestamp', ''))
            if (datetime.now() - cache_time).total_seconds() < daily_cache_duration:
                return cached_data
        
        # Если нет в кэше, запрашиваем из API
        daily_data = self.api_client.get_rates(target_date)
        if daily_data:
            # Сохраняем в кэш
            daily_data['cache_timestamp'] = datetime.now().isoformat()
            self.daily_cache[cache_key] = daily_data
            return daily_data
        
        return None

    def get_historical_data_for_chart(self, char_code: str, days: int = None) -> Optional[Dict]:
        """
        Готовит данные для построения графика.
        Оптимизированная версия с ограниченным периодом.
        """
        try:
            # Используем значение по умолчанию из конфига если не указано
            if days is None:
                days = self.data_config.get('default_chart_days', 3)
            
            # Ограничиваем период из конфига
            max_chart_days = self.data_config.get('max_chart_days', 7)
            days = min(days, max_chart_days)
            
            # Проверяем кэш
            cache_key = f"{char_code}_{days}"
            cache_duration = self.data_config.get('cache_duration_hours', 12) * 3600
            
            if cache_key in self.historical_cache:
                cached_data = self.historical_cache[cache_key]
                # Проверяем свежесть кэша
                cache_time = datetime.fromisoformat(cached_data.get('cache_timestamp', ''))
                if (datetime.now() - cache_time).total_seconds() < cache_duration:
                    logger.debug(f"Используем кэшированные данные для {char_code}")
                    return cached_data
            
            currency_data = self.get_currency_by_code(char_code)
            if not currency_data:
                logger.warning(f"Валюта {char_code} не найдена")
                return None

            # Получаем список дат для запроса (только рабочие дни)
            end_date = datetime.now().date()
            date_list = self._get_business_dates(end_date, days)
            
            # Получаем данные за все даты
            all_data = []
            for target_date in date_list:
                daily_data = self._get_cached_daily_data(target_date)
                if daily_data and char_code in daily_data.get('Valute', {}):
                    valute_info = daily_data['Valute'][char_code]
                    all_data.append({
                        'date': target_date,
                        'value': valute_info['Value'],
                        'normalized_value': valute_info['Value'] / valute_info['Nominal']
                    })

            if not all_data:
                logger.warning(f"Не найдено данных для {char_code} за {days} дней")
                return None

            # Сортируем данные по дате
            all_data.sort(key=lambda x: x['date'])
            
            dates = [d['date'] for d in all_data]
            values = [d['value'] for d in all_data]
            normalized_values = [d['normalized_value'] for d in all_data]

            # Рассчитываем статистику
            volatility = self.calculator.calculate_volatility(normalized_values)
            statistics = self.calculator.calculate_statistics(normalized_values)

            chart_data = {
                'currency_code': char_code,
                'currency_name': currency_data['name'],
                'dates': [d.isoformat() for d in dates],
                'values': values,
                'normalized_values': normalized_values,
                'volatility': volatility,
                'statistics': statistics,
                'period_days': days,
                'data_points': len(dates),
                'cache_timestamp': datetime.now().isoformat()
            }

            logger.info(f"Подготовлены данные для графика {char_code}: {len(dates)} точек")
            
            # Сохраняем в кэш если включено
            if self.data_config.get('cache_enabled', True):
                self.historical_cache[cache_key] = chart_data
                
            return chart_data

        except Exception as e:
            logger.error(f"Ошибка при получении исторических данных для {char_code}: {e}")
            return None

    def _get_business_dates(self, end_date: date, days: int) -> List[date]:
        """
        Возвращает список рабочих дней (пн-пт) за указанный период.
        """
        date_list = []
        current_date = end_date
        
        # Собираем дни в обратном порядке (от текущего к прошлому)
        while len(date_list) < days and current_date > end_date - timedelta(days=days * 2):
            if current_date.weekday() < 5:  # 0-4 = пн-пт
                date_list.append(current_date)
            current_date -= timedelta(days=1)
            
            # Защита от бесконечного цикла
            if (end_date - current_date).days > days * 3:
                break
        
        return date_list

    def get_historical_data_async(self, char_code: str, days: int = None) -> Any:
        """
        Создает асинхронный воркер для получения исторических данных.
        """
        # Используем значение по умолчанию из конфига если не указано
        if days is None:
            days = self.data_config.get('default_chart_days', 3)
        
        # Ограничиваем период из конфига
        max_chart_days = self.data_config.get('max_chart_days', 7)
        days = min(days, max_chart_days)
        
        # Получаем список дат для запроса
        end_date = datetime.now().date()
        date_list = self._get_business_dates(end_date, days)
        
        # Создаем асинхронный воркер
        return self.api_client.get_rates_async(char_code, date_list)

    def process_async_data(self, data: Dict[str, Any], currency_code: str, days: int = None) -> Optional[Dict]:
        """
        Обрабатывает данные, полученные асинхронно.
        """
        try:
            currency_data = self.get_currency_by_code(currency_code)
            if not currency_data:
                return None

            # Преобразуем данные в нужный формат
            all_data = []
            for date_str, daily_data in data.items():
                if daily_data and 'Valute' in daily_data and currency_code in daily_data['Valute']:
                    valute_info = daily_data['Valute'][currency_code]
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    all_data.append({
                        'date': target_date,
                        'value': valute_info['Value'],
                        'normalized_value': valute_info['Value'] / valute_info['Nominal']
                    })

            if not all_data:
                return None

            # Сортируем данные по дате
            all_data.sort(key=lambda x: x['date'])
            
            dates = [d['date'] for d in all_data]
            values = [d['value'] for d in all_data]
            normalized_values = [d['normalized_value'] for d in all_data]

            # Рассчитываем статистику
            volatility = self.calculator.calculate_volatility(normalized_values)
            statistics = self.calculator.calculate_statistics(normalized_values)

            chart_data = {
                'currency_code': currency_code,
                'currency_name': currency_data['name'],
                'dates': [d.isoformat() for d in dates],
                'values': values,
                'normalized_values': normalized_values,
                'volatility': volatility,
                'statistics': statistics,
                'period_days': days,
                'data_points': len(dates),
                'cache_timestamp': datetime.now().isoformat()
            }

            # Сохраняем в кэш если включено
            if self.data_config.get('cache_enabled', True):
                cache_key = f"{currency_code}_{days}"
                self.historical_cache[cache_key] = chart_data
            
            return chart_data

        except Exception as e:
            logger.error(f"Ошибка обработки асинхронных данных для {currency_code}: {e}")
            return None

    def calculate_currency_conversion(self, amount: float, from_currency: str, 
                                    to_currency: str) -> Optional[float]:
        """
        Конвертирует сумму из одной валюты в другую.
        """
        try:
            from_data = self.get_currency_by_code(from_currency)
            to_data = self.get_currency_by_code(to_currency)
            
            if not from_data or not to_data:
                return None

            # Быстрый расчет без вызова внешнего метода
            from_normalized = from_data['value'] / from_data['nominal']
            to_normalized = to_data['value'] / to_data['nominal']
            
            if to_normalized == 0:
                return None
                
            converted_amount = amount * from_normalized / to_normalized
            return round(converted_amount, 2)
            
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return None

    def get_top_movers(self, sort_by: str = 'percent_change', limit: int = 5) -> List[Dict]:
        """
        Возвращает топ валют по изменению курса.
        """
        if not self.processed_data:
            return []
        
        # Быстрая сортировка
        sorted_data = sorted(
            self.processed_data, 
            key=lambda x: abs(x.get(sort_by, 0)), 
            reverse=True
        )
        
        return sorted_data[:limit]

    def clear_cache(self):
        """Очищает кэш данных."""
        self.historical_cache.clear()
        self.daily_cache.clear()
        logger.info("Кэш данных очищен")

    def get_available_currencies(self) -> List[Dict]:
        """Возвращает список всех доступных валют."""
        return [{
            'char_code': curr['char_code'],
            'name': curr['name'],
            'nominal': curr['nominal']
        } for curr in self.processed_data]

    def get_cached_historical_data(self, char_code: str, days: int = None) -> Optional[Dict]:
        """Возвращает исторические данные из кэша."""
        # Используем значение по умолчанию из конфига если не указано
        if days is None:
            days = self.data_config.get('default_chart_days', 3)
            
        cache_key = f"{char_code}_{days}"
        return self.historical_cache.get(cache_key)

    def is_data_fresh(self, max_age_minutes: int = None) -> bool:
        """Проверяет, актуальны ли данные."""
        if not self.last_update or not self.processed_data:
            return False
            
        # Используем настройку из конфига если не указано
        if max_age_minutes is None:
            cache_duration = self.data_config.get('cache_duration_hours', 12) * 3600
            max_age_seconds = cache_duration
        else:
            max_age_seconds = max_age_minutes * 60
            
        return (datetime.now() - self.last_update).total_seconds() < max_age_seconds

    def get_initial_load_days(self) -> int:
        """Возвращает количество дней для начальной загрузки из конфига."""
        return self.data_config.get('initial_load_days', 3)
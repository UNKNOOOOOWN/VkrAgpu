import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

# Импортируем наши модули
from .api_client import CBRApiClient, AsyncApiWorker
from .calculator import Calculator

# Настройка логирования
logger = logging.getLogger(__name__)

class DataHandler:
    """
    Класс для обработки и преобразования данных о курсах валют.
    Получает сырые данные от CBRApiClient, парсит их и готовит для отображения в UI.
    """

    def __init__(self):
        self.api_client = CBRApiClient()
        self.calculator = Calculator()
        self.processed_data: List[Dict] = []  # Список обработанных данных для таблицы
        self.historical_cache: Dict[str, Dict] = {}  # Кэш исторических данных
        self.current_workers: Dict[str, AsyncApiWorker] = {}  # Текущие активные воркеры

    def fetch_and_process_data(self, target_date: Optional[date] = None) -> Optional[List[Dict]]:
        """
        Основной метод: получает и обрабатывает данные.
        
        Args:
            target_date: Дата, за которую нужны данные. Если None - берется текущая.
            
        Returns:
            Список словарей с обработанными данными по валютам или None при ошибке.
        """
        logger.info(f"Запрос данных за {target_date or 'текущую дату'}")

        # 1. Получаем СЫРЫЕ данные через API-клиент
        raw_data = self.api_client.get_rates(target_date)
        if not raw_data:
            logger.error("DataHandler: не удалось получить сырые данные.")
            return None

        # 2. Парсим и обрабатываем сырые данные
        self.processed_data = self._parse_and_process(raw_data, target_date)
        logger.info(f"Данные обработаны. Получено записей: {len(self.processed_data)}")
        
        return self.processed_data

    def _parse_and_process(self, raw_data: Dict, target_date: Optional[date] = None) -> List[Dict]:
        """
        Парсит сырой JSON от API и преобразует его в удобный для UI формат.
        """
        processed_list = []
        valute_dict = raw_data.get('Valute', {})
        timestamp = raw_data.get('Timestamp')
        actual_date = target_date or datetime.now().date()

        for char_code, currency_info in valute_dict.items():
            try:
                # Извлекаем и готовим данные
                nominal = currency_info['Nominal']
                current_value = currency_info['Value']
                previous_value = currency_info['Previous']

                # Используем Calculator для расчетов
                abs_change, percent_change = self.calculator.calculate_changes(
                    current_value, previous_value, nominal
                )

                # Нормализованное значение (за 1 единицу валюты)
                normalized_value = current_value / nominal
                normalized_previous = previous_value / nominal

                currency_entry = {
                    'char_code': char_code,
                    'name': currency_info['Name'],
                    'nominal': nominal,
                    'value': current_value,
                    'normalized_value': round(normalized_value, 4),
                    'previous': previous_value,
                    'normalized_previous': round(normalized_previous, 4),
                    'abs_change': abs_change,
                    'percent_change': percent_change,
                    'date': actual_date.isoformat(),
                    'timestamp': timestamp,
                    'icon': f":/icons/{char_code.lower()}.png"
                }
                processed_list.append(currency_entry)
                
            except KeyError as e:
                logger.warning(f"Отсутствует ключ у валюты {char_code}: {e}")
                continue
            except ZeroDivisionError:
                logger.warning(f"Деление на ноль для валюты {char_code}")
                continue

        # Сортируем список по буквенному коду валюты для удобства
        processed_list.sort(key=lambda x: x['char_code'])
        return processed_list

    def get_processed_data(self) -> List[Dict]:
        """Возвращает последние обработанные данные."""
        return self.processed_data

    def get_currency_by_code(self, char_code: str) -> Optional[Dict]:
        """Возвращает данные по конкретной валюте."""
        for currency in self.processed_data:
            if currency['char_code'].upper() == char_code.upper():
                return currency
        return None

    def get_historical_data_for_chart(self, char_code: str, days: int = 7) -> Optional[Dict]:
        """
        Готовит данные для построения графика.
        Использует кэширование и асинхронные запросы.
        """
        try:
            # ОГРАНИЧИВАЕМ ПЕРИОД ДЛЯ СКОРОСТИ
            days = min(days, 7)
            
            # Проверяем кэш
            cache_key = f"{char_code}_{days}"
            if cache_key in self.historical_cache:
                cached_data = self.historical_cache[cache_key]
                # Проверяем свежесть кэша (1 час)
                cache_time = datetime.fromisoformat(cached_data['cache_timestamp'])
                if (datetime.now() - cache_time).total_seconds() < 3600:
                    logger.debug(f"Используем кэшированные данные для {char_code}")
                    return cached_data
            
            currency_data = self.get_currency_by_code(char_code)
            if not currency_data:
                logger.warning(f"Валюта {char_code} не найдена")
                return None

            # Получаем список дат для запроса
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Собираем только рабочие дни (понедельник - пятница)
            date_list = []
            current_date = start_date
            
            while current_date <= end_date:
                if current_date.weekday() < 5:  # 0-4 = пн-пт
                    date_list.append(current_date)
                current_date += timedelta(days=1)

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
            returns = self.calculator.calculate_returns(normalized_values)

            chart_data = {
                'currency_code': char_code,
                'currency_name': currency_data['name'],
                'dates': [d.isoformat() for d in dates],
                'values': values,
                'normalized_values': normalized_values,
                'volatility': volatility,
                'statistics': statistics,
                'returns': returns,
                'period_days': days,
                'data_points': len(dates),
                'cache_timestamp': datetime.now().isoformat()
            }

            logger.info(f"Подготовлены данные для графика {char_code}: {len(dates)} точек")
            
            # Сохраняем в кэш
            self.historical_cache[cache_key] = chart_data
            return chart_data

        except Exception as e:
            logger.error(f"Ошибка при получении исторических данных для {char_code}: {e}")
            return None

    def _get_cached_daily_data(self, target_date: date) -> Optional[Dict]:
        """
        Получает данные за день из кэша или API.
        """
        cache_key = target_date.isoformat()
        
        # Проверяем кэш в памяти
        if hasattr(self, '_daily_cache'):
            if cache_key in self._daily_cache:
                cached_data = self._daily_cache[cache_key]
                # Проверяем свежесть кэша (12 часов)
                cache_time = datetime.fromisoformat(cached_data['cache_timestamp'])
                if (datetime.now() - cache_time).total_seconds() < 43200:
                    return cached_data
        
        # Если нет в кэше, запрашиваем из API
        daily_data = self.api_client.get_rates(target_date)
        if daily_data:
            # Сохраняем в кэш
            daily_data['cache_timestamp'] = datetime.now().isoformat()
            if not hasattr(self, '_daily_cache'):
                self._daily_cache = {}
            self._daily_cache[cache_key] = daily_data
            return daily_data
        
        return None

    def get_historical_data_async(self, char_code: str, days: int = 7) -> AsyncApiWorker:
        """
        Создает асинхронный воркер для получения исторических данных.
        """
        # Останавливаем предыдущий воркер для этой валюты, если есть
        if char_code in self.current_workers:
            self.current_workers[char_code].stop()
        
        # Получаем список дат для запроса
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=min(days, 7))
        
        # Собираем только рабочие дни
        date_list = []
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.weekday() < 5:  # 0-4 = пн-пт
                date_list.append(current_date)
            current_date += timedelta(days=1)
        
        # Создаем асинхронный воркер
        worker = self.api_client.get_rates_async(char_code, date_list)
        self.current_workers[char_code] = worker
        return worker

    def process_async_data(self, data: Dict[str, Any], currency_code: str, days: int = 7) -> Optional[Dict]:
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
            returns = self.calculator.calculate_returns(normalized_values)

            chart_data = {
                'currency_code': currency_code,
                'currency_name': currency_data['name'],
                'dates': [d.isoformat() for d in dates],
                'values': values,
                'normalized_values': normalized_values,
                'volatility': volatility,
                'statistics': statistics,
                'returns': returns,
                'period_days': days,
                'data_points': len(dates),
                'cache_timestamp': datetime.now().isoformat()
            }

            # Сохраняем в кэш
            cache_key = f"{currency_code}_{days}"
            self.historical_cache[cache_key] = chart_data
            
            return chart_data

        except Exception as e:
            logger.error(f"Ошибка обработки асинхронных данных для {currency_code}: {e}")
            return None

    def get_multiple_currencies_history(self, char_codes: List[str], days: int = 7) -> Dict:
        """
        Возвращает исторические данные для нескольких валют одновременно.
        """
        result = {}
        for code in char_codes:
            history = self.get_historical_data_for_chart(code, days)
            if history:
                result[code] = history
        return result

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

            converted_amount = self.calculator.convert_currency(
                amount=amount,
                from_rate=from_data['value'],
                to_rate=to_data['value'],
                from_nominal=from_data['nominal'],
                to_nominal=to_data['nominal']
            )
            
            return converted_amount
            
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return None

    def get_top_movers(self, sort_by: str = 'percent_change', limit: int = 5) -> List[Dict]:
        """
        Возвращает топ валют по изменению курса.
        """
        if not self.processed_data:
            return []
        
        sorted_data = sorted(
            self.processed_data, 
            key=lambda x: abs(x.get(sort_by, 0)), 
            reverse=True
        )
        
        return sorted_data[:limit]

    def clear_cache(self):
        """Очищает кэш исторических данных."""
        self.historical_cache.clear()
        if hasattr(self, '_daily_cache'):
            self._daily_cache.clear()
        logger.info("Кэш исторических данных очищен")
        
        # Останавливаем все активные воркеры
        for worker in self.current_workers.values():
            worker.stop()
        self.current_workers.clear()

    def get_available_currencies(self) -> List[Dict]:
        """Возвращает список всех доступных валют с основными данными."""
        return [{
            'char_code': curr['char_code'],
            'name': curr['name'],
            'nominal': curr['nominal']
        } for curr in self.processed_data]

    def get_cached_historical_data(self, char_code: str, days: int = 7) -> Optional[Dict]:
        """Возвращает исторические данные из кэша."""
        cache_key = f"{char_code}_{days}"
        return self.historical_cache.get(cache_key)

    def stop_worker(self, char_code: str):
        """Останавливает воркер для конкретной валюты."""
        if char_code in self.current_workers:
            self.current_workers[char_code].stop()
            del self.current_workers[char_code]
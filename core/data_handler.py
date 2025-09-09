import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

# Импортируем наши модули
from .api_client import CBRApiClient
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
        self.historical_cache: Dict[str, List[Dict]] = {}  # Кэш исторических данных

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

    def get_historical_data_for_chart(self, char_code: str, days: int = 30) -> Optional[Dict]:
        """
        Готовит данные для построения графика.
        Возвращает словарь с датами и значениями валюты.
        Формат: {'dates': [], 'values': [], 'currency_name': str}
        """
        try:
            currency_data = self.get_currency_by_code(char_code)
            if not currency_data:
                logger.warning(f"Валюта {char_code} не найдена")
                return None

            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            dates = []
            values = []
            normalized_values = []

            # Собираем исторические данные
            current_date = start_date
            while current_date <= end_date:
                try:
                    # Получаем данные за каждую дату
                    historical_data = self.api_client.get_rates(current_date)
                    if historical_data and 'Valute' in historical_data:
                        valute_info = historical_data['Valute'].get(char_code)
                        if valute_info:
                            nominal = valute_info['Nominal']
                            value = valute_info['Value']
                            normalized_value = value / nominal
                            
                            dates.append(current_date)
                            values.append(value)
                            normalized_values.append(normalized_value)
                            
                except Exception as e:
                    logger.debug(f"Нет данных за {current_date}: {e}")
                
                current_date += timedelta(days=1)

            if not dates:
                return None

            # Рассчитываем дополнительную статистику
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
                'period_days': days
            }

            # Сохраняем в кэш
            self.historical_cache[char_code] = chart_data
            return chart_data

        except Exception as e:
            logger.error(f"Ошибка при получении исторических данных для {char_code}: {e}")
            return None

    def get_multiple_currencies_history(self, char_codes: List[str], days: int = 30) -> Dict:
        """
        Возвращает исторические данные для нескольких валют одновременно.
        Полезно для сравнения на графике.
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
        
        Args:
            sort_by: 'percent_change' или 'abs_change'
            limit: количество возвращаемых записей
        """
        if not self.processed_data:
            return []
        
        # Сортируем по абсолютному значению изменения
        sorted_data = sorted(
            self.processed_data, 
            key=lambda x: abs(x.get(sort_by, 0)), 
            reverse=True
        )
        
        return sorted_data[:limit]

    def clear_cache(self):
        """Очищает кэш исторических данных."""
        self.historical_cache.clear()
        logger.info("Кэш исторических данных очищен")

    def get_available_currencies(self) -> List[Dict]:
        """Возвращает список всех доступных валют с основными данными."""
        return [{
            'char_code': curr['char_code'],
            'name': curr['name'],
            'nominal': curr['nominal']
        } for curr in self.processed_data]
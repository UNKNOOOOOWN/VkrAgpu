import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

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
        self.api_client = CBRApiClient()  # Используем готовый клиент!
        self.calculator = Calculator()    # Будем использовать для расчетов
        self.processed_data: List[Dict] = [] # Список обработанных данных для таблицы

    def fetch_and_process_data(self, target_date: Optional[date] = None) -> Optional[List[Dict]]:
        """
        Основной метод: получает и обрабатывает данные.
        
        Args:
            target_date: Дата, за которую нужны данные. Если None - берется текущая.
            
        Returns:
            Список словарей с обработанными данными по валютам или None при ошибке.
        """
        logger.info(f"Запрос данных за {target_date or 'текущую дату'}")

        # 1. Получаем СЫРЫЕ данные через API-клиент (он сам решит, откуда их взять)
        raw_data = self.api_client.get_rates()  # Ваш метод get_rates может быть адаптирован для даты
        if not raw_data:
            logger.error("DataHandler: не удалось получить сырые данные.")
            return None

        # 2. Парсим и обрабатываем сырые данные
        self.processed_data = self._parse_and_process(raw_data)
        logger.info(f"Данные обработаны. Получено записей: {len(self.processed_data)}")
        
        return self.processed_data

    def _parse_and_process(self, raw_data: Dict) -> List[Dict]:
        """
        Парсит сырой JSON от API и преобразует его в удобный для UI формат.
        """
        processed_list = []
        valute_dict = raw_data.get('Valute', {})

        for char_code, currency_info in valute_dict.items():
            try:
                # Извлекаем и готовим данные
                nominal = currency_info['Nominal']
                current_value = currency_info['Value']
                previous_value = currency_info['Previous']

                # Используем Calculator для бизнес-логики!
                abs_change, percent_change = self.calculator.calculate_change(previous_value, current_value)
                # volatility = self.calculator.calculate_volatility(...) # Можно добавить later

                currency_entry = {
                    'char_code': char_code,
                    'name': currency_info['Name'],
                    'nominal': nominal,
                    'value': current_value,
                    'previous': previous_value,
                    'abs_change': abs_change,
                    'percent_change': percent_change,
                    'icon': f":/icons/{char_code.lower()}.png"  # Пример для иконок
                }
                processed_list.append(currency_entry)
                
            except KeyError as e:
                logger.warning(f"Отсутствует ключ у валюты {char_code}: {e}")
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
            if currency['char_code'] == char_code:
                return currency
        return None

    # Метод для будущего: получение исторических данных для графика
    def get_historical_data_for_chart(self, char_code: str, days: int = 30) -> Optional[Dict]:
        """
        Готовит данные для построения графика.
        Формат: {'dates': [], 'values': []}
        """
        # Здесь будет логика, которая использует self.api_client
        # для загрузки кэшированных данных за несколько дней,
        # их парсинга и подготовки для matplotlib.
        # Это ваша следующая задача после настройки основного потока.
        pass
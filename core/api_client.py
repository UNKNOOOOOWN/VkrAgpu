"""
Модуль для работы с API Центрального Банка России.
Предоставляет функционал для получения актуальных курсов валют.
"""

# Стандартные библиотеки Python
import sys # Доступ к системным параметрам и функциям
import os # Взаимодействие с ОС и работой с путями
import requests  # Выполнение HTTP-запросов к внешним API
from datetime import datetime  # Работа с датой и временем
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Добавляем корневую директорию проекта в путь Python
from version import __version__ # Импорт версии ПО
import logging  # Логирование событий и ошибок приложения
import time  # Работа с временными задержками

# Настройка системы логирования для отслеживания работы приложения
# Уровень INFO обеспечивает запись информационных сообщений и ошибок
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Создание объекта логгера с именем текущего модуля
# Позволяет идентифицировать источник сообщений в логах
logger = logging.getLogger(__name__)


class CBRApiClient:
    """
    Клиент для работы с API Центрального Банка России.
    Обеспечивает получение актуальных курсов валют с обработкой ошибок.
    """
    
    # Базовый URL официального API ЦБ РФ для получения курсов валют
    BASE_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
    
    # Количество попыток повторного запроса при сбоях
    MAX_RETRIES = 3
    
    # Задержка между повторными попытками в секундах
    RETRY_DELAY = 2

    def __init__(self):
        """
        Инициализация клиента API с настройками подключения.
        Создает HTTP-сессию с параметрами таймаута для надежности.
        """
        self.last_update = None  # Время последнего успешного обновления данных
        self.session = requests.Session()  # Постоянное HTTP-соединение для повторных запросов
        
        # Настройка таймаутов для предотвращения зависания приложения:
        # - 5 секунд на установление соединения
        # - 10 секунд на ожидание ответа после соединения
        self.session.timeout = (5, 10)
        
        # Установка стандартных заголовков для HTTP-запросов
        self.session.headers.update({
            'User-Agent': f'PulseCurrency/{__version__} (https://github.com/UNKNOOOOOWN/VkrAgpu)'
        })

        # Временная проверка - выводим установленный User-Agent
        print(f"Установлен User-Agent: {self.session.headers['User-Agent']}")
        logger.info(f"Установлен User-Agent: {self.session.headers['User-Agent']}")

    def get_rates(self):
        """
        Получение актуальных курсов валют с API ЦБ РФ.
        
        Returns:
            dict | None: Данные о курсах валют в формате JSON 
                        или None в случае ошибки после всех попыток
        """
        # Реализация механизма повторных попыток при временных сбоях
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Запрос данных с API ЦБ РФ (попытка {attempt + 1}/{self.MAX_RETRIES})")
                
                # Выполнение HTTP GET-запроса к API ЦБ РФ
                response = self.session.get(self.BASE_URL)
                
                # Проверка успешности HTTP-запроса (статус 200-299)
                response.raise_for_status()
                
                # Преобразование ответа из формата JSON в словарь Python
                data = response.json()
                
                # Валидация полученных данных
                if not self._validate_data(data):
                    raise ValueError("Неверная структура данных от API")
                
                # Обновление времени последнего успешного запроса
                self.last_update = datetime.now()
                logger.info(f"Данные успешно получены, время: {self.last_update}")
                
                return data

            except requests.exceptions.RequestException as e:
                # Обработка ошибок сети и HTTP
                logger.warning(f"Ошибка сети при попытке {attempt + 1}: {e}")
                
                # Последняя попытка завершилась ошибкой
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Все попытки подключения к API завершились ошибкой")
                    return None
                
                # Пауза перед повторной попыткой с экспоненциальной задержкой
                time.sleep(self.RETRY_DELAY * (2 ** attempt))
                
            except ValueError as e:
                # Обработка ошибок парсинга JSON и валидации данных
                logger.error(f"Ошибка обработки данных: {e}")
                return None
                
            except Exception as e:
                # Обработка любых других непредвиденных ошибок
                logger.error(f"Непредвиденная ошибка: {e}")
                return None

    def _validate_data(self, data):
        """
        Проверка корректности и полноты полученных данных от API.
        
        Args:
            data (dict): Данные, полученные от API ЦБ РФ
            
        Returns:
            bool: True если данные валидны, False в противном случае
        """
        # Проверка наличия обязательных ключей в ответе API
        required_keys = ['Date', 'PreviousDate', 'Valute']
        if not all(key in data for key in required_keys):
            logger.error("Отсутствуют обязательные ключи в ответе API")
            return False
        
        # Проверка наличия данных по требуемым валютам
        required_currencies = ['USD', 'EUR', 'GBP', 'CNY']
        valute_data = data.get('Valute', {})
        
        for currency in required_currencies:
            if currency not in valute_data:
                logger.error(f"Отсутствуют данные по валюте: {currency}")
                return False
                
            # Проверка наличия обязательных полей для каждой валюты
            currency_data = valute_data[currency]
            required_currency_fields = ['ID', 'NumCode', 'CharCode', 'Nominal', 'Name', 'Value', 'Previous']
            if not all(field in currency_data for field in required_currency_fields):
                logger.error(f"Неполные данные по валюте: {currency}")
                return False
        
        return True


# Тестирование функционала модуля при прямом запуске
if __name__ == "__main__":
    # Создание экземпляра клиента API
    client = CBRApiClient()
    
    # Получение актуальных курсов валют
    rates = client.get_rates()
    
    # Проверка и отображение результатов
    if rates:
        print("Данные успешно получены!")
        print(f"Время обновления: {rates['Date']}")
        print(f"USD: {rates['Valute']['USD']['Value']} руб.")
        print(f"EUR: {rates['Valute']['EUR']['Value']} руб.")
        print(f"GBP: {rates['Valute']['GBP']['Value']} руб.")
        print(f"CNY: {rates['Valute']['CNY']['Value']} руб.")
    else:
        print("Не удалось получить данные от API ЦБ РФ")
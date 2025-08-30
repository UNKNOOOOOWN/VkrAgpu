# Импорт необходимых библиотек
import requests # Для выполнения HTTP-запросов к API
from datetime import datetime # Для работы с датой и временем
import logging # Для логирования событий и ошибок

# Настройка логирования для отслеживания ошибок
# basicConfig настраивает базовую конфигурацию логирования
# level=logging.INFO устанавливает уровень логирования - будут выводиться информационные сообщения и ошибки
logging.basicConfig(level=logging.INFO)

# Создание объекта логгера с именем текущего модуля (__name__)
# Это позволяет идентифицировать источник log-сообщений
logger = logging.getLogger(__name__)


# Определение класса CBRApiClient - основного компонента модуля
class CBRApiClient:
    # Клиент для работы с API ЦБ РA

    # Константа класса - базовый URL API ЦБ РФ, с которого будем получать данные о курсах валют
    BASE_URL = "https://www.cbr-xml-daily.ru/daily_json.js"


    # Инициализация нового объекта класса методом __init__ для настройки первоначальных параметров
    def __init__(self):
        self.last_update = None # Атрибут last_update для хранения времени последнего обновления
        self.session = requests.Session() # Использование сессии позволяет сохранять соединение открытым и повторно использовать его при необходимости
        # Таймауты для запросов:
        # 5 секунд на установление соединения
        # 10 секунд на получение ответа после установления соединения
        # Это предотвращает "зависание" программы при проблемах с сетью
        self.session.timeout = (5, 10)
    
    # Основной метод класса для получения курсов валют
    def get_rates(self):
        # Запрос на получение текущих курсов валют с API ЦБ РФ
        # Данные о курсах валют в формате JSON или None в случае ошибки
        
        try:
            logger.info("Запрос данных с API ЦБ РФ") # Логирование начало запроса
            # Выполнение GET-запрос к API ЦБ РФ
            # session.get() возвращает объект Response
            response = self.session.get(self.BASE_URL)
            # Проверка статуса ответа - если статус не 200 (OK), вызовет исключение
            response.raise_for_status()
            
            # Парсинг JSON-ответ в словарь Python
            data = response.json()
            self.last_update = datetime.now() # Запись времени последнего успешного обновления
            logger.info(f"Данные успешно получены, время: {self.last_update}") # Логирование успешного получения данных
            
            return data

        # Обработка исключений при работе с Интернетом и сервисом API    
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API ЦБ: {e}") # Логирование ошибки запроса
            return None # Возвращение None, что свидетельствует о не получении даных
        # Обработка исключений парсинга JSON
        except ValueError as e:
            logger.error(f"Ошибка парсинга JSON: {e}") # Логирование ошибки парсинга JSON
            return None # Возвращение None, что свидетельствует о некорректном парснге

# Тестовое получение курсов фиатных валют с API ЦБ РФ
if __name__ == "__main__":
    client = CBRApiClient() # Cоздание экземпляра (объекта) класса CBRApiClient
    rates = client.get_rates() # Вызов метода get_rates() для получения данных о курсах фиатных валют
    
    # Проверка, были ли получены данные
    if rates:
        print("Данные успешно получены!")
        print(f"USD: {rates['Valute']['USD']['Value']}")
        print(f"EUR: {rates['Valute']['EUR']['Value']}")
        print(f"GBP: {rates['Valute']['GBP']['Value']}")
        print(f"CNY: {rates['Valute']['CNY']['Value']}")
    else:
        print("Не удалось получить данные")        
import json
from datetime import datetime, timedelta
from pathlib import Path

class DataHandler:
    """
    Класс для обработки и хранения данных о курсах валют.
    Обеспечивает работу с текущими и историческими данными.
    """
    
    def __init__(self):
        # Инициализация хранилищ данных
        self.current_rates = {}  # Текущие курсы валют
        self.historical_data = {}  # Исторические данные
        self.currencies = ['USD', 'EUR', 'GBP', 'CNY']  # Отслеживаемые валюты
        
        # Создание директории для данных, если не существует
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
    
    def update_data(self, new_data):
        """
        Обновление данных из API ЦБ РФ.
        
        Args:
            new_data (dict): Данные, полученные от API ЦБ РФ
            
        Returns:
            bool: Результат операции обновления
        """
        if not new_data or 'Valute' not in new_data:
            return False
        
        try:
            # Обновление текущих курсов
            for currency in self.currencies:
                if currency in new_data['Valute']:
                    self.current_rates[currency] = new_data['Valute'][currency]
                    
                    # Добавление исторических данных
                    if currency not in self.historical_data:
                        self.historical_data[currency] = []
                    
                    # Сохранение исторической точки данных
                    self.historical_data[currency].append({
                        'date': datetime.now().isoformat(),
                        'value': new_data['Valute'][currency]['Value'],
                        'change': new_data['Valute'][currency]['Value'] - new_data['Valute'][currency]['Previous']
                    })
                    
                    # Ограничение истории последними 14 днями
                    if len(self.historical_data[currency]) > 14:
                        self.historical_data[currency].pop(0)
            
            # Сохранение данных в файл
            self._save_to_file()
            return True
            
        except Exception as e:
            print(f"Ошибка при обновлении данных: {e}")
            return False
    
    def get_current_rates(self):
        """
        Получение текущих курсов валют.
        
        Returns:
            dict: Текущие курсы валют
        """
        return self.current_rates
    
    def get_historical_data(self, currency, days=14):
        """
        Получение исторических данных для конкретной валюты.
        
        Args:
            currency (str): Код валюты
            days (int): Количество дней для возврата
            
        Returns:
            list: Исторические данные
        """
        if currency in self.historical_data:
            return self.historical_data[currency][-days:]
        return []
    
    def _save_to_file(self):
        """Сохранение данных в файл JSON."""
        try:
            data_to_save = {
                'current_rates': self.current_rates,
                'historical_data': self.historical_data,
                'last_update': datetime.now().isoformat()
            }
            
            with open(self.data_dir / 'currency_data.json', 'w') as f:
                json.dump(data_to_save, f, indent=2)
                
        except Exception as e:
            print(f"Ошибка при сохранении данных: {e}")
    
    def load_from_file(self):
        """Загрузка данных из файла JSON."""
        try:
            data_file = self.data_dir / 'currency_data.json'
            if data_file.exists():
                with open(data_file, 'r') as f:
                    data = json.load(f)
                    self.current_rates = data.get('current_rates', {})
                    self.historical_data = data.get('historical_data', {})
                    
        except Exception as e:
            print(f"Ошибка при загрузке данных: {e}")
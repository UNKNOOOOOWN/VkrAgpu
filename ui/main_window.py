from PyQt6.QtWidgets import (QMainWindow, QTableWidget, QTableWidgetItem, 
                             QVBoxLayout, QWidget, QHeaderView, QPushButton)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from core.api_client import CBRApiClient
from core.data_handler import DataHandler

class MainWindow(QMainWindow):
    """
    Главное окно приложения для отображения курсов валют.
    Содержит таблицу с текущими курсами и элементами управления.
    """
    
    def __init__(self):
        super().__init__()
        self.api_client = CBRApiClient()
        self.data_handler = DataHandler()
        
        # Загрузка сохраненных данных
        self.data_handler.load_from_file()
        
        self.init_ui()
        self.load_data()
        
        # Настройка таймера для автоматического обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_data)
        self.timer.start(1800000)  # 30 минут
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса."""
        self.setWindowTitle("PulseCurrency - Мониторинг курсов валют")
        self.setGeometry(100, 100, 800, 600)
        
        # Создание таблицы для отображения курсов
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Валюта", "Курс", "Изменение", "Изменение %", "Минимум/Максимум"
        ])
        
        # Настройка внешнего вида таблицы
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        
        # Кнопка для ручного обновления данных
        self.refresh_btn = QPushButton("Обновить данные")
        self.refresh_btn.clicked.connect(self.load_data)
        
        # Размещение элементов в layout
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.refresh_btn)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
    
    def load_data(self):
        """Загрузка данных с API и обновление интерфейса."""
        data = self.api_client.get_rates()
        if data:
            self.data_handler.update_data(data)
            self.update_table()
    
    def update_table(self):
        """Обновление таблицы с данными о курсах валют."""
        rates = self.data_handler.get_current_rates()
        currencies = ['USD', 'EUR', 'GBP', 'CNY']
        
        self.table.setRowCount(len(currencies))
        
        for row, currency in enumerate(currencies):
            if currency in rates:
                rate_data = rates[currency]
                current_value = rate_data['Value']
                previous_value = rate_data['Previous']
                change = current_value - previous_value
                change_percent = (change / previous_value) * 100
                
                # Определение цвета для индикации изменений
                color = QColor(0, 180, 0) if change >= 0 else QColor(180, 0, 0)
                
                # Заполнение строк таблицы данными
                self.table.setItem(row, 0, QTableWidgetItem(currency))
                self.table.setItem(row, 1, QTableWidgetItem(f"{current_value:.2f}"))
                
                change_item = QTableWidgetItem(f"{change:+.4f}")
                change_item.setForeground(color)
                self.table.setItem(row, 2, change_item)
                
                change_percent_item = QTableWidgetItem(f"{change_percent:+.2f}%")
                change_percent_item.setForeground(color)
                self.table.setItem(row, 3, change_percent_item)
                
                # Заглушка для минимума/максимума (будет реализовано позже)
                min_max = f"{min(previous_value, current_value):.2f}/{max(previous_value, current_value):.2f}"
                self.table.setItem(row, 4, QTableWidgetItem(min_max))
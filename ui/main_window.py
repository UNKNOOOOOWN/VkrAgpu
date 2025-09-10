import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter

from PyQt6.QtWidgets import (QMainWindow, QTableWidget, QTableWidgetItem, 
                             QVBoxLayout, QWidget, QHeaderView, QPushButton,
                             QHBoxLayout, QLabel, QComboBox, QSpinBox, 
                             QMessageBox, QStatusBar, QSplitter, QProgressBar,
                             QToolBar, QMenu, QMenuBar, QLineEdit, QApplication)
from PyQt6.QtCore import QTimer, Qt, QDate, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QAction

# Импорты ваших модулей
from core.api_client import CBRApiClient, AsyncApiWorker
from core.data_handler import DataHandler

# Настройка логирования
logger = logging.getLogger(__name__)


class ChartLoader(QObject):
    """Класс для асинхронной загрузки данных графика"""
    chart_loaded = pyqtSignal(str, dict)  # currency_code, chart_data
    chart_error = pyqtSignal(str, str)    # currency_code, error_message
    progress_updated = pyqtSignal(int, int, str)  # current, total, currency_code
    
    def __init__(self, data_handler):
        super().__init__()
        self.data_handler = data_handler
        self._is_running = False
        
    def load_chart(self, currency_code, period):
        """Загрузка данных графика"""
        if self._is_running:
            return
            
        self._is_running = True
        try:
            chart_data = self.data_handler.get_historical_data_for_chart(currency_code, period)
            if chart_data:
                self.chart_loaded.emit(currency_code, chart_data)
            else:
                self.chart_error.emit(currency_code, "Нет данных для построения графика")
                
        except Exception as e:
            error_msg = f"Ошибка при загрузке графика: {str(e)}"
            logger.error(error_msg)
            self.chart_error.emit(currency_code, error_msg)
        finally:
            self._is_running = False
            
    def stop(self):
        """Остановка загрузки"""
        self._is_running = False


class MplCanvas(FigureCanvas):
    """Matplotlib canvas for embedding plots."""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Настройка внешнего вида
        self.fig.tight_layout()
        self.axes.grid(True, alpha=0.3)
        self.axes.set_facecolor('#f8f9fa')


class MainWindow(QMainWindow):
    """
    Главное окно приложения для анализа и мониторинга курсов валют.
    """
    
    def __init__(self):
        super().__init__()
        self.api_client = CBRApiClient()
        self.data_handler = DataHandler()
        
        self.current_data = []
        self.historical_data = {}
        self.chart_cache = {}  # Кэш для уже построенных графиков
        
        # Для управления асинхронной загрузкой
        self.chart_loader = ChartLoader(self.data_handler)
        self.chart_loader_thread = QThread()
        self.chart_loader.moveToThread(self.chart_loader_thread)
        self.chart_loader_thread.start()
        
        # Текущая загружаемая валюта
        self.current_currency = None
        self.current_period = 7
        
        self.init_ui()
        self.load_initial_data()
        
        # Подключаем сигналы загрузчика
        self.chart_loader.chart_loaded.connect(self.on_chart_loaded)
        self.chart_loader.chart_error.connect(self.on_chart_error)
        
        # Настройка таймера для автоматического обновления (каждые 30 минут)
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(1800000)
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса."""
        self.setWindowTitle("PulseCurrency - Анализ динамики курсов валют")
        self.setGeometry(100, 100, 1200, 800)
        
        # Создание меню
        self.create_menu()
        
        # Создание тулбара
        self.create_toolbar()
        
        # Главный виджет и layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Панель управления
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Сплиттер для таблицы и графика
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Таблица с курсами валют
        self.create_currency_table()
        splitter.addWidget(self.table)
        
        # График
        self.create_chart_widget()
        splitter.addWidget(self.chart_widget)
        
        splitter.setSizes([400, 400])
        main_layout.addWidget(splitter)
        
        # Статус бар
        self.statusBar().showMessage("Готово к работе")
        
        self.setCentralWidget(central_widget)
    
    def create_menu(self):
        """Создание меню приложения."""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        
        export_action = QAction("Экспорт данных", self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Вид
        view_menu = menubar.addMenu("Вид")
        
        refresh_action = QAction("Обновить", self)
        refresh_action.triggered.connect(self.refresh_data)
        view_menu.addAction(refresh_action)
    
    def create_toolbar(self):
        """Создание тулбара."""
        toolbar = QToolBar("Основные инструменты")
        self.addToolBar(toolbar)
        
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)
        
        toolbar.addSeparator()
        
        self.currency_combo = QComboBox()
        self.currency_combo.setMinimumWidth(120)
        self.currency_combo.currentTextChanged.connect(self.on_currency_selected)
        toolbar.addWidget(QLabel("Валюта:"))
        toolbar.addWidget(self.currency_combo)
        
        self.period_spin = QSpinBox()
        self.period_spin.setRange(7, 30)
        self.period_spin.setValue(7)
        self.period_spin.setSuffix(" дней")
        self.period_spin.valueChanged.connect(self.on_period_changed)
        toolbar.addWidget(QLabel("Период:"))
        toolbar.addWidget(self.period_spin)
    
    def create_control_panel(self):
        """Создание панели управления."""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        # Конвертер валют
        currency_layout = QHBoxLayout()
        currency_layout.addWidget(QLabel("Конвертер:"))
        
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Сумма")
        self.amount_input.setText("100")
        self.amount_input.setMaximumWidth(80)
        currency_layout.addWidget(self.amount_input)
        
        self.from_currency_combo = QComboBox()
        self.from_currency_combo.setMinimumWidth(70)
        currency_layout.addWidget(self.from_currency_combo)
        
        currency_layout.addWidget(QLabel("→"))
        
        self.to_currency_combo = QComboBox()
        self.to_currency_combo.setMinimumWidth(70)
        self.to_currency_combo.setCurrentText("RUB")
        currency_layout.addWidget(self.to_currency_combo)
        
        self.convert_btn = QPushButton("Конвертировать")
        self.convert_btn.clicked.connect(self.convert_currency)
        currency_layout.addWidget(self.convert_btn)
        
        self.convert_result = QLabel()
        currency_layout.addWidget(self.convert_result)
        
        layout.addLayout(currency_layout)
        layout.addStretch()
        
        return panel
    
    def create_currency_table(self):
        """Создание таблицы для отображения курсов."""
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Код", "Валюта", "Номинал", "Курс", "Предыдущий", 
            "Изменение", "Изменение %", "Волатильность"
        ])
        
        # Настройка таблицы
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        # Установка ширины колонок
        self.table.setColumnWidth(0, 60)   # Код
        self.table.setColumnWidth(1, 150)  # Валюта
        self.table.setColumnWidth(2, 70)   # Номинал
        self.table.setColumnWidth(3, 100)  # Курс
        self.table.setColumnWidth(4, 100)  # Предыдущий
        self.table.setColumnWidth(5, 100)  # Изменение
        self.table.setColumnWidth(6, 100)  # Изменение %
        self.table.setColumnWidth(7, 100)  # Волатильность
    
    def create_chart_widget(self):
        """Создание виджета для графика."""
        self.chart_widget = QWidget()
        layout = QVBoxLayout(self.chart_widget)
        
        # Заголовок графика
        self.chart_title = QLabel("Выберите валюту для отображения графика")
        self.chart_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(self.chart_title)
        
        # Canvas для matplotlib
        self.canvas = MplCanvas(self, width=10, height=6, dpi=100)
        layout.addWidget(self.canvas)
        
        # Статистика под графиком
        self.stats_label = QLabel()
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.stats_label)
        
        # Индикатор загрузки
        self.loading_label = QLabel("")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.loading_label)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
    
    def load_initial_data(self):
        """Загрузка начальных данных."""
        self.refresh_data()
    
    def refresh_data(self):
        """Обновление данных."""
        try:
            self.statusBar().showMessage("Загрузка данных...")
            
            # Получаем и обрабатываем данные через DataHandler
            data = self.data_handler.fetch_and_process_data()
            if data:
                self.current_data = data
                self.update_currency_table()
                self.update_currency_combos()
                self.statusBar().showMessage(f"Данные обновлены. Валют: {len(data)}")
            else:
                self.statusBar().showMessage("Ошибка загрузки данных")
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении данных: {e}")
            self.statusBar().showMessage("Ошибка при обновлении данных")
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить данные: {str(e)}")
    
    def update_currency_table(self):
        """Обновление таблицы с данными о курсах валют."""
        if not self.current_data:
            return
            
        self.table.setRowCount(len(self.current_data))
        
        for row, currency in enumerate(self.current_data):
            # Создаем элементы таблицы
            items = [
                QTableWidgetItem(currency['char_code']),
                QTableWidgetItem(currency['name']),
                QTableWidgetItem(str(currency['nominal'])),
                QTableWidgetItem(f"{currency['normalized_value']:.4f}"),
                QTableWidgetItem(f"{currency['normalized_previous']:.4f}"),
                QTableWidgetItem(f"{currency['abs_change']:+.4f}"),
                QTableWidgetItem(f"{currency['percent_change']:+.2f}%")
            ]
            
            # Цвет для изменений (зеленый - рост, красный - падение)
            color = QColor(0, 128, 0) if currency['abs_change'] >= 0 else QColor(200, 0, 0)
            items[5].setForeground(color)  # Изменение
            items[6].setForeground(color)  # Изменение %
            
            # Добавляем элементы в таблицу
            for col, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
            
            # Заглушка для волатильности
            vol_item = QTableWidgetItem("Н/Д")
            vol_item.setFlags(vol_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 7, vol_item)
        
        # Сортируем по коду валюты
        self.table.sortItems(0)
    
    def update_currency_combos(self):
        """Обновление выпадающих списков валют."""
        self.currency_combo.clear()
        self.from_currency_combo.clear()
        self.to_currency_combo.clear()
        
        for currency in self.current_data:
            code = currency['char_code']
            self.currency_combo.addItem(f"{code} - {currency['name']}", code)
            self.from_currency_combo.addItem(code, code)
            self.to_currency_combo.addItem(code, code)
    
    def on_currency_selected(self):
        """Обработчик выбора валюты для графика."""
        currency_code = self.currency_combo.currentData()
        if currency_code:
            self.current_currency = currency_code
            self.update_chart(currency_code)
    
    def on_period_changed(self, period):
        """Обработчик изменения периода графика."""
        self.current_period = period
        if self.current_currency:
            # При изменении периода очищаем кэш для этой валюты
            cache_key = f"{self.current_currency}_{period}"
            if cache_key in self.chart_cache:
                del self.chart_cache[cache_key]
            self.update_chart(self.current_currency)
    
    def on_table_selection_changed(self):
        """Обработчик выбора строки в таблице."""
        selected_items = self.table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            currency_code = self.table.item(row, 0).text()
            self.currency_combo.setCurrentText(f"{currency_code} - {self.table.item(row, 1).text()}")
    
    def update_chart(self, currency_code):
        """Обновление графика для выбранной валюты."""
        period = self.period_spin.value()
        cache_key = f"{currency_code}_{period}"
        
        # Проверяем кэш
        if cache_key in self.chart_cache:
            self._display_chart(self.chart_cache[cache_key])
            return
        
        # Показываем индикатор загрузки
        self.show_loading_indicator(currency_code)
        
        # Запускаем асинхронную загрузку
        QApplication.processEvents()  # Обновляем UI
        self.chart_loader.load_chart(currency_code, period)
    
    def show_loading_indicator(self, currency_code):
        """Показать индикатор загрузки"""
        self.loading_label.setText(f"Загрузка данных для {currency_code}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
    
    def hide_loading_indicator(self):
        """Скрыть индикатор загрузки"""
        self.loading_label.setText("")
        self.progress_bar.setVisible(False)
    
    def on_chart_loaded(self, currency_code, chart_data):
        """Обработчик успешной загрузки графика"""
        if currency_code != self.current_currency:
            return  # Игнорируем старые запросы
            
        self.hide_loading_indicator()
        
        # Сохраняем в кэш
        cache_key = f"{currency_code}_{self.current_period}"
        self.chart_cache[cache_key] = chart_data
        
        # Отображаем график
        self._display_chart(chart_data)
    
    def on_chart_error(self, currency_code, error_message):
        """Обработчик ошибки загрузки графика"""
        if currency_code != self.current_currency:
            return
            
        self.hide_loading_indicator()
        
        # Показываем сообщение об ошибке
        self.chart_title.setText(f"Ошибка загрузки данных для {currency_code}")
        self.canvas.axes.clear()
        self.canvas.axes.text(0.5, 0.5, error_message, 
                            horizontalalignment='center', verticalalignment='center',
                            transform=self.canvas.axes.transAxes, fontsize=10)
        self.canvas.draw()
        self.stats_label.setText("")
    
    def _display_chart(self, chart_data):
        """Отображает график из данных"""
        currency_code = chart_data['currency_code']
        
        # Обновляем заголовок
        self.chart_title.setText(
            f"{chart_data['currency_name']} ({currency_code}) - "
            f"Волатильность: {chart_data['volatility']:.2f}%"
        )
        
        # Очищаем и строим график
        self.canvas.axes.clear()
        
        dates = [datetime.fromisoformat(d) for d in chart_data['dates']]
        values = chart_data['normalized_values']
        
        # Построение графика
        self.canvas.axes.plot(dates, values, 'b-', linewidth=2, label='Курс', marker='o', markersize=3)
        self.canvas.axes.set_xlabel('Дата')
        self.canvas.axes.set_ylabel('Курс, руб.')
        self.canvas.axes.set_title(f'Динамика курса {currency_code} за {len(dates)} дней')
        self.canvas.axes.legend()
        
        # Форматирование дат на оси X
        self.canvas.axes.xaxis.set_major_formatter(DateFormatter('%d.%m.%Y'))
        self.canvas.fig.autofmt_xdate()
        
        self.canvas.draw()
        
        # Обновляем статистику
        stats = chart_data['statistics']
        stats_text = (
            f"Среднее: {stats['mean']:.4f} | "
            f"Мин: {stats['min']:.4f} | "
            f"Макс: {stats['max']:.4f} | "
            f"Общее изменение: {stats['total_return']:+.2f}%"
        )
        self.stats_label.setText(stats_text)
        
        # Обновляем волатильность в таблице
        self.update_volatility_in_table(currency_code, chart_data['volatility'])
    
    def update_volatility_in_table(self, currency_code, volatility):
        """Обновление значения волатильности в таблице."""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == currency_code:
                vol_item = QTableWidgetItem(f"{volatility:.2f}%")
                vol_item.setFlags(vol_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # Цвет в зависимости от уровня волатильности
                if volatility > 2.0:
                    vol_item.setForeground(QColor(200, 0, 0))  # Высокая волатильность
                elif volatility > 1.0:
                    vol_item.setForeground(QColor(200, 100, 0))  # Средняя волатильность
                else:
                    vol_item.setForeground(QColor(0, 128, 0))  # Низкая волатильность
                    
                self.table.setItem(row, 7, vol_item)
                break
    
    def convert_currency(self):
        """Конвертация валюты."""
        try:
            amount_text = self.amount_input.text().replace(',', '.')
            amount = float(amount_text)
            from_curr = self.from_currency_combo.currentData()
            to_curr = self.to_currency_combo.currentData()
            
            result = self.data_handler.calculate_currency_conversion(amount, from_curr, to_curr)
            if result is not None:
                self.convert_result.setText(
                    f"{amount:.2f} {from_curr} = {result:.2f} {to_curr}"
                )
            else:
                self.convert_result.setText("Ошибка конвертации")
                
        except ValueError:
            self.convert_result.setText("Неверная сумма")
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            self.convert_result.setText("Ошибка конвертации")
    
    def export_data(self):
        """Экспорт данных в файл."""
        QMessageBox.information(self, "Экспорт", "Функция экспорта в разработке")
    
    def closeEvent(self, event):
        """Обработчик закрытия окна."""
        # Останавливаем загрузчик
        self.chart_loader.stop()
        self.chart_loader_thread.quit()
        self.chart_loader_thread.wait()
        
        # Останавливаем таймер
        self.timer.stop()
        
        event.accept()
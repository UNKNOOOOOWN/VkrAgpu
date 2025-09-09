"""
Модуль финансовых расчетов для анализа динамики курсов валют.
Реализует методы статистического анализа и финансовых вычислений.
"""

import numpy as np
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class Calculator:
    """
    Класс для выполнения финансовых расчетов и анализа валютных курсов.
    """
    
    @staticmethod
    def calculate_changes(current_rate: float, previous_rate: float, nominal: int = 1) -> Tuple[float, float]:
        """
        Расчет изменений курса в абсолютных и процентных значениях.
        
        Args:
            current_rate: Текущий курс валюты
            previous_rate: Предыдущий курс валюты
            nominal: Номинал валюты (по умолчанию 1)
            
        Returns:
            Tuple[float, float]: (абсолютное изменение, процентное изменение)
        """
        try:
            # Нормализуем курсы с учетом номинала
            current_normalized = current_rate / nominal
            previous_normalized = previous_rate / nominal
            
            # Расчет абсолютного изменения
            absolute_change = current_normalized - previous_normalized
            
            # Расчет процентного изменения
            if previous_normalized != 0:
                percent_change = (absolute_change / previous_normalized) * 100
            else:
                percent_change = 0.0
                logger.warning("Предыдущий курс равен нулю, невозможно рассчитать процентное изменение")
            
            return round(absolute_change, 4), round(percent_change, 2)
            
        except (TypeError, ValueError) as e:
            logger.error(f"Ошибка при расчете изменений: {e}")
            return 0.0, 0.0
    
    @staticmethod
    def calculate_volatility(historical_rates: List[float], annualize: bool = True) -> float:
        """
        Расчет волатильности на основе исторических данных.
        
        Args:
            historical_rates: Список исторических значений курса
            annualize: Флаг annualized волатильности (годовая)
            
        Returns:
            float: Значение волатильности в процентах
        """
        if not historical_rates or len(historical_rates) < 2:
            return 0.0
        
        try:
            # Преобразуем в numpy array для удобства вычислений
            rates = np.array(historical_rates)
            
            # Расчет логарифмической доходности
            log_returns = np.log(rates[1:] / rates[:-1])
            
            # Стандартное отклонение доходности (дневная волатильность)
            daily_volatility = np.std(log_returns)
            
            if annualize:
                # Annualized volatility (предполагаем 252 торговых дня в году)
                annual_volatility = daily_volatility * np.sqrt(252)
                return round(annual_volatility * 100, 2)  # в процентах
            else:
                return round(daily_volatility * 100, 2)  # дневная волатильность в %
                
        except Exception as e:
            logger.error(f"Ошибка при расчете волатильности: {e}")
            return 0.0
    
    @staticmethod
    def calculate_moving_average(historical_rates: List[float], window: int = 20) -> List[float]:
        """
        Расчет скользящего среднего.
        
        Args:
            historical_rates: Список исторических значений курса
            window: Размер окна для скользящего среднего
            
        Returns:
            List[float]: Значения скользящего среднего
        """
        if not historical_rates or len(historical_rates) < window:
            return []
        
        try:
            rates = np.array(historical_rates)
            moving_avg = np.convolve(rates, np.ones(window)/window, mode='valid')
            return moving_avg.tolist()
            
        except Exception as e:
            logger.error(f"Ошибка при расчете скользящего среднего: {e}")
            return []
    
    @staticmethod
    def convert_currency(amount: float, from_rate: float, to_rate: float, 
                        from_nominal: int = 1, to_nominal: int = 1) -> float:
        """
        Конвертация суммы из одной валюты в другую.
        
        Args:
            amount: Сумма для конвертации
            from_rate: Курс исходной валюты
            to_rate: Курс целевой валюты
            from_nominal: Номинал исходной валюты
            to_nominal: Номинал целевой валюты
            
        Returns:
            float: Конвертированная сумма
        """
        try:
            # Нормализуем курсы (приводим к курсу за 1 единицу валюты)
            from_normalized = from_rate / from_nominal
            to_normalized = to_rate / to_nominal
            
            # Конвертируем через рубль (или другую базовую валюту)
            # amount * (from_normalized) / to_normalized
            converted_amount = amount * from_normalized / to_normalized
            return round(converted_amount, 2)
            
        except ZeroDivisionError:
            logger.error("Деление на ноль при конвертации валюты")
            return 0.0
        except Exception as e:
            logger.error(f"Ошибка при конвертации валюты: {e}")
            return 0.0
    
    @staticmethod
    def calculate_correlation(rates1: List[float], rates2: List[float]) -> float:
        """
        Расчет корреляции между двумя рядами курсов валют.
        
        Args:
            rates1: Первый ряд значений курсов
            rates2: Второй ряд значений курсов
            
        Returns:
            float: Коэффициент корреляции (-1 до 1)
        """
        if len(rates1) != len(rates2) or len(rates1) < 2:
            return 0.0
        
        try:
            correlation = np.corrcoef(rates1, rates2)[0, 1]
            return round(correlation, 4)
            
        except Exception as e:
            logger.error(f"Ошибка при расчете корреляции: {e}")
            return 0.0
    
    @staticmethod
    def calculate_returns(historical_rates: List[float]) -> List[float]:
        """
        Расчет дневной доходности.
        
        Args:
            historical_rates: Список исторических значений курса
            
        Returns:
            List[float]: Список значений доходности в процентах
        """
        if len(historical_rates) < 2:
            return []
        
        try:
            returns = []
            for i in range(1, len(historical_rates)):
                daily_return = (historical_rates[i] - historical_rates[i-1]) / historical_rates[i-1] * 100
                returns.append(round(daily_return, 2))
            return returns
            
        except Exception as e:
            logger.error(f"Ошибка при расчете доходности: {e}")
            return []
    
    @staticmethod
    def calculate_statistics(historical_rates: List[float]) -> dict:
        """
        Расчет базовой статистики для ряда курсов.
        
        Args:
            historical_rates: Список исторических значений курса
            
        Returns:
            dict: Словарь со статистическими показателями
        """
        if not historical_rates:
            return {}
        
        try:
            rates = np.array(historical_rates)
            returns = Calculator.calculate_returns(historical_rates)
            
            statistics = {
                'mean': round(float(np.mean(rates)), 4),
                'median': round(float(np.median(rates)), 4),
                'std_dev': round(float(np.std(rates)), 4),
                'min': round(float(np.min(rates)), 4),
                'max': round(float(np.max(rates)), 4),
                'total_return': round((rates[-1] - rates[0]) / rates[0] * 100, 2) if rates[0] != 0 else 0,
                'avg_daily_return': round(np.mean(returns), 2) if returns else 0,
            }
            return statistics
            
        except Exception as e:
            logger.error(f"Ошибка при расчете статистики: {e}")
            return {}


# Создаем экземпляр калькулятора для удобства импорта
calculator = Calculator()
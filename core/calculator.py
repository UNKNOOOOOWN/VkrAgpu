"""
Модуль финансовых расчетов для анализа динамики курсов валют.
Реализует методы статистического анализа и финансовых вычислений.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Union
import logging
from numpy.typing import ArrayLike

logger = logging.getLogger(__name__)


class Calculator:
    """
    Класс для выполнения финансовых расчетов и анализа валютных курсов.
    Оптимизирован для быстрой работы и интеграции с асинхронным UI.
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
            # Быстрая проверка на нулевые значения
            if previous_rate == 0:
                logger.debug("Предыдущий курс равен нулю")
                return 0.0, 0.0
            
            # Нормализуем курсы с учетом номинала
            current_normalized = current_rate / nominal
            previous_normalized = previous_rate / nominal
            
            # Расчет абсолютного изменения
            absolute_change = current_normalized - previous_normalized
            
            # Расчет процентного изменения
            percent_change = (absolute_change / previous_normalized) * 100
            
            return round(absolute_change, 4), round(percent_change, 2)
            
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.debug(f"Ошибка при расчете изменений: {e}")
            return 0.0, 0.0
    
    @staticmethod
    def calculate_volatility(historical_rates: ArrayLike, annualize: bool = True) -> float:
        """
        Расчет волатильности на основе исторических данных.
        Оптимизированная версия с использованием векторных операций.
        
        Args:
            historical_rates: Массив исторических значений курса
            annualize: Флаг annualized волатильности (годовая)
            
        Returns:
            float: Значение волатильности в процентах
        """
        if historical_rates is None or len(historical_rates) < 2:
            return 0.0
        
        try:
            # Быстрое преобразование в numpy array
            rates = np.asarray(historical_rates, dtype=np.float64)
            
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
            logger.debug(f"Ошибка при расчете волатильности: {e}")
            return 0.0
    
    @staticmethod
    def calculate_moving_average(historical_rates: ArrayLike, window: int = 20) -> np.ndarray:
        """
        Расчет скользящего среднего с использованием быстрых numpy операций.
        
        Args:
            historical_rates: Массив исторических значений курса
            window: Размер окна для скользящего среднего
            
        Returns:
            np.ndarray: Значения скользящего среднего
        """
        if historical_rates is None or len(historical_rates) < window:
            return np.array([])
        
        try:
            rates = np.asarray(historical_rates, dtype=np.float64)
            
            # Используем cumsum для быстрого расчета скользящего среднего
            cumsum = np.cumsum(rates)
            moving_avg = (cumsum[window:] - cumsum[:-window]) / window
            
            return moving_avg
            
        except Exception as e:
            logger.debug(f"Ошибка при расчете скользящего среднего: {e}")
            return np.array([])
    
    @staticmethod
    def convert_currency(amount: float, from_rate: float, to_rate: float, 
                        from_nominal: int = 1, to_nominal: int = 1) -> float:
        """
        Конвертация суммы из одной валюты в другую.
        Оптимизированная версия с проверкой ошибок.
        
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
            # Быстрые проверки
            if amount == 0:
                return 0.0
            if to_rate == 0:
                logger.debug("Курс целевой валюты равен нулю")
                return 0.0
            
            # Нормализуем курсы (приводим к курсу за 1 единицу валюты)
            from_normalized = from_rate / from_nominal
            to_normalized = to_rate / to_nominal
            
            # Конвертируем через базовую валюту
            converted_amount = amount * from_normalized / to_normalized
            return round(converted_amount, 2)
            
        except (ZeroDivisionError, TypeError, ValueError) as e:
            logger.debug(f"Ошибка при конвертации валюты: {e}")
            return 0.0
    
    @staticmethod
    def calculate_correlation(rates1: ArrayLike, rates2: ArrayLike) -> float:
        """
        Расчет корреляции между двумя рядами курсов валют.
        Оптимизированная версия с проверкой длины массивов.
        
        Args:
            rates1: Первый ряд значений курсов
            rates2: Второй ряд значений курсов
            
        Returns:
            float: Коэффициент корреляции (-1 до 1)
        """
        if (rates1 is None or rates2 is None or 
            len(rates1) != len(rates2) or len(rates1) < 2):
            return 0.0
        
        try:
            # Быстрое преобразование в numpy arrays
            arr1 = np.asarray(rates1, dtype=np.float64)
            arr2 = np.asarray(rates2, dtype=np.float64)
            
            # Расчет корреляции
            correlation = np.corrcoef(arr1, arr2)[0, 1]
            
            # Проверка на NaN
            if np.isnan(correlation):
                return 0.0
                
            return round(correlation, 4)
            
        except Exception as e:
            logger.debug(f"Ошибка при расчете корреляции: {e}")
            return 0.0
    
    @staticmethod
    def calculate_returns(historical_rates: ArrayLike) -> np.ndarray:
        """
        Расчет дневной доходности с использованием векторных операций.
        
        Args:
            historical_rates: Массив исторических значений курса
            
        Returns:
            np.ndarray: Массив значений доходности в процентах
        """
        if historical_rates is None or len(historical_rates) < 2:
            return np.array([])
        
        try:
            rates = np.asarray(historical_rates, dtype=np.float64)
            
            # Векторный расчет доходности
            returns = (rates[1:] - rates[:-1]) / rates[:-1] * 100
            
            # Округление и замена NaN/Inf
            returns = np.round(returns, 2)
            returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
            
            return returns
            
        except Exception as e:
            logger.debug(f"Ошибка при расчете доходности: {e}")
            return np.array([])
    
    @staticmethod
    def calculate_statistics(historical_rates: ArrayLike) -> Dict[str, float]:
        """
        Расчет базовой статистики для ряда курсов.
        Оптимизированная версия с использованием numpy.
        
        Args:
            historical_rates: Массив исторических значений курса
            
        Returns:
            dict: Словарь со статистическими показателями
        """
        if historical_rates is None or len(historical_rates) == 0:
            return {}
        
        try:
            rates = np.asarray(historical_rates, dtype=np.float64)
            
            # Основная статистика
            statistics = {
                'mean': round(float(np.mean(rates)), 4),
                'median': round(float(np.median(rates)), 4),
                'std_dev': round(float(np.std(rates)), 4),
                'min': round(float(np.min(rates)), 4),
                'max': round(float(np.max(rates)), 4),
                'range': round(float(np.max(rates) - np.min(rates)), 4),
            }
            
            # Расчет общей доходности
            if rates[0] != 0:
                statistics['total_return'] = round((rates[-1] - rates[0]) / rates[0] * 100, 2)
            else:
                statistics['total_return'] = 0.0
            
            # Расчет средней дневной доходности
            if len(rates) > 1:
                returns = Calculator.calculate_returns(rates)
                if len(returns) > 0:
                    statistics['avg_daily_return'] = round(float(np.mean(returns)), 2)
                else:
                    statistics['avg_daily_return'] = 0.0
            else:
                statistics['avg_daily_return'] = 0.0
            
            return statistics
            
        except Exception as e:
            logger.debug(f"Ошибка при расчете статистики: {e}")
            return {}
    
    @staticmethod
    def calculate_ema(historical_rates: ArrayLike, span: int = 20) -> np.ndarray:
        """
        Расчет экспоненциального скользящего среднего (EMA).
        
        Args:
            historical_rates: Массив исторических значений курса
            span: Период сглаживания
            
        Returns:
            np.ndarray: Значения EMA
        """
        if historical_rates is None or len(historical_rates) < span:
            return np.array([])
        
        try:
            rates = np.asarray(historical_rates, dtype=np.float64)
            
            # Расчет EMA
            alpha = 2 / (span + 1)
            ema = np.zeros_like(rates)
            ema[0] = rates[0]
            
            for i in range(1, len(rates)):
                ema[i] = alpha * rates[i] + (1 - alpha) * ema[i-1]
            
            return ema
            
        except Exception as e:
            logger.debug(f"Ошибка при расчете EMA: {e}")
            return np.array([])
    
    @staticmethod
    def calculate_rsi(historical_rates: ArrayLike, period: int = 14) -> np.ndarray:
        """
        Расчет индекса относительной силы (RSI).
        
        Args:
            historical_rates: Массив исторических значений курса
            period: Период для расчета RSI
            
        Returns:
            np.ndarray: Значения RSI
        """
        if historical_rates is None or len(historical_rates) <= period:
            return np.array([])
        
        try:
            rates = np.asarray(historical_rates, dtype=np.float64)
            deltas = np.diff(rates)
            
            # Разделяем рост и падение
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            # Расчет средних значений
            avg_gain = np.convolve(gains, np.ones(period)/period, mode='valid')
            avg_loss = np.convolve(losses, np.ones(period)/period, mode='valid')
            
            # Расчет RS и RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # Заполнение начала массива NaN значениями
            rsi_full = np.full(len(rates), np.nan)
            rsi_full[period:] = rsi
            
            return rsi_full
            
        except Exception as e:
            logger.debug(f"Ошибка при расчете RSI: {e}")
            return np.array([])


# Создаем экземпляр калькулятора для удобства импорта
calculator = Calculator()
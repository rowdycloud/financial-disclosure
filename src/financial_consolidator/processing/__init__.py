"""Transaction processing pipeline components."""

from financial_consolidator.processing.normalizer import (
    Normalizer,
    normalize_transactions,
)
from financial_consolidator.processing.categorizer import (
    Categorizer,
    categorize_transactions,
)
from financial_consolidator.processing.deduplicator import (
    Deduplicator,
    find_duplicates,
)
from financial_consolidator.processing.balance_calculator import (
    BalanceCalculator,
    calculate_balances,
)
from financial_consolidator.processing.anomaly_detector import (
    AnomalyDetector,
    detect_anomalies,
)

__all__ = [
    "Normalizer",
    "normalize_transactions",
    "Categorizer",
    "categorize_transactions",
    "Deduplicator",
    "find_duplicates",
    "BalanceCalculator",
    "calculate_balances",
    "AnomalyDetector",
    "detect_anomalies",
]

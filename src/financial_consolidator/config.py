"""Configuration loading and validation for the financial consolidator."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

import yaml

from financial_consolidator.models.account import Account
from financial_consolidator.models.category import Category, CategoryRule, ManualOverride
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class ConfigError(Exception):
    """Exception raised for configuration errors."""

    pass


# Default values for AnomalyConfig
DEFAULT_FEE_KEYWORDS = [
    "FEE", "CHARGE", "PENALTY", "LATE FEE", "OVERDRAFT", "NSF", "RETURNED ITEM"
]
DEFAULT_CASH_ADVANCE_KEYWORDS = [
    "CASH ADVANCE", "CASH WITHDRAWAL", "ATM WITHDRAWAL", "CASINO"
]


@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection.

    Attributes:
        large_transaction_threshold: Flag transactions above this amount.
        date_gap_warning_days: Warn about gaps longer than this.
        date_gap_alert_days: Alert about gaps longer than this.
        fee_keywords: Keywords to detect fees.
        cash_advance_keywords: Keywords to detect cash advances.
        custom_patterns: Custom regex patterns for anomaly detection.
    """

    large_transaction_threshold: Decimal = field(default_factory=lambda: Decimal("5000.00"))
    date_gap_warning_days: int = 7
    date_gap_alert_days: int = 30
    fee_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_FEE_KEYWORDS))
    cash_advance_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_CASH_ADVANCE_KEYWORDS))
    custom_patterns: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AnomalyConfig":
        """Create from dictionary."""
        threshold = Decimal("5000.00")
        if "large_transaction_threshold" in data:
            threshold = Decimal(str(data["large_transaction_threshold"]))

        return cls(
            large_transaction_threshold=threshold,
            date_gap_warning_days=int(data.get("date_gap_warning_days", 7)),  # type: ignore[arg-type]
            date_gap_alert_days=int(data.get("date_gap_alert_days", 30)),  # type: ignore[arg-type]
            fee_keywords=list(data.get("fee_keywords", DEFAULT_FEE_KEYWORDS)),  # type: ignore[arg-type]
            cash_advance_keywords=list(data.get("cash_advance_keywords", DEFAULT_CASH_ADVANCE_KEYWORDS)),  # type: ignore[arg-type]
            custom_patterns=list(data.get("custom_patterns", [])),  # type: ignore[arg-type]
        )


@dataclass
class OutputConfig:
    """Configuration for output generation.

    Attributes:
        format: Output format (xlsx or csv).
        date_format: Date format for output.
        currency_symbol: Currency symbol for display.
        decimal_places: Number of decimal places.
    """

    format: str = "xlsx"
    date_format: str = "%Y-%m-%d"
    currency_symbol: str = "$"
    decimal_places: int = 2

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "OutputConfig":
        """Create from dictionary."""
        return cls(
            format=str(data.get("format", "xlsx")),
            date_format=str(data.get("date_format", "%Y-%m-%d")),
            currency_symbol=str(data.get("currency_symbol", "$")),
            decimal_places=int(data.get("decimal_places", 2)),  # type: ignore[arg-type]
        )


@dataclass
class LoggingConfig:
    """Configuration for logging.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        file: Path to log file.
    """

    level: str = "INFO"
    file: str = "financial_consolidator.log"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "LoggingConfig":
        """Create from dictionary."""
        return cls(
            level=str(data.get("level", "INFO")),
            file=str(data.get("file", "financial_consolidator.log")),
        )


@dataclass
class Config:
    """Main configuration container.

    Attributes:
        accounts: Dictionary of account ID to Account.
        file_mappings: Dictionary of filename to account ID.
        categories: Dictionary of category ID to Category.
        category_rules: List of category rules (sorted by priority).
        manual_overrides: List of manual category overrides.
        anomaly: Anomaly detection configuration.
        output: Output generation configuration.
        logging: Logging configuration.
        start_date: Start date for filtering transactions.
        end_date: End date for filtering transactions.
    """

    accounts: dict[str, Account] = field(default_factory=dict)
    file_mappings: dict[str, str] = field(default_factory=dict)
    categories: dict[str, Category] = field(default_factory=dict)
    category_rules: list[CategoryRule] = field(default_factory=list)
    manual_overrides: list[ManualOverride] = field(default_factory=list)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    def get_account_for_file(self, filename: str) -> Optional[Account]:
        """Get the account associated with a filename.

        First checks explicit file mappings, then pattern matching.

        Args:
            filename: The filename to look up.

        Returns:
            Account if found, None otherwise.
        """
        # Check explicit mappings first
        if filename in self.file_mappings:
            account_id = self.file_mappings[filename]
            return self.accounts.get(account_id)

        # Check pattern matching
        for account in self.accounts.values():
            if account.matches_file(filename):
                return account

        return None

    def add_file_mapping(self, filename: str, account_id: str) -> None:
        """Add a file to account mapping.

        Args:
            filename: The filename to map.
            account_id: The account ID to map to.
        """
        self.file_mappings[filename] = account_id

    def get_matching_rules(
        self,
        description: str,
        amount: Decimal,
        account_id: str,
    ) -> Optional[CategoryRule]:
        """Find the first matching category rule.

        Rules are evaluated in priority order (highest first).

        Args:
            description: Transaction description.
            amount: Transaction amount.
            account_id: Account ID.

        Returns:
            First matching rule, or None.
        """
        for rule in self.category_rules:
            if rule.matches(description, amount, account_id):
                return rule
        return None

    def get_matching_override(
        self,
        transaction_date: str,
        amount: Decimal,
        description: str,
    ) -> Optional[ManualOverride]:
        """Find the first matching manual override.

        Overrides are evaluated in priority order (highest first).

        Args:
            transaction_date: Transaction date in YYYY-MM-DD format.
            amount: Transaction amount.
            description: Transaction description.

        Returns:
            First matching override, or None.
        """
        for override in self.manual_overrides:
            if override.matches(transaction_date, amount, description):
                return override
        return None


def load_yaml_file(path: Path) -> dict[str, object]:
    """Load a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML content.

    Raises:
        FileNotFoundError: If file doesn't exist.
        yaml.YAMLError: If file is invalid YAML.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, encoding="utf-8") as f:
        content = yaml.safe_load(f)

    return content if content else {}


def load_settings(path: Path) -> tuple[AnomalyConfig, OutputConfig, LoggingConfig]:
    """Load settings from settings.yaml.

    Args:
        path: Path to settings.yaml.

    Returns:
        Tuple of (AnomalyConfig, OutputConfig, LoggingConfig).
    """
    data = load_yaml_file(path)

    anomaly = AnomalyConfig()
    if "anomaly_detection" in data:
        anomaly = AnomalyConfig.from_dict(data["anomaly_detection"])  # type: ignore[arg-type]

    output = OutputConfig()
    if "output" in data:
        output = OutputConfig.from_dict(data["output"])  # type: ignore[arg-type]

    logging_config = LoggingConfig()
    if "logging" in data:
        logging_config = LoggingConfig.from_dict(data["logging"])  # type: ignore[arg-type]

    return anomaly, output, logging_config


def load_accounts(path: Path) -> tuple[dict[str, Account], dict[str, str]]:
    """Load accounts and file mappings from accounts.yaml.

    Args:
        path: Path to accounts.yaml.

    Returns:
        Tuple of (accounts dict, file_mappings dict).
    """
    data = load_yaml_file(path)

    accounts: dict[str, Account] = {}
    if "accounts" in data:
        accounts_list = data["accounts"]
        if isinstance(accounts_list, dict):
            # Dict format: accounts: {id: {...}}
            for account_id, account_data in accounts_list.items():
                account_data["id"] = account_id  # type: ignore[index]
                account = Account.from_dict(account_data)  # type: ignore[arg-type]
                accounts[account.id] = account
        elif isinstance(accounts_list, list):
            # List format: accounts: [{id: ..., ...}]
            for account_data in accounts_list:
                account = Account.from_dict(account_data)
                accounts[account.id] = account

    file_mappings: dict[str, str] = {}
    if "file_mappings" in data and data["file_mappings"] is not None:
        file_mappings = dict(data["file_mappings"])  # type: ignore[arg-type]

    return accounts, file_mappings


def load_categories(path: Path) -> tuple[dict[str, Category], list[CategoryRule]]:
    """Load categories and rules from categories.yaml.

    Args:
        path: Path to categories.yaml.

    Returns:
        Tuple of (categories dict, rules list sorted by priority desc).
    """
    data = load_yaml_file(path)

    categories: dict[str, Category] = {}
    if "categories" in data and data["categories"] is not None:
        cat_list = data["categories"]
        if not isinstance(cat_list, list):
            raise ConfigError(f"'categories' must be a list, got {type(cat_list).__name__}")
        for cat_data in cat_list:
            category = Category.from_dict(cat_data)
            categories[category.id] = category

    rules: list[CategoryRule] = []
    if "rules" in data and data["rules"] is not None:
        rule_list = data["rules"]
        if not isinstance(rule_list, list):
            raise ConfigError(f"'rules' must be a list, got {type(rule_list).__name__}")
        for rule_data in rule_list:
            rule = CategoryRule.from_dict(rule_data)
            rules.append(rule)

    # Sort rules by priority (highest first)
    rules.sort(key=lambda r: r.priority, reverse=True)

    return categories, rules


def load_manual_overrides(path: Path) -> list[ManualOverride]:
    """Load manual category overrides from manual_categories.yaml.

    Args:
        path: Path to manual_categories.yaml.

    Returns:
        List of manual overrides sorted by priority desc.
    """
    if not path.exists():
        return []

    data = load_yaml_file(path)

    overrides: list[ManualOverride] = []
    if "overrides" in data and data["overrides"] is not None:
        override_list = data["overrides"]
        if not isinstance(override_list, list):
            raise ConfigError(f"'overrides' must be a list, got {type(override_list).__name__}")
        for override_data in override_list:
            override = ManualOverride.from_dict(override_data)
            overrides.append(override)

    # Sort by priority (highest first)
    overrides.sort(key=lambda o: o.priority, reverse=True)

    return overrides


def load_config(
    settings_path: Optional[Path] = None,
    accounts_path: Optional[Path] = None,
    categories_path: Optional[Path] = None,
    manual_overrides_path: Optional[Path] = None,
    config_dir: Optional[Path] = None,
) -> Config:
    """Load complete configuration from all config files.

    Args:
        settings_path: Path to settings.yaml (or None to use default).
        accounts_path: Path to accounts.yaml (or None to use default).
        categories_path: Path to categories.yaml (or None to use default).
        manual_overrides_path: Path to manual_categories.yaml (or None to use default).
        config_dir: Base config directory (default: ./config).

    Returns:
        Complete Config object.

    Raises:
        FileNotFoundError: If required config files are missing.
    """
    if config_dir is None:
        config_dir = Path("config")

    # Set default paths
    if settings_path is None:
        settings_path = config_dir / "settings.yaml"
    if accounts_path is None:
        accounts_path = config_dir / "accounts.yaml"
    if categories_path is None:
        categories_path = config_dir / "categories.yaml"
    if manual_overrides_path is None:
        manual_overrides_path = config_dir / "manual_categories.yaml"

    config = Config()

    # Load settings (optional - use defaults if missing)
    if settings_path.exists():
        config.anomaly, config.output, config.logging = load_settings(settings_path)
        logger.info(f"Loaded settings from {settings_path}")
    else:
        logger.warning(f"Settings file not found: {settings_path}, using defaults")

    # Load accounts (optional for first run)
    if accounts_path.exists():
        config.accounts, config.file_mappings = load_accounts(accounts_path)
        logger.info(f"Loaded {len(config.accounts)} accounts from {accounts_path}")
    else:
        logger.warning(f"Accounts file not found: {accounts_path}")

    # Load categories (required for categorization)
    if categories_path.exists():
        config.categories, config.category_rules = load_categories(categories_path)
        logger.info(
            f"Loaded {len(config.categories)} categories and "
            f"{len(config.category_rules)} rules from {categories_path}"
        )
    else:
        logger.warning(f"Categories file not found: {categories_path}")

    # Load manual overrides (optional)
    config.manual_overrides = load_manual_overrides(manual_overrides_path)
    if config.manual_overrides:
        logger.info(f"Loaded {len(config.manual_overrides)} manual overrides")

    return config


def save_accounts(path: Path, config: Config) -> None:
    """Save accounts and file mappings to accounts.yaml.

    This is used to persist interactive account mappings.

    Args:
        path: Path to save accounts.yaml.
        config: Config object with accounts and mappings.
    """
    data: dict[str, object] = {
        "file_mappings": config.file_mappings,
        "accounts": {},
    }

    accounts_dict: dict[str, dict[str, object]] = {}
    for account in config.accounts.values():
        accounts_dict[account.id] = {
            "name": account.name,
            "type": account.account_type.value,
        }
        if account.institution:
            accounts_dict[account.id]["institution"] = account.institution
        if account.account_number_masked:
            accounts_dict[account.id]["account_number_masked"] = account.account_number_masked
        if account.opening_balance:
            accounts_dict[account.id]["opening_balance"] = str(account.opening_balance)
        if account.opening_balance_date:
            accounts_dict[account.id]["opening_balance_date"] = account.opening_balance_date.isoformat()
        if account.source_file_patterns:
            accounts_dict[account.id]["source_file_patterns"] = account.source_file_patterns
        if account.display_order:
            accounts_dict[account.id]["display_order"] = account.display_order

    data["accounts"] = accounts_dict

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved accounts configuration to {path}")

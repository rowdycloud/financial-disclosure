"""Configuration loading and validation for the financial consolidator."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import yaml

from financial_consolidator.models.account import Account
from financial_consolidator.models.category import (
    Category,
    CategoryCorrection,
    CategoryRule,
    ManualOverride,
    MatchMode,
)
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

        # Type-safe extraction from YAML data
        raw_warning = data.get("date_gap_warning_days", 7)
        warning_days = int(raw_warning) if isinstance(raw_warning, (int, str, float)) else 7

        raw_alert = data.get("date_gap_alert_days", 30)
        alert_days = int(raw_alert) if isinstance(raw_alert, (int, str, float)) else 30

        raw_fees = data.get("fee_keywords", DEFAULT_FEE_KEYWORDS)
        fee_keywords = list(raw_fees) if isinstance(raw_fees, (list, tuple)) else list(DEFAULT_FEE_KEYWORDS)

        raw_cash = data.get("cash_advance_keywords", DEFAULT_CASH_ADVANCE_KEYWORDS)
        cash_keywords = list(raw_cash) if isinstance(raw_cash, (list, tuple)) else list(DEFAULT_CASH_ADVANCE_KEYWORDS)

        raw_patterns = data.get("custom_patterns", [])
        custom_patterns = list(raw_patterns) if isinstance(raw_patterns, (list, tuple)) else []

        return cls(
            large_transaction_threshold=threshold,
            date_gap_warning_days=warning_days,
            date_gap_alert_days=alert_days,
            fee_keywords=fee_keywords,
            cash_advance_keywords=cash_keywords,
            custom_patterns=custom_patterns,
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
        raw_decimal_places = data.get("decimal_places", 2)
        decimal_places = int(raw_decimal_places) if isinstance(raw_decimal_places, (int, str, float)) else 2

        return cls(
            format=str(data.get("format", "xlsx")),
            date_format=str(data.get("date_format", "%Y-%m-%d")),
            currency_symbol=str(data.get("currency_symbol", "$")),
            decimal_places=decimal_places,
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
class AICategorizationConfig:
    """Configuration for AI-powered categorization.

    Attributes:
        enabled: Whether AI categorization is enabled.
        api_key_env: Environment variable name for API key.
        model: Model to use for AI requests.
        max_tokens: Maximum tokens for responses.
        budget_limit: Maximum spend per run in USD.
        require_confirmation: Whether to require confirmation before spending.
        validation_threshold: Confidence threshold below which to validate.
        correction_threshold: AI confidence needed to apply corrections.
        requests_per_minute: Rate limit for API requests.
        retry_attempts: Number of retry attempts for failed requests.
    """

    enabled: bool = False
    api_key_env: str = "ANTHROPIC_API_KEY"
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 150
    budget_limit: float = 5.00
    require_confirmation: bool = True
    validation_threshold: float = 0.7
    correction_threshold: float = 0.9
    requests_per_minute: int = 20
    retry_attempts: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AICategorizationConfig":
        """Create from dictionary with type safety and range validation."""
        budget_data = data.get("budget", {})
        rate_limit_data = data.get("rate_limit", {})
        validation_data = data.get("validation", {})

        # Parse max_tokens with type safety
        raw_max_tokens = data.get("max_tokens", 150)
        if isinstance(raw_max_tokens, (int, str, float)):
            try:
                max_tokens = int(raw_max_tokens)
            except (ValueError, TypeError):
                max_tokens = 150
        else:
            max_tokens = 150

        # Parse budget_limit with range validation (no negative budgets)
        try:
            raw_budget = budget_data.get("max_cost_per_run", 5.00) if isinstance(budget_data, dict) else 5.00
            budget_limit = max(0.0, float(raw_budget))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            budget_limit = 5.00

        # Parse validation_threshold with range validation (clamp to 0-1)
        try:
            if isinstance(validation_data, dict):
                raw_val_thresh = validation_data.get("confidence_threshold", 0.7)
            else:
                raw_val_thresh = 0.7
            validation_threshold = max(0.0, min(1.0, float(raw_val_thresh)))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            validation_threshold = 0.7

        # Parse correction_threshold with range validation (clamp to 0-1)
        try:
            if isinstance(validation_data, dict):
                raw_corr_thresh = validation_data.get("correction_threshold", 0.9)
            else:
                raw_corr_thresh = 0.9
            correction_threshold = max(0.0, min(1.0, float(raw_corr_thresh)))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            correction_threshold = 0.9

        # Parse requests_per_minute with range validation (at least 1 RPM)
        try:
            raw_rpm = rate_limit_data.get("requests_per_minute", 20) if isinstance(rate_limit_data, dict) else 20
            requests_per_minute = max(1, int(raw_rpm))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            requests_per_minute = 20

        # Parse retry_attempts with range validation (no negative retries)
        try:
            raw_retries = rate_limit_data.get("retry_attempts", 3) if isinstance(rate_limit_data, dict) else 3
            retry_attempts = max(0, int(raw_retries))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            retry_attempts = 3

        return cls(
            enabled=bool(data.get("enabled", False)),
            api_key_env=str(data.get("api_key_env", "ANTHROPIC_API_KEY")),
            model=str(data.get("model", "claude-sonnet-4-5-20250929")),
            max_tokens=max_tokens,
            budget_limit=budget_limit,
            require_confirmation=bool(
                budget_data.get("require_confirmation", True) if isinstance(budget_data, dict) else True
            ),
            validation_threshold=validation_threshold,
            correction_threshold=correction_threshold,
            requests_per_minute=requests_per_minute,
            retry_attempts=retry_attempts,
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
        corrections: Dictionary of fingerprint to CategoryCorrection.
        anomaly: Anomaly detection configuration.
        output: Output generation configuration.
        logging: Logging configuration.
        ai: AI categorization configuration.
        start_date: Start date for filtering transactions.
        end_date: End date for filtering transactions.
    """

    accounts: dict[str, Account] = field(default_factory=dict)
    file_mappings: dict[str, str] = field(default_factory=dict)
    categories: dict[str, Category] = field(default_factory=dict)
    category_rules: list[CategoryRule] = field(default_factory=list)
    manual_overrides: list[ManualOverride] = field(default_factory=list)
    corrections: dict[str, CategoryCorrection] = field(default_factory=dict)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ai: AICategorizationConfig = field(default_factory=AICategorizationConfig)
    start_date: date | None = None
    end_date: date | None = None

    def get_account_for_file(self, filename: str) -> Account | None:
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

    def get_matching_override(
        self,
        transaction_date: str,
        amount: Decimal,
        description: str,
    ) -> ManualOverride | None:
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

    def get_matching_correction(self, fingerprint: str) -> CategoryCorrection | None:
        """Find a correction matching the transaction fingerprint.

        Args:
            fingerprint: Transaction fingerprint (16-char hex hash).

        Returns:
            Matching correction, or None.
        """
        return self.corrections.get(fingerprint)

    def get_category_id_by_name(self, name: str | None) -> str | None:
        """Find a category ID by its display name (case-insensitive).

        Args:
            name: Category display name to look up.

        Returns:
            Category ID if found, None otherwise.
        """
        if not name:
            return None
        name_lower = name.lower().strip()
        for category_id, category in self.categories.items():
            if category.name.lower() == name_lower:
                return category_id
        return None

    def get_category_name_by_id(self, category_id: str) -> str | None:
        """Find a category display name by its ID.

        Args:
            category_id: Category ID to look up.

        Returns:
            Category name if found, None otherwise.
        """
        category = self.categories.get(category_id)
        return category.name if category else None


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

    return cast(dict[str, object], content) if content else {}


def load_settings(
    path: Path,
) -> tuple[AnomalyConfig, OutputConfig, LoggingConfig, AICategorizationConfig]:
    """Load settings from settings.yaml.

    Args:
        path: Path to settings.yaml.

    Returns:
        Tuple of (AnomalyConfig, OutputConfig, LoggingConfig, AICategorizationConfig).
    """
    data = load_yaml_file(path)

    anomaly = AnomalyConfig()
    if "anomaly_detection" in data:
        anomaly_data = data["anomaly_detection"]
        if isinstance(anomaly_data, dict):
            anomaly = AnomalyConfig.from_dict(anomaly_data)
        else:
            logger.warning(f"anomaly_detection must be a dict, got {type(anomaly_data).__name__}")

    output = OutputConfig()
    if "output" in data:
        output_data = data["output"]
        if isinstance(output_data, dict):
            output = OutputConfig.from_dict(output_data)
        else:
            logger.warning(f"output must be a dict, got {type(output_data).__name__}")

    logging_config = LoggingConfig()
    if "logging" in data:
        logging_data = data["logging"]
        if isinstance(logging_data, dict):
            logging_config = LoggingConfig.from_dict(logging_data)
        else:
            logger.warning(f"logging must be a dict, got {type(logging_data).__name__}")

    ai_config = AICategorizationConfig()
    if "ai_categorization" in data:
        ai_data = data["ai_categorization"]
        if isinstance(ai_data, dict):
            ai_config = AICategorizationConfig.from_dict(ai_data)
        else:
            logger.warning(f"ai_categorization must be a dict, got {type(ai_data).__name__}")

    return anomaly, output, logging_config, ai_config


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
    raw_mappings = data.get("file_mappings")
    if isinstance(raw_mappings, dict):
        file_mappings = {str(k): str(v) for k, v in raw_mappings.items()}

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
    # Track names to detect duplicates (case-insensitive)
    name_to_ids: dict[str, list[str]] = {}

    if "categories" in data and data["categories"] is not None:
        cat_list = data["categories"]
        if not isinstance(cat_list, list):
            raise ConfigError(f"'categories' must be a list, got {type(cat_list).__name__}")
        for cat_data in cat_list:
            category = Category.from_dict(cat_data)
            categories[category.id] = category
            # Track category name (case-insensitive) for duplicate detection
            name_lower = category.name.lower()
            if name_lower not in name_to_ids:
                name_to_ids[name_lower] = []
            name_to_ids[name_lower].append(category.id)

    # Warn about duplicate category names (affects correction import)
    # Note: get_category_id_by_name() iterates self.categories which preserves
    # insertion order (Python 3.7+), so it returns the first defined category.
    for name_lower, ids in name_to_ids.items():
        if len(ids) > 1:
            logger.warning(
                f"Duplicate category name '{categories[ids[0]].name}' has multiple IDs: "
                f"{', '.join(ids)}. Name lookups will return '{ids[0]}' "
                "(first in categories.yaml). Consider renaming to avoid ambiguity."
            )

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


def load_corrections(path: Path) -> dict[str, CategoryCorrection]:
    """Load category corrections from corrections.yaml.

    Args:
        path: Path to corrections.yaml.

    Returns:
        Dictionary of fingerprint to CategoryCorrection.
    """
    if not path.exists():
        return {}

    data = load_yaml_file(path)

    corrections: dict[str, CategoryCorrection] = {}
    if "corrections" in data and data["corrections"] is not None:
        correction_list = data["corrections"]
        if not isinstance(correction_list, list):
            raise ConfigError(f"'corrections' must be a list, got {type(correction_list).__name__}")
        for correction_data in correction_list:
            correction = CategoryCorrection.from_dict(correction_data)
            corrections[correction.fingerprint] = correction

    return corrections


def save_corrections(path: Path, corrections: dict[str, CategoryCorrection]) -> None:
    """Save category corrections to corrections.yaml.

    Uses atomic write (temp file + rename) to prevent corruption if YAML
    serialization fails partway through.

    Args:
        path: Path to save corrections.yaml.
        corrections: Dictionary of fingerprint to CategoryCorrection.

    Raises:
        OSError: If file cannot be written.
        yaml.YAMLError: If corrections cannot be serialized (should not happen
            with well-formed CategoryCorrection objects).
    """
    import os
    import tempfile

    data: dict[str, object] = {
        "corrections": [corr.to_dict() for corr in corrections.values()]
    }

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: serialize to temp file first, then rename
    # This prevents corruption if yaml.dump fails or process is interrupted
    temp_fd, temp_path = tempfile.mkstemp(
        dir=path.parent, prefix=".corrections_", suffix=".yaml"
    )
    fd_owned = False  # Track if fd has been handed to file object
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            fd_owned = True  # os.fdopen now owns the fd
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        # Atomic rename (on POSIX systems)
        Path(temp_path).replace(path)
        temp_path = None  # Mark as successfully renamed
    finally:
        # Close fd if os.fdopen() failed before taking ownership
        if not fd_owned:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        # Clean up temp file if rename didn't happen
        if temp_path:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass  # Best effort cleanup

    logger.info(f"Saved {len(corrections)} corrections to {path}")


def load_config(
    settings_path: Path | None = None,
    accounts_path: Path | None = None,
    categories_path: Path | None = None,
    manual_overrides_path: Path | None = None,
    corrections_path: Path | None = None,
    config_dir: Path | None = None,
) -> Config:
    """Load complete configuration from all config files.

    Args:
        settings_path: Path to settings.yaml (or None to use default).
        accounts_path: Path to accounts.yaml (or None to use default).
        categories_path: Path to categories.yaml (or None to use default).
        manual_overrides_path: Path to manual_categories.yaml (or None to use default).
        corrections_path: Path to corrections.yaml (or None to use default).
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
    if corrections_path is None:
        corrections_path = config_dir / "corrections.yaml"

    config = Config()

    # Load settings (optional - use defaults if missing)
    if settings_path.exists():
        config.anomaly, config.output, config.logging, config.ai = load_settings(
            settings_path
        )
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

    # Load corrections (optional)
    config.corrections = load_corrections(corrections_path)
    if config.corrections:
        logger.info(f"Loaded {len(config.corrections)} category corrections")

    return config


def save_accounts(path: Path, config: Config) -> None:
    """Save accounts and file mappings to accounts.yaml.

    Uses atomic write (temp file + rename) to prevent corruption if
    the process is interrupted during YAML serialization.

    This is used to persist interactive account mappings.

    Args:
        path: Path to save accounts.yaml.
        config: Config object with accounts and mappings.

    Raises:
        OSError: If file cannot be written.
    """
    import os
    import tempfile
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
        # Write balance fields:
        # - None = auto-detect from transactions (field not saved, becomes None on reload)
        # - Decimal value (including 0) = explicit balance (always saved to preserve user intent)
        if account.opening_balance is not None:
            accounts_dict[account.id]["opening_balance"] = str(account.opening_balance)
            if account.opening_balance_date is not None:
                accounts_dict[account.id]["opening_balance_date"] = account.opening_balance_date.isoformat()
        if account.source_file_patterns:
            accounts_dict[account.id]["source_file_patterns"] = account.source_file_patterns
        if account.display_order:
            accounts_dict[account.id]["display_order"] = account.display_order

    data["accounts"] = accounts_dict

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: serialize to temp file first, then rename
    # This prevents corruption if yaml.dump fails or process is interrupted
    temp_fd, temp_path = tempfile.mkstemp(
        dir=path.parent, prefix=".accounts_", suffix=".yaml"
    )
    fd_owned = False  # Track if fd has been handed to file object
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            fd_owned = True  # os.fdopen now owns the fd
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        # Atomic rename (on POSIX systems)
        Path(temp_path).replace(path)
        temp_path = None  # Mark as successfully renamed
    finally:
        # Close fd if os.fdopen() failed before taking ownership
        if not fd_owned:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        # Clean up temp file if rename didn't happen
        if temp_path:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass  # Best effort cleanup

    logger.info(f"Saved accounts configuration to {path}")


def save_categories(path: Path, config: Config) -> None:
    """Save categories and rules to categories.yaml.

    Uses atomic write (temp file + rename) to prevent corruption if
    the process is interrupted during YAML serialization.

    This is used to persist new categories created during correction import.

    Args:
        path: Path to save categories.yaml.
        config: Config object with categories and rules.

    Raises:
        OSError: If file cannot be written.
    """
    import os
    import tempfile

    # Build categories list
    categories_list: list[dict[str, object]] = []
    for category in config.categories.values():
        cat_dict: dict[str, object] = {
            "id": category.id,
            "name": category.name,
            "type": category.category_type.value,
        }
        if category.parent_id:
            cat_dict["parent"] = category.parent_id
        if category.display_order:
            cat_dict["display_order"] = category.display_order
        if category.color:
            cat_dict["color"] = category.color
        categories_list.append(cat_dict)

    # Build rules list
    rules_list: list[dict[str, object]] = []
    for rule in config.category_rules:
        rule_dict: dict[str, object] = {
            "id": rule.id,
            "category": rule.category_id,
        }
        if rule.subcategory_id:
            rule_dict["subcategory"] = rule.subcategory_id
        if rule.keywords:
            rule_dict["keywords"] = rule.keywords
        if rule.regex_patterns:
            rule_dict["regex_patterns"] = rule.regex_patterns
        if rule.amount_min is not None:
            rule_dict["amount_min"] = str(rule.amount_min)
        if rule.amount_max is not None:
            rule_dict["amount_max"] = str(rule.amount_max)
        if rule.account_ids:
            rule_dict["account_ids"] = rule.account_ids
        if rule.priority:
            rule_dict["priority"] = rule.priority
        if not rule.is_active:
            rule_dict["is_active"] = False
        if rule.match_mode != MatchMode.SUBSTRING:
            rule_dict["match_mode"] = rule.match_mode.value
        rules_list.append(rule_dict)

    data: dict[str, object] = {
        "categories": categories_list,
        "rules": rules_list,
    }

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: serialize to temp file first, then rename
    # This prevents corruption if yaml.dump fails or process is interrupted
    temp_fd, temp_path = tempfile.mkstemp(
        dir=path.parent, prefix=".categories_", suffix=".yaml"
    )
    fd_owned = False  # Track if fd has been handed to file object
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            fd_owned = True  # os.fdopen now owns the fd
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        # Atomic rename (on POSIX systems)
        Path(temp_path).replace(path)
        temp_path = None  # Mark as successfully renamed
    finally:
        # Close fd if os.fdopen() failed before taking ownership
        if not fd_owned:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        # Clean up temp file if rename didn't happen
        if temp_path:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass  # Best effort cleanup

    logger.info(f"Saved {len(config.categories)} categories and {len(config.category_rules)} rules to {path}")

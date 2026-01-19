"""Category and categorization rule data models."""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MatchResult:
    """Result of a categorization rule match with confidence scoring.

    Attributes:
        matched: Whether the rule matched the transaction.
        confidence: Confidence score from 0.0 to 1.0.
        matched_by: Type of match ("keyword", "regex", "amount", "account").
        matched_value: The specific keyword or pattern that matched.
        factors: List of explanations for the confidence calculation.
    """

    matched: bool
    confidence: float
    matched_by: str
    matched_value: str
    factors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


# Maximum pattern length to prevent overly complex patterns
MAX_PATTERN_LENGTH = 500

# Patterns that can cause catastrophic backtracking (ReDoS)
# These are checked via substring matching for known dangerous patterns
DANGEROUS_PATTERN_SIGNATURES = [
    r'(\w+)+',   # Nested quantifiers on word chars
    r'(.*)*',    # Nested quantifiers on any chars
    r'(.+)+',    # Nested quantifiers on one-or-more
    r'([^"]+)+', # Nested quantifiers on negated char class
    r'(\s+)+',   # Nested quantifiers on whitespace
]

# Regex to detect nested quantifiers dynamically (catches (a+)+, ([a-z]+)+, etc.)
# Matches: group with quantifier inside, followed by outer quantifier
# Also catches {n,m} bounded quantifiers like (a+){2,}
_NESTED_QUANTIFIER_PATTERN = re.compile(
    r'\([^)]*[+*?][^)]*\)[+*?]|'        # Nested +, *, ? quantifiers
    r'\([^)]*[+*?][^)]*\)\{[0-9,]+\}'   # Nested with {n,m} bounded quantifier
)


def _is_safe_pattern(pattern: str) -> tuple[bool, str]:
    """Check if regex pattern is safe from ReDoS attacks.

    Args:
        pattern: Regex pattern string to validate.

    Returns:
        Tuple of (is_safe, reason if unsafe).
    """
    if len(pattern) > MAX_PATTERN_LENGTH:
        return False, f"Pattern exceeds {MAX_PATTERN_LENGTH} character limit"

    # Check for nested quantifiers using regex-based detection
    if _NESTED_QUANTIFIER_PATTERN.search(pattern):
        return False, "Pattern contains dangerous nested quantifier"

    # Also check for known dangerous pattern signatures
    for dangerous in DANGEROUS_PATTERN_SIGNATURES:
        if dangerous in pattern:
            return False, "Pattern contains known dangerous signature"

    return True, ""


class CategoryType(Enum):
    """Type of category for P&L classification."""

    INCOME = "income"  # Included in P&L income section
    EXPENSE = "expense"  # Included in P&L expense section
    TRANSFER = "transfer"  # Excluded from P&L totals (shown in memo section)


class MatchMode(Enum):
    """Matching mode for keywords in categorization rules."""

    SUBSTRING = "substring"  # Default: "SHELL" matches "SHELLPOINT"
    WORD_BOUNDARY = "word"  # "SHELL" only matches as whole word


@dataclass
class Category:
    """Category definition with hierarchy support.

    Attributes:
        id: Unique identifier for this category.
        name: Human-readable category name.
        category_type: Type for P&L classification (income, expense, transfer).
        parent_id: Parent category ID for subcategories.
        display_order: Order for displaying in outputs.
        color: Optional color code for Excel formatting (e.g., "#4CAF50").
    """

    id: str
    name: str
    category_type: CategoryType
    parent_id: str | None = None
    display_order: int = 0
    color: str | None = None

    @property
    def is_subcategory(self) -> bool:
        """Check if this is a subcategory."""
        return self.parent_id is not None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Category":
        """Create a Category from a dictionary (e.g., from YAML config).

        Args:
            data: Dictionary containing category data.

        Returns:
            A new Category instance.
        """
        type_str = str(data.get("type", "expense"))
        try:
            category_type = CategoryType(type_str)
        except ValueError:
            category_type = CategoryType.EXPENSE

        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            category_type=category_type,
            parent_id=str(data["parent"]) if "parent" in data else None,
            display_order=int(data.get("display_order", 0)),  # type: ignore[arg-type]
            color=str(data["color"]) if "color" in data else None,
        )

    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, name={self.name!r}, type={self.category_type.value})"


@dataclass
class CategoryRule:
    """Rule for automatic transaction categorization.

    Keyword matching is case-insensitive and can use substring or word-boundary mode.

    Attributes:
        id: Unique identifier for this rule.
        category_id: Category to assign when rule matches.
        subcategory_id: Optional subcategory to assign.
        keywords: List of keywords for case-insensitive matching.
        regex_patterns: List of regex patterns to match description.
        amount_min: Minimum amount for rule to apply.
        amount_max: Maximum amount for rule to apply.
        account_ids: List of account IDs this rule applies to (empty = all accounts).
        priority: Rule priority (higher = evaluated first).
        is_active: Whether this rule is active.
        match_mode: How keywords are matched (substring or word boundary).
    """

    id: str
    category_id: str
    subcategory_id: str | None = None

    # Matching criteria
    keywords: list[str] = field(default_factory=list)
    regex_patterns: list[str] = field(default_factory=list)
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    account_ids: list[str] = field(default_factory=list)

    # Rule settings
    priority: int = 0
    is_active: bool = True
    match_mode: MatchMode = MatchMode.SUBSTRING

    # Compiled regex patterns (cached)
    _compiled_patterns: list[re.Pattern[str]] = field(
        default_factory=list, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        """Compile regex patterns for efficiency."""
        self._compiled_patterns = []
        for pattern in self.regex_patterns:
            # Check for ReDoS vulnerability
            is_safe, reason = _is_safe_pattern(pattern)
            if not is_safe:
                logger.warning(
                    f"Rejecting unsafe regex pattern '{pattern}' in rule '{self.id}': {reason}"
                )
                continue
            try:
                self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(
                    f"Invalid regex pattern '{pattern}' in rule '{self.id}': {e}"
                )

        # Warn about rule matching behavior based on criteria
        has_matching_criteria = (
            self.keywords
            or self._compiled_patterns
            or self.amount_min is not None
            or self.amount_max is not None
            or self.account_ids
        )
        if not has_matching_criteria:
            if self.regex_patterns:
                # User specified regex patterns but all were rejected/invalid
                logger.warning(
                    f"Rule '{self.id}' has no valid matching criteria (all regex patterns "
                    f"were rejected) and will match nothing"
                )
            else:
                # No criteria specified at all
                logger.warning(
                    f"Rule '{self.id}' has no matching criteria and will match all transactions"
                )

    def matches(
        self,
        description: str,
        amount: Decimal,
        account_id: str,
    ) -> MatchResult | None:
        """Check if a transaction matches this rule and return match details.

        Args:
            description: Transaction description.
            amount: Transaction amount (can be negative for debits).
            account_id: Account ID of the transaction.

        Returns:
            MatchResult with confidence scoring if matched, None if no match.
            Rules match when:
            - Account filter matches (if specified)
            - Amount (absolute value) is within range (if specified)
            - At least one keyword matches OR at least one regex matches
              (if both are specified, only one needs to match)

        Confidence scoring:
            - Regex with ^ prefix (anchored): 0.92-1.00
            - Regex pattern: 0.85-0.98
            - Word boundary keyword: 0.77-0.95
            - Substring keyword: 0.70-0.88
            - Amount-only or account-only match: 0.50-0.70
        """
        if not self.is_active:
            return None

        # Check account filter
        if self.account_ids and account_id not in self.account_ids:
            return None

        # Use absolute value for amount comparisons (amounts can be negative for debits)
        abs_amount = abs(amount)

        # Check amount range
        if self.amount_min is not None and abs_amount < self.amount_min:
            return None
        if self.amount_max is not None and abs_amount > self.amount_max:
            return None

        # Track what matched for confidence calculation
        matched_keyword: str | None = None
        matched_pattern: str | None = None
        match_mode_used: str | None = None
        confidence_factors: list[str] = []

        # Check keywords based on match mode
        description_lower = description.lower()
        keyword_match = False
        if self.keywords:
            for keyword in self.keywords:
                kw_lower = keyword.lower()
                if self.match_mode == MatchMode.WORD_BOUNDARY:
                    # Use regex word boundary for whole-word matching
                    pattern = r'\b' + re.escape(kw_lower) + r'\b'
                    if re.search(pattern, description_lower):
                        keyword_match = True
                        matched_keyword = keyword
                        match_mode_used = "word_boundary"
                        break
                else:
                    # Default substring match
                    if kw_lower in description_lower:
                        keyword_match = True
                        matched_keyword = keyword
                        match_mode_used = "substring"
                        break
        else:
            # No keywords specified, consider it a match for keyword criteria
            keyword_match = True

        # Check regex patterns
        # Note: We distinguish between "no patterns specified" and
        # "patterns specified but all rejected"
        regex_match = False
        if self._compiled_patterns:
            for i, pattern in enumerate(self._compiled_patterns):
                if pattern.search(description):
                    regex_match = True
                    if i < len(self.regex_patterns):
                        matched_pattern = self.regex_patterns[i]
                    else:
                        matched_pattern = str(pattern.pattern)
                    break
        elif not self.regex_patterns:
            # No regex patterns were specified at all - don't filter by regex
            regex_match = True
        # else: patterns were specified but rejected/invalid - regex_match stays False

        # Determine if we have a match
        has_match = False
        if self.keywords and self.regex_patterns:
            has_match = keyword_match or regex_match
        elif self.keywords:
            has_match = keyword_match
        elif self.regex_patterns:
            has_match = regex_match
        else:
            # No keywords or regex specified - match based on amount/account only
            has_match = True

        if not has_match:
            return None

        # Calculate confidence score based on match type
        confidence = self._calculate_confidence(
            matched_keyword=matched_keyword,
            matched_pattern=matched_pattern,
            match_mode_used=match_mode_used,
            description=description,
            confidence_factors=confidence_factors,
        )

        # Determine matched_by and matched_value
        if matched_pattern:
            matched_by = "regex"
            matched_value = matched_pattern
        elif matched_keyword:
            matched_by = "keyword"
            matched_value = matched_keyword
        else:
            matched_by = "filter"
            matched_value = "amount/account filter"

        return MatchResult(
            matched=True,
            confidence=confidence,
            matched_by=matched_by,
            matched_value=matched_value,
            factors=confidence_factors,
        )

    def _calculate_confidence(
        self,
        matched_keyword: str | None,
        matched_pattern: str | None,
        match_mode_used: str | None,
        description: str,
        confidence_factors: list[str],
    ) -> float:
        """Calculate confidence score based on match characteristics.

        Args:
            matched_keyword: The keyword that matched (if any).
            matched_pattern: The regex pattern that matched (if any).
            match_mode_used: The match mode used ("word_boundary" or "substring").
            description: The transaction description.
            confidence_factors: List to append explanation factors to.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        base_confidence = 0.50

        if matched_pattern:
            # Regex match - check if anchored
            if matched_pattern.startswith('^'):
                # Anchored regex (very specific)
                base_confidence = 0.92
                confidence_factors.append(f"Anchored regex match: {matched_pattern}")
                # Bonus for longer patterns (more specific)
                pattern_len = len(matched_pattern)
                if pattern_len > 10:
                    base_confidence = min(1.0, base_confidence + 0.04)
                    confidence_factors.append(f"Long pattern ({pattern_len} chars)")
                if pattern_len > 20:
                    base_confidence = min(1.0, base_confidence + 0.04)
            else:
                # Non-anchored regex
                base_confidence = 0.85
                confidence_factors.append(f"Regex pattern match: {matched_pattern}")
                # Bonus for specific patterns
                if '\\b' in matched_pattern:
                    base_confidence = min(0.98, base_confidence + 0.05)
                    confidence_factors.append("Word boundary in pattern")

        elif matched_keyword:
            description_lower = description.lower()
            kw_lower = matched_keyword.lower()

            if match_mode_used == "word_boundary":
                # Word boundary match
                base_confidence = 0.77
                confidence_factors.append(f"Word boundary keyword: {matched_keyword}")

                # Bonus for exact match at start
                if description_lower.startswith(kw_lower):
                    base_confidence = min(0.95, base_confidence + 0.10)
                    confidence_factors.append("Keyword at description start")

                # Bonus for longer keywords (more specific)
                if len(matched_keyword) > 8:
                    base_confidence = min(0.95, base_confidence + 0.05)
                    confidence_factors.append(f"Long keyword ({len(matched_keyword)} chars)")

            else:
                # Substring match (less specific)
                base_confidence = 0.70
                confidence_factors.append(f"Substring keyword: {matched_keyword}")

                # Bonus for exact match at start
                if description_lower.startswith(kw_lower):
                    base_confidence = min(0.88, base_confidence + 0.10)
                    confidence_factors.append("Keyword at description start")

                # Bonus for longer keywords
                if len(matched_keyword) > 10:
                    base_confidence = min(0.88, base_confidence + 0.05)
                    confidence_factors.append(f"Long keyword ({len(matched_keyword)} chars)")

        else:
            # Amount/account filter only (low confidence)
            base_confidence = 0.50
            confidence_factors.append("Matched by amount/account filter only")

            # Slightly increase confidence for specific amount ranges
            if self.amount_min is not None and self.amount_max is not None:
                range_size = float(self.amount_max - self.amount_min)
                if 0 < range_size < 100:
                    base_confidence = min(0.70, base_confidence + 0.15)
                    min_amt = self.amount_min
                    max_amt = self.amount_max
                    confidence_factors.append(f"Narrow amount range: ${min_amt}-${max_amt}")

        # Apply priority bonus (higher priority rules are more trusted)
        if self.priority > 50:
            priority_bonus = min(0.05, (self.priority - 50) / 1000)
            base_confidence = min(1.0, base_confidence + priority_bonus)
            confidence_factors.append(f"High priority rule: {self.priority}")

        return round(base_confidence, 3)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CategoryRule":
        """Create a CategoryRule from a dictionary (e.g., from YAML config).

        Args:
            data: Dictionary containing rule data.

        Returns:
            A new CategoryRule instance.
        """
        amount_min = None
        if "amount_min" in data:
            amount_min = Decimal(str(data["amount_min"]))

        amount_max = None
        if "amount_max" in data:
            amount_max = Decimal(str(data["amount_max"]))

        # Parse match_mode (defaults to substring)
        match_mode = MatchMode.SUBSTRING
        if "match_mode" in data:
            mode_str = str(data["match_mode"]).lower()
            if mode_str == "word":
                match_mode = MatchMode.WORD_BOUNDARY

        return cls(
            id=str(data["id"]),
            category_id=str(data["category"]),
            subcategory_id=str(data["subcategory"]) if "subcategory" in data else None,
            keywords=list(data.get("keywords", [])),  # type: ignore[arg-type]
            regex_patterns=list(data.get("regex_patterns", [])),  # type: ignore[arg-type]
            amount_min=amount_min,
            amount_max=amount_max,
            account_ids=list(data.get("account_ids", [])),  # type: ignore[arg-type]
            priority=int(data.get("priority", 0)),  # type: ignore[arg-type]
            is_active=bool(data.get("is_active", True)),
            match_mode=match_mode,
        )

    def __repr__(self) -> str:
        return (
            f"CategoryRule(id={self.id!r}, category={self.category_id!r}, "
            f"priority={self.priority})"
        )


@dataclass
class ManualOverride:
    """Manual category override for specific transactions.

    Match logic: A transaction matches when ALL specified criteria match:
    - date: exact match (required)
    - amount: exact match (required)
    - keywords: at least one keyword matches description (case-insensitive substring)

    Attributes:
        date_str: Transaction date to match (YYYY-MM-DD format).
        amount: Transaction amount to match exactly.
        keywords: Keywords for description matching.
        category_id: Category to assign.
        subcategory_id: Optional subcategory to assign.
        priority: Override priority (higher wins).
    """

    date_str: str
    amount: Decimal
    keywords: list[str]
    category_id: str
    subcategory_id: str | None = None
    priority: int = 0

    def matches(self, transaction_date: str, transaction_amount: Decimal, description: str) -> bool:
        """Check if a transaction matches this override.

        Args:
            transaction_date: Transaction date in YYYY-MM-DD format.
            transaction_amount: Transaction amount.
            description: Transaction description.

        Returns:
            True if all criteria match.
        """
        # Exact date match
        if transaction_date != self.date_str:
            return False

        # Exact amount match
        if transaction_amount != self.amount:
            return False

        # At least one keyword must match (case-insensitive substring)
        if self.keywords:
            description_lower = description.lower()
            for keyword in self.keywords:
                if keyword.lower() in description_lower:
                    return True
            return False

        # No keywords specified, match on date and amount only
        return True

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ManualOverride":
        """Create a ManualOverride from a dictionary.

        Args:
            data: Dictionary containing override data.

        Returns:
            A new ManualOverride instance.
        """
        return cls(
            date_str=str(data["date"]),
            amount=Decimal(str(data["amount"])),
            keywords=list(data.get("keywords", [])),  # type: ignore[arg-type]
            category_id=str(data["category"]),
            subcategory_id=str(data["subcategory"]) if "subcategory" in data else None,
            priority=int(data.get("priority", 0)),  # type: ignore[arg-type]
        )

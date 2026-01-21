"""Prompt templates for AI categorization."""

# System prompt for categorization tasks
CATEGORIZATION_SYSTEM_PROMPT = """You are a financial transaction categorizer. \
Your job is to analyze transaction descriptions and assign them to the most \
appropriate category.

Guidelines:
1. Base your categorization on the merchant name, transaction description, and amount
2. Consider common merchant patterns (e.g., "SQ *" = Square point-of-sale)
3. Be conservative - if uncertain, express lower confidence
4. Common patterns:
   - "SQ *", "SQUARE *", "TST*", "CLOVER*" = point-of-sale terminals, categorize by merchant name
   - "PAYPAL *" = online payment, categorize by the merchant after PAYPAL
   - "ZELLE", "VENMO" = peer-to-peer transfers
   - Numbers at the end often indicate store/location IDs

Response format: Raw JSON only - no markdown code blocks, no explanation outside the JSON."""


def build_categorization_prompt(
    description: str,
    amount: float,
    account_name: str,
    categories: list[dict[str, str]],
) -> str:
    """Build a categorization prompt for a single transaction.

    Args:
        description: Transaction description.
        amount: Transaction amount (negative for expenses).
        account_name: Name of the account.
        categories: List of category dicts with 'id' and 'name' keys.

    Returns:
        Formatted prompt string.
    """
    # Format categories as a list
    category_list = "\n".join(
        f"- {cat['id']}: {cat['name']}" for cat in categories
    )

    return f"""Categorize this transaction into ONE of these categories:

{category_list}

Transaction:
- Description: {description}
- Amount: ${abs(amount):.2f} ({'expense' if amount < 0 else 'income/credit'})
- Account: {account_name}

Respond with JSON only:
{{"category_id": "...", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""


# System prompt for validation tasks
VALIDATION_SYSTEM_PROMPT = """You are validating a transaction categorization \
made by a rule-based system. Assess whether the assigned category is correct.

Guidelines:
1. Consider the transaction description and the assigned category
2. If the categorization is clearly correct, validate it
3. If clearly wrong, suggest the correct category
4. If ambiguous, express uncertainty
5. Be conservative about suggesting corrections - the original system may have context you don't

Response format: Raw JSON only - no markdown code blocks, no explanation outside the JSON."""


def build_validation_prompt(
    description: str,
    amount: float,
    current_category: str,
    current_category_name: str,
    categories: list[dict[str, str]],
) -> str:
    """Build a validation prompt for a categorized transaction.

    Args:
        description: Transaction description.
        amount: Transaction amount.
        current_category: Currently assigned category ID.
        current_category_name: Display name of current category.
        categories: List of available category dicts.

    Returns:
        Formatted prompt string.
    """
    category_list = "\n".join(
        f"- {cat['id']}: {cat['name']}" for cat in categories
    )

    return f"""Validate this categorization:

Transaction:
- Description: {description}
- Amount: ${abs(amount):.2f}
- Current Category: {current_category_name} (id: {current_category})

Available categories:
{category_list}

Is this categorization correct? Respond with JSON only:
{{"validated": true/false, "suggested_category_id": "...", "confidence": 0.0-1.0, \
"reasoning": "brief explanation"}}

If validated is true, suggested_category_id should match the current category."""


def build_batch_categorization_prompt(
    transactions: list[dict[str, object]],
    categories: list[dict[str, str]],
) -> str:
    """Build a prompt for batch categorization.

    Args:
        transactions: List of transaction dicts with description, amount, account.
        categories: List of available category dicts.

    Returns:
        Formatted prompt string.
    """
    category_list = "\n".join(
        f"- {cat['id']}: {cat['name']}" for cat in categories
    )

    txn_list = "\n".join(
        f"{i+1}. \"{t['description']}\" | ${abs(float(str(t['amount']))):.2f} | {t['account']}"
        for i, t in enumerate(transactions)
    )

    return f"""Categorize each transaction into ONE of these categories:

{category_list}

Transactions:
{txn_list}

Respond with a JSON array, one entry per transaction:
[{{"index": 1, "category_id": "...", "confidence": 0.0-1.0, "reasoning": "brief"}}]"""

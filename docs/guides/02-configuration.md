# Configuration Guide

The Financial Consolidator uses YAML configuration files to customize behavior, define accounts, and manage categorization rules.

## Configuration Directory Structure

```
config/
├── settings.yaml      # Global application settings
├── accounts.yaml      # Account definitions and file mappings
├── categories.yaml    # Category hierarchy and rules
└── corrections.yaml   # User corrections (auto-managed)
```

## Overriding Config Paths

You can override the default config directory or individual files:

```bash
# Use a different config directory
financial-consolidator -i ./statements --config-dir /path/to/config

# Override specific config files
financial-consolidator -i ./statements \
  --config /path/to/settings.yaml \
  --accounts /path/to/accounts.yaml \
  --categories /path/to/categories.yaml
```

---

## settings.yaml

Global application settings controlling behavior, thresholds, and AI configuration.

### Key Sections

```yaml
# Date range defaults
date_range:
  start: null        # null = no start limit
  end: null          # null = no end limit

# Large transaction alerts
thresholds:
  large_transaction: 5000.00  # Flag transactions over this amount

# AI categorization settings
ai:
  enabled: false
  api_key_env: ANTHROPIC_API_KEY  # Environment variable name
  budget: 5.00                     # Max spend per run in USD
  confidence_threshold: 0.7        # Minimum confidence for auto-accept
  model: claude-sonnet-4-20250514  # Model to use
```

### CLI Overrides

```bash
# Override large transaction threshold
financial-consolidator -i ./statements --large-transaction-threshold 10000

# Override date range
financial-consolidator -i ./statements --start-date 2025-01-01 --end-date 2025-06-30
```

---

## accounts.yaml

Defines your financial accounts and maps CSV files to them.

### Account Structure

```yaml
accounts:
  chase_checking:                    # Account ID (unique identifier)
    name: Chase Checking ****1234    # Display name
    type: checking                   # Account type
    institution: Chase               # Institution name (optional)
    opening_balance: "5234.56"       # Starting balance (optional)
    opening_balance_date: "2024-01-01"
    file_mappings:                   # CSV files that belong to this account
      - pattern: "Chase*Activity*.csv"
        parser: chase
```

### Account Types

| Type | Description |
|------|-------------|
| `checking` | Checking accounts |
| `savings` | Savings accounts |
| `credit_card` | Credit cards |
| `loan` | Loans and mortgages |
| `investment` | Investment accounts |
| `crypto` | Cryptocurrency accounts |

### File Mappings

File mappings tell the tool which CSV files belong to which account:

```yaml
file_mappings:
  - pattern: "Chase*Activity*.csv"  # Glob pattern to match files
    parser: chase                   # Parser to use (auto-detected if omitted)
```

**Supported parsers:** `chase`, `amex`, `capital_one`, `citi`, `generic`, and more.

### Opening Balance

See [Account Management](04-account-management.md) for details on setting opening balances.

---

## categories.yaml

Defines the category hierarchy and automatic categorization rules.

### Category Structure

```yaml
categories:
  dining:
    name: Dining
    type: expense
    display_order: 10

  fast_food:
    name: Fast Food
    type: expense
    parent_id: dining     # Subcategory of dining
    display_order: 11

  income_salary:
    name: Salary
    type: income
    display_order: 1

  transfers:
    name: Transfers
    type: transfer        # Not counted as income or expense
    display_order: 90
```

### Category Types

| Type | P&L Impact |
|------|------------|
| `income` | Added to income total |
| `expense` | Added to expense total |
| `transfer` | Not counted (money between accounts) |

### Categorization Rules

Rules automatically assign categories based on transaction descriptions:

```yaml
rules:
  - id: rule_starbucks
    category: dining
    keywords:
      - "STARBUCKS"
      - "SBUX"
    priority: 50

  - id: rule_amazon
    category: shopping
    keywords:
      - "AMAZON"
      - "AMZN"
    priority: 45

  - id: rule_large_amazon
    category: shopping
    keywords:
      - "AMAZON"
    amount_min: 500.00    # Only match amounts >= $500
    priority: 60          # Higher priority overrides rule_amazon
```

### Rule Priority

Higher priority rules are checked first. When multiple rules match:
1. **User corrections** (priority 1000) - Always highest
2. **AI categorization** (priority varies)
3. **Custom rules** (priority 50-100 recommended)
4. **Default rules** (priority 1-49)

### Rule Options

| Field | Description |
|-------|-------------|
| `keywords` | List of strings to match in description |
| `regex` | Regular expression pattern |
| `amount_min` | Minimum amount to match |
| `amount_max` | Maximum amount to match |
| `priority` | Rule priority (higher = checked first) |

---

## corrections.yaml

Stores user-provided category corrections. This file is auto-managed.

### Structure

```yaml
corrections:
  abc123def456:          # Transaction fingerprint
    category: dining
    source: user
    timestamp: "2025-01-15T10:30:00"
```

### Managing Corrections

```bash
# View current corrections
financial-consolidator --show-corrections

# Clear all corrections
financial-consolidator --clear-corrections

# Import corrections from reviewed file
financial-consolidator --import-corrections reviewed.xlsx
```

See [Category Corrections](05-category-corrections.md) for the full workflow.

---

## Sample Configuration

A complete sample configuration is available at:

```bash
# Copy sample config to start customizing
cp config/accounts_sample.yaml config/accounts.yaml
```

---

## Next Steps

- [Account Management](04-account-management.md) - Set up accounts and balances
- [Category Corrections](05-category-corrections.md) - Fix categorization errors
- [CLI Reference](08-cli-reference.md) - All configuration-related flags

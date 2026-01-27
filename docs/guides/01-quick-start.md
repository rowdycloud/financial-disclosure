# Quick Start Guide

Get up and running with the Financial Consolidator CLI in minutes.

## Prerequisites

- Python 3.11 or higher
- pip or uv package manager

## Installation

```bash
# Using pip
pip install financial-consolidator

# Or using uv (recommended)
uv pip install financial-consolidator
```

## Your First Analysis

### 1. Prepare Your Data

Collect your bank/credit card statement CSV files into a single directory:

```
bank_statements/
├── chase_checking_2025.csv
├── amex_platinum_jan.csv
└── capital_one_q1.csv
```

### 2. Run the Analysis

```bash
financial-consolidator -i ./bank_statements
```

On first run, the tool will:
1. Detect each CSV file
2. Prompt you to create accounts for unmapped files
3. Parse and categorize transactions
4. Generate output reports

### 3. Check Your Results

Output is saved to `analysis/YYYYMMDD_HHMMSS/`:

```bash
ls analysis/
```

You'll find:
- `pl_summary.csv` - Profit & Loss summary
- `all_transactions.csv` - All transactions with categories
- Per-account CSV files

## Common Next Steps

### Generate Excel Output

```bash
financial-consolidator -i ./bank_statements -o report.xlsx
```

### Filter by Date Range

```bash
financial-consolidator -i ./bank_statements --start-date 2025-01-01 --end-date 2025-12-31
```

### Run Non-Interactively (Skip Prompts)

```bash
financial-consolidator -i ./bank_statements --no-interactive
```

### Enable AI Categorization

```bash
export ANTHROPIC_API_KEY="your-api-key"
financial-consolidator -i ./bank_statements --ai
```

## Getting Help

```bash
# View all options
financial-consolidator --help

# Enable verbose output
financial-consolidator -i ./bank_statements -v
```

## Next Steps

- [Configuration Guide](02-configuration.md) - Customize settings, accounts, and categories
- [Account Management](04-account-management.md) - Set up accounts and opening balances
- [Output Formats](07-output-formats.md) - Understand the generated reports
- [CLI Reference](08-cli-reference.md) - Complete command reference

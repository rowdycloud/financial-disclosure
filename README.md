# Financial Consolidator

A Python tool for consolidating and analyzing financial transactions from multiple file formats.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](https://github.com/your-repo/financial-disclosure)

## Overview

Financial Consolidator processes bank statements and transaction exports from multiple sources, providing:

- **Multi-format parsing** - CSV, OFX/QFX, Excel, and PDF files
- **Automatic categorization** - Rule-based system with manual override support
- **Duplicate detection** - Fuzzy matching across files to flag duplicates
- **Anomaly detection** - Flags large transactions, fees, cash advances, and date gaps
- **Financial reporting** - Excel workbooks with P&L summaries and detailed analysis

## Features

- **Multi-format CSV parsing** - Recognizes Chase, Bank of America, Wells Fargo, Capital One, and other common CSV formats
- **Flexible categorization** - Priority-ordered rules with regex pattern matching
- **Fuzzy duplicate detection** - Configurable similarity threshold and date tolerance
- **Running balance calculation** - Per-account balance tracking
- **Excel output** - Styled workbooks with multiple analysis sheets
- **CSV export** - Google Sheets compatible output files
- **Interactive mode** - Prompts to create accounts and map files on first run

## Installation

```bash
# Clone repository
git clone <repo-url>
cd financial-disclosure

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install as editable package
pip install -e .
```

### Dependencies

- pandas >= 2.0
- openpyxl >= 3.1
- pdfplumber >= 0.10
- ofxparse >= 0.21
- pyyaml >= 6.0
- rich >= 13.0

## Quick Start

```bash
# Basic usage - outputs to analysis/analysis_YYYYMMDD_HHMMSS.csv
financial-consolidator -i ./bank_statements

# With date range filter
financial-consolidator -i ./statements \
  --start-date 2024-01-01 --end-date 2024-12-31

# Also export Excel workbook alongside CSV
financial-consolidator -i ./statements --xlsx

# Custom output path
financial-consolidator -i ./statements -o my_report.csv

# Legacy Excel output with CSV export
financial-consolidator -i ./statements -o report.xlsx --csv

# Non-interactive mode (skip unmapped files)
financial-consolidator -i ./statements --no-interactive

# Verbose output for debugging
financial-consolidator -i ./statements -vv
```

## Configuration

Configuration files are stored in the `config/` directory:

### settings.yaml

Global application settings:

```yaml
output:
  format: "xlsx"
  date_format: "%Y-%m-%d"
  currency_symbol: "$"
  decimal_places: 2

anomaly_detection:
  large_transaction_threshold: 5000.00
  date_gap_warning_days: 7
  date_gap_alert_days: 30
  fee_keywords:
    - FEE
    - CHARGE
    - PENALTY
    - OVERDRAFT
  cash_advance_keywords:
    - CASH ADVANCE
    - ATM WITHDRAWAL

logging:
  level: "INFO"
  file: "financial_consolidator.log"
```

### accounts.yaml

Account definitions and file mappings:

```yaml
accounts:
  checking_main:
    name: "Primary Checking"
    type: checking
    institution: "Chase"
    source_file_patterns:
      - "*chase*checking*.csv"
    opening_balance: 1000.00
    opening_balance_date: "2024-01-01"

  credit_card:
    name: "Rewards Card"
    type: credit_card
    institution: "Bank of America"

file_mappings:
  "Chase1234_Activity.csv": "checking_main"
```

### categories.yaml

Category hierarchy and categorization rules:

```yaml
categories:
  - id: income_salary
    name: "Salary"
    type: income

  - id: expense_groceries
    name: "Groceries"
    type: expense

  - id: expense_utilities
    name: "Utilities"
    type: expense
    parent_id: expense_housing

rules:
  - id: salary_direct_deposit
    category_id: income_salary
    priority: 100
    keywords:
      - DIRECT DEPOSIT
      - PAYROLL

  - id: grocery_stores
    category_id: expense_groceries
    priority: 50
    keywords:
      - KROGER
      - WHOLE FOODS
      - TRADER JOE
```

### manual_categories.yaml (optional)

Manual overrides for specific transactions:

```yaml
overrides:
  - category_id: expense_travel
    priority: 1000
    date: "2024-03-15"
    amount: -500.00
    description_pattern: "HOTEL"
```

## CLI Reference

| Option | Description |
|--------|-------------|
| `-i, --input-dir PATH` | Directory containing transaction files (required) |
| `-o, --output PATH` | Output file path (default: analysis/analysis_YYYYMMDD_HHMMSS.csv) |
| `--config-dir PATH` | Configuration directory (default: ./config) |
| `--config PATH` | Path to settings.yaml |
| `--accounts PATH` | Path to accounts.yaml |
| `--categories PATH` | Path to categories.yaml |
| `--start-date DATE` | Filter transactions from this date (YYYY-MM-DD) |
| `--end-date DATE` | Filter transactions until this date (YYYY-MM-DD) |
| `--xlsx` | Also export Excel workbook (when using CSV output) |
| `--csv` | Also export CSV files (when using .xlsx output) |
| `--no-interactive` | Skip prompts for unmapped files |
| `--strict` | Abort on first parse error |
| `--dry-run` | Parse files without generating output |
| `--validate-only` | Validate configuration files only |
| `--large-transaction-threshold AMOUNT` | Override large transaction threshold |
| `-v, --verbose` | Increase verbosity (-v, -vv, -vvv) |
| `--version` | Show version |
| `-h, --help` | Show help |

## Supported File Formats

| Format | Extensions | Notes |
|--------|------------|-------|
| CSV | .csv | Auto-detects Chase, Bank of America, Wells Fargo, and generic formats |
| OFX/QFX | .ofx, .qfx | Open Financial Exchange standard |
| Excel | .xlsx | Multi-sheet workbook support |
| PDF | .pdf | Bank statement extraction |

## Output Files

By default, output files are written to the `analysis/` directory with timestamped filenames (e.g., `analysis/analysis_20240115_143022_*.csv`). Use `-o` to specify a custom path.

### CSV Export (Default)

CSV files are generated by default for easy import into Google Sheets:

- `{base}_pl_summary.csv` - P&L summary
- `{base}_all_transactions.csv` - All transactions
- `{base}_account_{name}.csv` - Per-account sheets
- `{base}_category_analysis.csv` - Category breakdown
- `{base}_anomalies.csv` - Flagged items

Use `--xlsx` to also generate an Excel workbook.

### Excel Workbook

Use `-o report.xlsx` or `--xlsx` flag. The Excel file contains multiple sheets:

- **P&L Summary** - Income vs. expenses breakdown by category
- **All Transactions** - Master list with all columns (date, account, description, category, amount, balance, flags)
- **[Account Name]** - Per-account transaction history (one sheet per account)
- **Category Analysis** - Monthly spending by category
- **Anomalies** - Flagged transactions and date gaps

## Project Structure

```
financial-disclosure/
├── config/                          # Configuration files
│   ├── settings.yaml
│   ├── accounts.yaml
│   ├── categories.yaml
│   └── manual_categories.yaml
├── src/financial_consolidator/
│   ├── __init__.py
│   ├── cli.py                       # Command-line interface
│   ├── config.py                    # Configuration loading
│   ├── models/                      # Data models
│   │   ├── transaction.py
│   │   ├── account.py
│   │   └── category.py
│   ├── parsers/                     # File format parsers
│   │   ├── detector.py              # Format detection
│   │   ├── csv_parser.py
│   │   ├── ofx_parser.py
│   │   ├── excel_parser.py
│   │   └── pdf_parser.py
│   ├── processing/                  # Transaction processing
│   │   ├── normalizer.py
│   │   ├── categorizer.py
│   │   ├── deduplicator.py
│   │   ├── anomaly_detector.py
│   │   └── balance_calculator.py
│   ├── output/                      # Report generation
│   │   ├── excel_writer.py
│   │   └── csv_exporter.py
│   └── utils/                       # Utilities
│       ├── date_utils.py
│       ├── decimal_utils.py
│       └── logging_config.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Processing Pipeline

1. **File Discovery** - Scan input directory for supported file types
2. **Format Detection** - Identify appropriate parser for each file
3. **Account Mapping** - Associate files with configured accounts
4. **Parsing** - Extract raw transactions from each file
5. **Normalization** - Standardize dates, amounts, and formats
6. **Categorization** - Apply rules and manual overrides
7. **Deduplication** - Flag duplicate transactions
8. **Balance Calculation** - Compute running balances per account
9. **Anomaly Detection** - Flag suspicious transactions
10. **Output Generation** - Create Excel workbook and CSV files

## License

MIT License - see LICENSE file for details.

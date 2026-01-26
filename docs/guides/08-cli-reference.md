# CLI Reference

Complete reference for all `financial-consolidator` command-line arguments.

## Usage

```bash
financial-consolidator [OPTIONS]
```

## Quick Examples

```bash
# Basic analysis
financial-consolidator -i ./bank_statements

# Excel output with date filter
financial-consolidator -i ./statements -o report.xlsx --start-date 2025-01-01

# AI-powered categorization
financial-consolidator -i ./statements --ai --ai-budget 10.00

# Import corrections
financial-consolidator --import-corrections reviewed.xlsx

# Set account balance
financial-consolidator --set-balance chase_checking --balance 5234.56
```

---

## Argument Groups

### Standard Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--version` | flag | — | Show program version and exit |
| `-h, --help` | flag | — | Show help message and exit |
| `-i, --input-dir` | PATH | — | Directory containing transaction CSV files |
| `-o, --output` | PATH | auto | Output file path (.csv or .xlsx) |
| `--config` | PATH | config/settings.yaml | Path to settings configuration |
| `--categories` | PATH | config/categories.yaml | Path to categories configuration |
| `--accounts` | PATH | config/accounts.yaml | Path to accounts configuration |
| `--config-dir` | PATH | ./config | Base configuration directory |
| `--start-date` | DATE | — | Filter: only include transactions on or after (YYYY-MM-DD) |
| `--end-date` | DATE | — | Filter: only include transactions on or before (YYYY-MM-DD) |
| `--csv` | flag | false | Also export CSV files (when using .xlsx output) |
| `--xlsx` | flag | false | Also export Excel workbook (when using CSV output) |
| `--no-interactive` | flag | false | Skip all prompts, skip unmapped files |
| `--strict` | flag | false | Abort on first parse error instead of skipping |
| `--large-transaction-threshold` | FLOAT | 5000 | Override threshold for large transaction alerts |
| `-v, --verbose` | count | 0 | Increase verbosity (-v for INFO, -vv for DEBUG) |
| `--dry-run` | flag | false | Parse files but do not generate output |
| `--validate-only` | flag | false | Validate configuration files and exit |
| `--export-uncategorized` | PATH | — | Export uncategorized transactions to file |
| `--export-summary` | PATH | — | Export categorization summary statistics |

### AI Categorization

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--ai` | flag | false | Enable all AI features (validation + categorization) |
| `--ai-validate` | flag | false | Validate low-confidence rule-based categorizations |
| `--ai-categorize` | flag | false | Categorize uncategorized transactions |
| `--ai-budget` | FLOAT | 5.00 | Maximum AI spend per run in USD |
| `--ai-dry-run` | flag | false | Preview AI costs without making API calls |
| `--ai-confidence` | FLOAT | 0.7 | Confidence threshold for AI validation (0.0-1.0) |
| `--skip-ai-confirm` | flag | false | Skip confirmation prompts for AI spending |

### Corrections Management

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--import-corrections` | PATH | — | Import category corrections from reviewed file |
| `--show-corrections` | flag | false | Display current corrections and exit |
| `--clear-corrections` | flag | false | Delete all stored corrections |
| `--force` | flag | false | Skip confirmation (use with --clear-corrections) |
| `--corrections-file` | PATH | config/corrections.yaml | Path to corrections file |

### Balance Management

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--set-balance` | ACCOUNT_ID | — | Set opening balance for an account |
| `--balance` | AMOUNT | — | Balance amount (required with --set-balance) |
| `--balance-date` | DATE | today | Balance date in YYYY-MM-DD format |

---

## Detailed Descriptions

### Input/Output

#### `-i, --input-dir PATH`

Directory containing your transaction CSV files. Required for processing (unless using management commands).

```bash
financial-consolidator -i ./bank_statements
financial-consolidator -i /path/to/downloads/
```

#### `-o, --output PATH`

Output file or directory path. Format determined by extension:

```bash
# CSV output (directory created)
financial-consolidator -i ./statements -o ./reports/

# Excel output (single file)
financial-consolidator -i ./statements -o report.xlsx

# Auto-generated path (default)
financial-consolidator -i ./statements
# Creates: analysis/YYYYMMDD_HHMMSS/
```

### Configuration

#### `--config-dir PATH`

Base directory for all config files. Individual file paths are relative to this.

```bash
# Use alternative config directory
financial-consolidator -i ./statements --config-dir /path/to/config/
```

#### `--config, --categories, --accounts PATH`

Override specific configuration files:

```bash
financial-consolidator -i ./statements \
  --config /alt/settings.yaml \
  --categories /alt/categories.yaml \
  --accounts /alt/accounts.yaml
```

### Date Filtering

#### `--start-date, --end-date DATE`

Filter transactions by date range. Format: YYYY-MM-DD

```bash
# Full year 2025
financial-consolidator -i ./statements --start-date 2025-01-01 --end-date 2025-12-31

# From start date onwards
financial-consolidator -i ./statements --start-date 2025-06-01

# Up to end date
financial-consolidator -i ./statements --end-date 2025-06-30
```

### Processing Modes

#### `--no-interactive`

Skip all prompts. Unmapped files are skipped instead of prompting for account creation.

```bash
# For automated/CI usage
financial-consolidator -i ./statements --no-interactive
```

#### `--strict`

Abort on first parse error instead of logging and continuing.

```bash
# Fail fast for debugging
financial-consolidator -i ./statements --strict
```

#### `--dry-run`

Parse and categorize but don't generate output files.

```bash
# Preview what would be processed
financial-consolidator -i ./statements --dry-run
```

#### `--validate-only`

Check configuration files without processing any transactions.

```bash
# Verify config is valid
financial-consolidator --validate-only
```

### Verbosity

#### `-v, --verbose`

Increase output detail. Can be used multiple times.

| Level | Meaning |
|-------|---------|
| (none) | Warnings only |
| `-v` | Info messages |
| `-vv` | Debug messages |
| `-vvv` | Trace messages |

```bash
# Standard verbose
financial-consolidator -i ./statements -v

# Debug mode
financial-consolidator -i ./statements -vv
```

### AI Features

#### `--ai`

Enable all AI features. Equivalent to `--ai-validate --ai-categorize`.

```bash
financial-consolidator -i ./statements --ai
```

#### `--ai-validate`

Only validate low-confidence rule-based categorizations.

```bash
financial-consolidator -i ./statements --ai-validate
```

#### `--ai-categorize`

Only categorize uncategorized transactions.

```bash
financial-consolidator -i ./statements --ai-categorize
```

#### `--ai-budget AMOUNT`

Maximum USD to spend on AI per run.

```bash
financial-consolidator -i ./statements --ai --ai-budget 10.00
```

#### `--ai-dry-run`

Show cost estimates without making API calls.

```bash
financial-consolidator -i ./statements --ai --ai-dry-run
```

#### `--ai-confidence THRESHOLD`

Confidence threshold (0.0-1.0). Transactions below this are sent for validation.

```bash
# More aggressive validation
financial-consolidator -i ./statements --ai-validate --ai-confidence 0.5
```

### Corrections

#### `--import-corrections PATH`

Import category corrections from a reviewed output file.

```bash
financial-consolidator --import-corrections reviewed.xlsx
financial-consolidator --import-corrections all_transactions.csv
```

#### `--show-corrections`

Display all stored corrections.

```bash
financial-consolidator --show-corrections
```

#### `--clear-corrections`

Delete all corrections. Prompts for confirmation unless `--force` is used.

```bash
financial-consolidator --clear-corrections
financial-consolidator --clear-corrections --force
```

### Balance Management

#### `--set-balance ACCOUNT_ID`

Set or update opening balance for an account. Requires `--balance`.

```bash
financial-consolidator --set-balance chase_checking --balance 5234.56
financial-consolidator --set-balance chase_checking --balance 5234.56 --balance-date 2025-01-01
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key for AI categorization (default name, configurable) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |

---

## Command Patterns

### Daily Workflow

```bash
# Process new statements
financial-consolidator -i ./downloads -o today.xlsx

# Review and correct
# (edit today.xlsx in Excel)

# Import corrections
financial-consolidator --import-corrections today.xlsx

# Final output
financial-consolidator -i ./downloads -o final.xlsx
```

### Monthly Analysis

```bash
financial-consolidator -i ./statements \
  --start-date 2025-01-01 \
  --end-date 2025-01-31 \
  -o january_2025.xlsx
```

### Year-End Report

```bash
financial-consolidator -i ./all_statements \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --ai --ai-budget 20.00 \
  -o 2025_annual_report.xlsx
```

### CI/CD Pipeline

```bash
financial-consolidator -i ./statements \
  --no-interactive \
  --strict \
  --ai --ai-budget 5.00 --skip-ai-confirm \
  -o /output/report.xlsx
```

---

## See Also

- [Quick Start](01-quick-start.md) - Get started quickly
- [Configuration Guide](02-configuration.md) - Config file details
- [AI Categorization](06-ai-categorization.md) - AI feature details
- [Category Corrections](05-category-corrections.md) - Correction workflow

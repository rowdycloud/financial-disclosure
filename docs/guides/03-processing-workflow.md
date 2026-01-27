# Processing Workflow Guide

Understanding how the Financial Consolidator processes your transaction data helps you troubleshoot issues and optimize your workflow.

## The Four Processing Phases

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Phase 1        │    │  Phase 2         │    │  Phase 3        │    │  Phase 4         │
│  File Discovery │ -> │  Parsing &       │ -> │  Categorization │ -> │  Output          │
│  & Mapping      │    │  Normalization   │    │  & Analysis     │    │  Generation      │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └──────────────────┘
```

---

## Phase 1: File Discovery & Account Mapping

The tool scans your input directory for CSV files and maps them to accounts.

### What Happens

1. **Scans** the input directory for `.csv` files
2. **Matches** files against existing file mappings in `accounts.yaml`
3. **Prompts** for unmapped files (unless `--no-interactive`)
4. **Cleans up** stale mappings (files that no longer exist)

### Interactive Prompts

When an unmapped file is detected:

```
Found unmapped file: chase_activity_2025.csv

Select an action:
1. Create new account
2. Map to existing account: Chase Checking
3. Map to existing account: Amex Platinum
4. Skip this file

Your choice:
```

### Stale Mapping Cleanup

If a file mapping references a file that no longer exists:

```
The following file mappings reference non-existent files:
  - old_statement_2023.csv

Remove stale mappings? [Y/n]:
```

### Skip Interactive Mode

```bash
# Skip all prompts, ignore unmapped files
financial-consolidator -i ./statements --no-interactive
```

---

## Phase 2: Parsing & Normalization

Each CSV file is parsed according to its account's parser configuration.

### What Happens

1. **Detects** file format (Chase, Amex, Citi, etc.)
2. **Parses** columns into standard transaction fields
3. **Normalizes** amounts, dates, and descriptions
4. **Assigns** fingerprints for duplicate detection
5. **Infers** opening balances (if not set)

### Supported Formats

| Institution | Auto-Detected |
|-------------|---------------|
| Chase | Yes |
| American Express | Yes |
| Capital One | Yes |
| Citibank | Yes |
| Bank of America | Yes |
| Wells Fargo | Yes |
| Generic CSV | Fallback |

### Date Filtering

Filter transactions by date range:

```bash
# Only process transactions in 2025
financial-consolidator -i ./statements --start-date 2025-01-01 --end-date 2025-12-31

# Process from a start date onwards
financial-consolidator -i ./statements --start-date 2025-06-01
```

### Strict Mode

By default, parsing errors are logged and the file is skipped. Use strict mode to abort on first error:

```bash
# Abort on first parse error
financial-consolidator -i ./statements --strict
```

---

## Phase 3: Categorization & Analysis

Transactions are categorized and analyzed for patterns.

### Categorization Priority

Categories are assigned in this order (highest priority first):

1. **User corrections** - Manual overrides from `corrections.yaml`
2. **AI categorization** - If enabled with `--ai`
3. **Rule-based** - Keyword and regex matches from `categories.yaml`
4. **Uncategorized** - Left for manual review

### Analysis Performed

- **P&L calculation** - Income vs expenses by category and year
- **Running balances** - Per-account balance tracking
- **Anomaly detection** - Large transactions, date gaps
- **Category statistics** - Spending patterns by category

---

## Phase 4: Output Generation

Results are written to files in your chosen format.

### Default Output Location

```
analysis/YYYYMMDD_HHMMSS/
├── pl_summary.csv
├── all_transactions.csv
├── deposits.csv
├── transfers.csv
├── account_chase_checking.csv
├── category_analysis.csv
└── anomalies.csv
```

### Output Format Options

```bash
# CSV output (default)
financial-consolidator -i ./statements

# Excel output
financial-consolidator -i ./statements -o report.xlsx

# Both formats
financial-consolidator -i ./statements -o report.xlsx --csv
```

See [Output Formats](07-output-formats.md) for details on each file.

---

## Workflow Examples

### Basic Analysis

```bash
financial-consolidator -i ./bank_statements
```

### Year-End Analysis

```bash
financial-consolidator -i ./bank_statements \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  -o 2025_analysis.xlsx
```

### CI/CD Pipeline

```bash
financial-consolidator -i ./statements \
  --no-interactive \
  --strict \
  -o /output/report.xlsx
```

### Debug Mode

```bash
# Verbose output
financial-consolidator -i ./statements -v

# Debug output (very verbose)
financial-consolidator -i ./statements -vv
```

### Dry Run (Preview)

```bash
# Parse files but don't generate output
financial-consolidator -i ./statements --dry-run
```

### Validate Configuration Only

```bash
# Check config files without processing
financial-consolidator --validate-only
```

---

## Troubleshooting

### File Not Being Processed

1. Check the file is in the input directory
2. Verify it has a `.csv` extension
3. Check if it's mapped in `accounts.yaml`
4. Run with `-v` to see which files are skipped

### Parse Errors

```bash
# See detailed error messages
financial-consolidator -i ./statements -vv

# Abort on first error to identify problem file
financial-consolidator -i ./statements --strict
```

### Wrong Categories

1. Check rule priority in `categories.yaml`
2. Import corrections from reviewed output
3. Consider enabling AI categorization

See [Category Corrections](05-category-corrections.md) for fixing categorization.

---

## Next Steps

- [Account Management](04-account-management.md) - Set up accounts properly
- [Category Corrections](05-category-corrections.md) - Fix categorization errors
- [AI Categorization](06-ai-categorization.md) - Enable AI-powered categorization
- [Output Formats](07-output-formats.md) - Understand the generated reports

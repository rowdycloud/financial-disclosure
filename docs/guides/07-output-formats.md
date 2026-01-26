# Output Formats Guide

The Financial Consolidator generates comprehensive reports in CSV and Excel formats. This guide explains each output file and how to use them.

## Output Location

By default, output is saved to a timestamped directory:

```
analysis/
└── 20250115_143022/          # YYYYMMDD_HHMMSS
    ├── pl_summary.csv
    ├── all_transactions.csv
    ├── deposits.csv
    ├── transfers.csv
    ├── account_chase_checking.csv
    ├── category_analysis.csv
    └── anomalies.csv
```

### Custom Output Path

```bash
# Specify output file
financial-consolidator -i ./statements -o my_report.xlsx

# Specify output directory
financial-consolidator -i ./statements -o /path/to/output/
```

---

## Format Selection

### CSV Output (Default)

```bash
financial-consolidator -i ./statements
```

Generates a directory of CSV files.

### Excel Output

```bash
financial-consolidator -i ./statements -o report.xlsx
```

Generates a single Excel workbook with multiple sheets.

### Both Formats

```bash
# Excel primary, also generate CSVs
financial-consolidator -i ./statements -o report.xlsx --csv

# CSV primary, also generate Excel
financial-consolidator -i ./statements --xlsx
```

---

## CSV Files

### pl_summary.csv

**Profit & Loss summary with year-by-year breakdown.**

```
REPORT SUMMARY
Period,2025-01-01 to 2025-12-31
Accounts,"Chase Checking, Amex Platinum, ..."

INCOME,2024,2025,Total
Salary,50000.00,75000.00,125000.00
Refunds,500.00,750.00,1250.00
Total Income,50500.00,75750.00,126250.00

EXPENSES,2024,2025,Total
Dining,2000.00,3500.00,5500.00
Groceries,4000.00,5000.00,9000.00
...
Total Expenses,25000.00,35000.00,60000.00

NET INCOME,25500.00,40750.00,66250.00

TRANSFERS,2024,2025,Total
Transfers,5000.00,3000.00,8000.00
```

### all_transactions.csv

**Master list of all transactions with full details.**

| Column | Description |
|--------|-------------|
| Date | Transaction date |
| Description | Original description |
| Amount | Transaction amount |
| Account | Account name |
| Category | Assigned category |
| Category Type | income/expense/transfer |
| Source | How categorized (rule/ai/correction) |
| Confidence | Categorization confidence (0-1) |
| Fingerprint | Unique transaction ID |
| Balance | Running balance (if available) |

### deposits.csv

**Positive amount transactions only.**

Useful for reviewing income and credits separately.

### transfers.csv

**Transactions categorized as transfers.**

Money moved between your own accounts - not counted as income or expense.

### account_{id}.csv

**Per-account transaction history.**

One file per account (e.g., `account_chase_checking.csv`), containing:
- Opening balance row
- All transactions for that account
- Running balance column

### category_analysis.csv

**Monthly spending breakdown by category.**

```
Category,Jan 2025,Feb 2025,Mar 2025,...,Total
Dining,350.00,425.00,380.00,...,4500.00
Groceries,500.00,480.00,520.00,...,6000.00
...
```

### anomalies.csv

**Flagged transactions and date gaps.**

Includes:
- Large transactions (above threshold)
- Date gaps in transaction history
- Duplicate fingerprints
- Other anomalies

---

## Optional CSV Exports

### Export Uncategorized Transactions

```bash
financial-consolidator -i ./statements --export-uncategorized review.csv
```

Creates a CSV with only uncategorized transactions for focused review.

### Export Categorization Summary

```bash
financial-consolidator -i ./statements --export-summary stats.csv
```

Creates a CSV with categorization statistics:
- Count by category
- Count by source (rule/ai/correction/uncategorized)
- Confidence distribution

---

## Excel Sheets

When generating Excel output, you get a single workbook with these sheets:

### 1. Category Lookup (Hidden)

**Internal reference sheet for VLOOKUP formulas.**

Contains category names and types. Used by formulas in P&L Summary.
This sheet is hidden but can be unhidden if needed.

### 2. P&L Summary

**Formula-driven Profit & Loss statement.**

- Dynamically calculates totals from All Transactions
- Updates automatically if you modify categories
- Year-by-year columns plus Total column

### 3. All Transactions

**Master transaction list - same as CSV but with formatting.**

| Column | Description |
|--------|-------------|
| A | Date |
| B | Description |
| C | Amount (currency formatted) |
| D | Account |
| E | Category (dropdown for editing) |
| F | Category Type |
| ... | Additional metadata |

**Tip:** Edit the Category column, save, then import corrections.

### 4. Review Queue

**Transactions needing attention.**

Contains:
- Uncategorized transactions
- Low-confidence categorizations
- Flagged anomalies

Start your review here for the most impactful corrections.

### 5. Deposits

**Positive amount transactions.**

Same as deposits.csv but in Excel format.

### 6. Transfers

**Transfer transactions.**

Same as transfers.csv but in Excel format.

### 7. Account Summary

**Per-account balance overview.**

| Account | Opening Balance | Total Credits | Total Debits | Closing Balance |
|---------|-----------------|---------------|--------------|-----------------|
| Chase Checking | $5,234.56 | $12,500.00 | -$8,750.00 | $8,984.56 |
| Amex Platinum | -$1,000.00 | $500.00 | -$2,500.00 | -$3,000.00 |

### 8. [Account Name] Sheets

**One sheet per account.**

Each account gets its own sheet showing:
- Opening balance row (styled differently)
- Chronological transactions
- Running balance column

### 9. Category Analysis

**Monthly spending by category.**

Same as category_analysis.csv but with Excel formatting and charts.

### 10. Anomalies

**Flagged items for review.**

Same as anomalies.csv but in Excel format.

---

## Working with Excel Output

### Editing Categories

1. Go to **All Transactions** or **Review Queue** sheet
2. Find the **Category** column
3. Use the dropdown or type a category name
4. Save the file
5. Import corrections:

```bash
financial-consolidator --import-corrections report.xlsx
```

### Refreshing Formulas

The P&L Summary uses formulas that reference All Transactions. If you:
- Add transactions manually
- Change category names

The P&L should update automatically. If not, press Ctrl+Shift+F9 (Windows) or Cmd+Shift+F9 (Mac) to force recalculation.

### Filtering Large Files

Use Excel's filter feature:
1. Select the header row
2. Data → Filter
3. Click dropdown arrows to filter by account, category, etc.

---

## Output Customization

### Large Transaction Threshold

Control what counts as a "large transaction" in anomalies:

```bash
# Flag transactions over $10,000
financial-consolidator -i ./statements --large-transaction-threshold 10000
```

### Date Filtering

Limit output to a specific period:

```bash
financial-consolidator -i ./statements --start-date 2025-01-01 --end-date 2025-12-31
```

---

## Common Tasks

### Compare Two Periods

```bash
# Generate 2024 report
financial-consolidator -i ./statements \
  --start-date 2024-01-01 --end-date 2024-12-31 \
  -o 2024_report.xlsx

# Generate 2025 report
financial-consolidator -i ./statements \
  --start-date 2025-01-01 --end-date 2025-12-31 \
  -o 2025_report.xlsx
```

### Extract Specific Category

Use Excel filtering or:

```bash
# Generate full report, then filter in Excel
financial-consolidator -i ./statements -o report.xlsx
```

### Archive Reports

Reports are timestamped by default. For archival:

```bash
# Explicit naming
financial-consolidator -i ./statements -o reports/2025_Q1_analysis.xlsx
```

---

## Next Steps

- [Category Corrections](05-category-corrections.md) - Edit and import corrections from Excel
- [Processing Workflow](03-processing-workflow.md) - Understand what generates each output
- [CLI Reference](08-cli-reference.md) - All output-related flags

# Category Corrections Guide

When automatic categorization gets it wrong, you can manually correct transactions. Corrections are stored in `config/corrections.yaml` and take the highest priority during categorization.

## The Correction Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. Run     │    │  2. Review  │    │  3. Import  │    │  4. Re-run  │
│  Analysis   │ -> │  & Edit     │ -> │  Corrections│ -> │  Analysis   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Step 1: Run Initial Analysis

```bash
financial-consolidator -i ./statements -o analysis.xlsx
```

### Step 2: Review & Edit Categories

1. Open `analysis.xlsx` in Excel
2. Go to the **All Transactions** or **Review Queue** sheet
3. Find transactions with wrong categories
4. Edit the **Category** column with the correct category name

**Important:** Use the exact category name from your `categories.yaml` file.

### Step 3: Import Corrections

```bash
financial-consolidator --import-corrections analysis.xlsx
```

Output:
```
Importing corrections from analysis.xlsx...
Found 15 category changes:
  - "AMAZON PRIME" -> Shopping (was: Subscriptions)
  - "UBER TRIP" -> Transportation (was: Dining)
  ...
Imported 15 corrections to config/corrections.yaml
```

### Step 4: Re-run Analysis

```bash
financial-consolidator -i ./statements -o analysis_corrected.xlsx
```

Corrections are now applied. The corrected transactions will show `source: correction` in the output.

---

## Managing Corrections

### View Current Corrections

```bash
financial-consolidator --show-corrections
```

Output:
```
Current corrections (15 total):

Fingerprint: abc123def456
  Category: shopping
  Applied: 2025-01-15 10:30:00

Fingerprint: xyz789ghi012
  Category: transportation
  Applied: 2025-01-15 10:30:00

...
```

### Clear All Corrections

```bash
# With confirmation prompt
financial-consolidator --clear-corrections

# Skip confirmation
financial-consolidator --clear-corrections --force
```

Output:
```
This will delete all 15 corrections from config/corrections.yaml.
Are you sure? [y/N]: y
Cleared all corrections.
```

### Use Custom Corrections File

```bash
# Import to a different corrections file
financial-consolidator --import-corrections analysis.xlsx --corrections-file /path/to/corrections.yaml

# Use a different corrections file during processing
financial-consolidator -i ./statements --corrections-file /path/to/corrections.yaml
```

---

## How Corrections Work

### Fingerprint Matching

Each transaction has a unique fingerprint based on:
- Date
- Description
- Amount
- Account

When you import corrections, the tool matches fingerprints to apply the right category to the right transaction.

### Priority System

Corrections have the highest priority in categorization:

1. **Corrections** (priority 1000) - Your manual overrides
2. **AI categorization** (if enabled)
3. **Rule-based categorization**
4. **Uncategorized** (fallback)

This means your corrections always win, even if a rule or AI would suggest something different.

### Persistence

Corrections are stored in `config/corrections.yaml`:

```yaml
corrections:
  abc123def456:
    category: shopping
    source: user
    timestamp: "2025-01-15T10:30:00"
  xyz789ghi012:
    category: transportation
    source: user
    timestamp: "2025-01-15T10:30:00"
```

These corrections persist across runs until you clear them.

---

## Import Sources

### From Excel (.xlsx)

```bash
financial-consolidator --import-corrections analysis.xlsx
```

The tool looks for:
- **All Transactions** sheet
- **Fingerprint** and **Category** columns

### From CSV

```bash
financial-consolidator --import-corrections all_transactions.csv
```

CSV must have `fingerprint` and `category` columns.

---

## Best Practices

### 1. Review the Review Queue

The **Review Queue** sheet in Excel contains:
- Uncategorized transactions
- Low-confidence categorizations
- Flagged anomalies

Start your review here for the most impactful corrections.

### 2. Use Consistent Category Names

Category names must match exactly what's in `categories.yaml`. Common issues:

| Wrong | Correct |
|-------|---------|
| `Dining Out` | `Dining` |
| `groceries` | `Groceries` |
| `SHOPPING` | `Shopping` |

### 3. Batch Your Corrections

Make all your corrections in one editing session, then import once:

```bash
# Good: One import with many corrections
financial-consolidator --import-corrections analysis.xlsx

# Avoid: Multiple imports
financial-consolidator --import-corrections file1.xlsx
financial-consolidator --import-corrections file2.xlsx
```

### 4. Consider Adding Rules

If you're correcting the same type of transaction repeatedly, add a rule to `categories.yaml` instead:

```yaml
rules:
  - id: rule_my_gym
    category: healthcare
    keywords:
      - "ANYTIME FITNESS"
      - "PLANET FITNESS"
    priority: 50
```

---

## Troubleshooting

### Corrections Not Applied

1. **Check fingerprint match**: The transaction fingerprint must match exactly
2. **Check category name**: Must match a category in `categories.yaml`
3. **Verify file was saved**: Excel must be saved before import

### Wrong Transactions Corrected

Fingerprints can collide if you have:
- Same description
- Same amount
- Same date
- Same account

This is rare but possible. The tool warns about duplicate fingerprints in the **Anomalies** output.

### Corrections Lost

Corrections are stored in `config/corrections.yaml`. If this file is deleted or overwritten, corrections are lost. Consider:
- Backing up your config directory
- Using version control for config files

---

## Example Workflow

```bash
# 1. Initial analysis
financial-consolidator -i ./bank_statements -o report.xlsx

# 2. (Open report.xlsx, edit categories, save)

# 3. Import corrections
financial-consolidator --import-corrections report.xlsx
# Output: Imported 23 corrections

# 4. Re-run with corrections
financial-consolidator -i ./bank_statements -o report_v2.xlsx

# 5. Verify corrections applied
financial-consolidator --show-corrections
```

---

## Next Steps

- [AI Categorization](06-ai-categorization.md) - Reduce manual corrections with AI
- [Configuration Guide](02-configuration.md) - Add categorization rules
- [Output Formats](07-output-formats.md) - Understand the Review Queue sheet

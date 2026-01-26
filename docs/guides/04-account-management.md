# Account Management Guide

Accounts represent your financial institutions - checking accounts, credit cards, loans, etc. This guide covers creating accounts, setting opening balances, and managing file mappings.

## Account Types

| Type | Description | Balance Semantics |
|------|-------------|-------------------|
| `checking` | Checking accounts | Positive = money available |
| `savings` | Savings accounts | Positive = money available |
| `credit_card` | Credit cards | Negative = amount owed |
| `loan` | Loans and mortgages | Negative = amount owed |
| `investment` | Investment accounts | Positive = portfolio value |
| `crypto` | Cryptocurrency | Positive = holdings value |

---

## Creating Accounts

### Interactive Creation

When processing an unmapped CSV file, the tool prompts you to create an account:

```
Found unmapped file: chase_activity_jan2025.csv

Select an action:
1. Create new account
2. Map to existing account
3. Skip this file

Your choice: 1

Enter account details:
  Account ID (e.g., chase_checking): chase_checking
  Display name: Chase Checking ****1234
  Account type:
    1. checking
    2. savings
    3. credit_card
    4. loan
    5. investment
    6. crypto
  Your choice: 1

Opening Balance
Enter the balance as of the first transaction date.
Leave blank to auto-detect from transaction data, or enter 0 to start fresh.
  Opening balance: $5234.56
  Balance date (YYYY-MM-DD, blank for today): 2025-01-01

Account created: chase_checking
```

### Manual Creation

Add accounts directly to `config/accounts.yaml`:

```yaml
accounts:
  chase_checking:
    name: Chase Checking ****1234
    type: checking
    institution: Chase
    opening_balance: "5234.56"
    opening_balance_date: "2025-01-01"
    file_mappings:
      - pattern: "Chase*Activity*.csv"
```

---

## Opening Balances

Opening balances ensure accurate running balance calculations. There are three ways to set them:

### 1. Interactive Prompt

During account creation, you're prompted for the opening balance:

```
Opening Balance
Enter the balance as of the first transaction date.
Leave blank to auto-detect from transaction data, or enter 0 to start fresh.
  Opening balance: $____
```

- **Enter a value**: Saved immediately to `accounts.yaml`
- **Leave blank**: System will attempt to infer from transaction data
- **Enter 0**: Starts with zero balance (explicit)

### 2. CLI Command

Set or update opening balance for an existing account:

```bash
# Set opening balance
financial-consolidator --set-balance chase_checking --balance 5234.56 --balance-date 2025-01-01

# Update balance (same command)
financial-consolidator --set-balance chase_checking --balance 6000.00 --balance-date 2025-02-01
```

### 3. Auto-Inference

If no opening balance is set (blank during creation), the system attempts to infer it from the CSV data after parsing.

**How it works:**
1. Finds the first transaction for the account
2. Looks for a "Balance" column in the CSV
3. Calculates: `opening_balance = first_balance - first_amount`

**Example:**
```
First transaction: -$50.00 (expense)
CSV Balance column: $4,950.00
Inferred opening: $4,950 - (-$50) = $5,000.00
```

**Note:** Auto-inference works best for checking and savings accounts. Credit card balance semantics vary by bank - you may need to verify and correct using `--set-balance`.

---

## File Mappings

File mappings tell the tool which CSV files belong to which account.

### Automatic Mapping

When you create an account interactively, the CSV file is automatically mapped:

```yaml
accounts:
  chase_checking:
    file_mappings:
      - pattern: "chase_activity_jan2025.csv"
```

### Pattern Matching

Use glob patterns to match multiple files:

```yaml
file_mappings:
  - pattern: "Chase*Activity*.csv"    # Matches Chase_Activity_Jan.csv, ChaseActivity2025.csv, etc.
  - pattern: "chase_*.csv"            # Matches chase_jan.csv, chase_feb.csv, etc.
```

### Specifying Parser

If auto-detection fails, specify the parser:

```yaml
file_mappings:
  - pattern: "statement_*.csv"
    parser: chase
```

### Stale Mapping Cleanup

When mapped files are deleted or moved, the tool offers to clean up:

```
The following file mappings reference non-existent files:
  - old_statement_2023.csv

Remove stale mappings? [Y/n]: Y
Removed 1 stale mapping(s).
```

To skip this prompt:

```bash
financial-consolidator -i ./statements --no-interactive
```

---

## Account Configuration in YAML

### Full Example

```yaml
accounts:
  # Checking account with opening balance
  chase_checking:
    name: Chase Checking ****1234
    type: checking
    institution: Chase
    opening_balance: "5234.56"
    opening_balance_date: "2025-01-01"
    file_mappings:
      - pattern: "Chase*Activity*.csv"
        parser: chase

  # Credit card (no opening balance - will be inferred)
  amex_platinum:
    name: Amex Platinum
    type: credit_card
    institution: American Express
    file_mappings:
      - pattern: "amex_*.csv"

  # Savings with multiple file patterns
  ally_savings:
    name: Ally Savings
    type: savings
    institution: Ally Bank
    opening_balance: "10000.00"
    opening_balance_date: "2024-12-31"
    file_mappings:
      - pattern: "ally_savings_*.csv"
      - pattern: "AllyBank_Export_*.csv"
```

### Credit Card Balance Note

Credit card balance semantics vary by bank:
- Some report balance as positive (amount owed)
- Some report as negative

If inferred balances look wrong, verify and correct with:

```bash
financial-consolidator --set-balance amex_platinum --balance -1234.56 --balance-date 2025-01-01
```

---

## Viewing Account Status

### In Excel Output

The **Account Summary** sheet shows:

| Account | Opening Balance | Total Credits | Total Debits | Closing Balance |
|---------|-----------------|---------------|--------------|-----------------|
| Chase Checking | $5,234.56 | $12,500.00 | -$8,750.00 | $8,984.56 |

### Per-Account Sheets

Each account has its own sheet with:
- Opening balance row (first row)
- All transactions in chronological order
- Running balance column

---

## Validation

Validate your account configuration without processing files:

```bash
financial-consolidator --validate-only
```

This checks:
- YAML syntax is valid
- Required fields are present
- Account types are valid
- File patterns are syntactically correct

---

## Common Tasks

### List All Accounts

Check `config/accounts.yaml` or run:

```bash
financial-consolidator --validate-only
```

### Remove an Account

1. Delete the account section from `config/accounts.yaml`
2. Remove any corrections for that account (optional)

### Merge Duplicate Accounts

1. Update file mappings to point to one account
2. Delete the duplicate account section
3. Re-run analysis

---

## Next Steps

- [Category Corrections](05-category-corrections.md) - Fix transaction categories
- [Output Formats](07-output-formats.md) - Understand the Account Summary sheet
- [Configuration Guide](02-configuration.md) - Full accounts.yaml reference

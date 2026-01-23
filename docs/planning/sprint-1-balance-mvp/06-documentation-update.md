# Task: Update accounts_sample.yaml Documentation

## Objective
Document opening_balance fields with examples and explain the three ways to set them.

## Location
[config/accounts_sample.yaml](config/accounts_sample.yaml)

## Implementation

### Add Header Documentation
At the top of the file, add comprehensive comments:

```yaml
# =============================================================================
# ACCOUNTS CONFIGURATION
# =============================================================================
#
# This file defines your financial accounts and their settings.
#
# OPENING BALANCE
# ---------------
# The opening_balance field sets the starting balance for running balance
# calculations. There are three ways to set it:
#
# 1. CLI Command (recommended for existing accounts):
#    financial-consolidator --set-balance ACCOUNT_ID --balance AMOUNT --balance-date DATE
#    Example: --set-balance chase_checking --balance 5234.56 --balance-date 2024-01-01
#
# 2. Interactive Prompt (during new account creation):
#    When a new file is detected and you create an account interactively,
#    you'll be prompted to enter the opening balance.
#
# 3. Auto-Inference (leave unset):
#    If opening_balance is not set, the system will attempt to infer it
#    from the first transaction's balance column (if available in CSV).
#    Formula: opening_balance = first_balance - first_amount
#    If inference fails, defaults to $0.00.
#
# CREDIT CARD NOTE
# ----------------
# Balance inference works best for asset accounts (checking/savings).
# For credit cards, the "balance" column semantics vary by bank:
# - Some show amount owed (positive = debt)
# - Some show available credit
# If inference produces unexpected results, use --set-balance to correct.
#
# =============================================================================

file_mappings:
  # Map filenames to account IDs
  chase-checking-2024.CSV: chase_checking
  amex-platinum-2024.csv: amex_platinum

accounts:
```

### Add Example with Opening Balance

```yaml
  # Example: Account with explicit opening balance
  chase_checking:
    name: Chase Checking ****1234
    type: checking
    institution: Chase
    # Opening balance set via CLI or interactive prompt
    # This is the balance BEFORE the first transaction in your data
    opening_balance: "5234.56"
    opening_balance_date: "2024-01-01"
```

### Add Example without Opening Balance (Inference)

```yaml
  # Example: Account without opening balance (will be inferred)
  amex_platinum:
    name: Amex Platinum ****5678
    type: credit_card
    institution: American Express
    # opening_balance not set - will be inferred from transaction data
    # If CSV has a Balance column, system calculates:
    #   opening = first_balance - first_amount
    # Otherwise defaults to $0.00
```

### Add Example with Explicit Zero

```yaml
  # Example: Account starting from zero
  new_savings:
    name: New Savings Account
    type: savings
    institution: Local Bank
    # Explicit zero - this account started with no balance
    opening_balance: "0"
    opening_balance_date: "2024-06-01"
```

### Full Sample File Structure

```yaml
# [Header comments as shown above]

file_mappings:
  chase-checking-2024.CSV: chase_checking
  chase-checking-2025.CSV: chase_checking
  amex-platinum-*.csv: amex_platinum
  new-savings-*.csv: new_savings

accounts:
  chase_checking:
    name: Chase Checking ****1234
    type: checking
    institution: Chase
    opening_balance: "5234.56"
    opening_balance_date: "2024-01-01"
    display_order: 1

  amex_platinum:
    name: Amex Platinum ****5678
    type: credit_card
    institution: American Express
    # opening_balance will be inferred from transaction data
    display_order: 2

  new_savings:
    name: New Savings Account
    type: savings
    institution: Local Bank
    opening_balance: "0"
    opening_balance_date: "2024-06-01"
    display_order: 3
```

## Key Files
- [config/accounts_sample.yaml](config/accounts_sample.yaml) - Update this file

## Verification
1. File is valid YAML: `python -c "import yaml; yaml.safe_load(open('config/accounts_sample.yaml'))"`
2. Comments explain all three methods for setting opening balance
3. Examples show:
   - Account with explicit opening_balance
   - Account without opening_balance (inference case)
   - Account with opening_balance: "0" (explicit zero)
4. Credit card note is included
5. Documentation is clear and helpful for new users

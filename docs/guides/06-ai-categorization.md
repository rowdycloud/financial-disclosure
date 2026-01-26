# AI Categorization Guide

The Financial Consolidator can use AI (Claude) to categorize transactions that rules miss or to validate uncertain categorizations. This guide covers setup, cost control, and best practices.

## Prerequisites

### API Key Setup

You need an Anthropic API key:

1. Get your key from [console.anthropic.com](https://console.anthropic.com)
2. Set the environment variable:

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or use a `.env` file in your project directory:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Custom Environment Variable

You can use a different environment variable name in `settings.yaml`:

```yaml
ai:
  api_key_env: MY_CUSTOM_API_KEY
```

---

## AI Modes

### Enable All AI Features

```bash
financial-consolidator -i ./statements --ai
```

This enables both validation and categorization.

### Validate Only

Check low-confidence rule-based categorizations:

```bash
financial-consolidator -i ./statements --ai-validate
```

**What it does:**
- Finds transactions categorized by rules with low confidence
- Asks AI to verify or suggest a better category
- Does NOT touch uncategorized transactions

### Categorize Only

Categorize transactions that rules couldn't match:

```bash
financial-consolidator -i ./statements --ai-categorize
```

**What it does:**
- Finds uncategorized transactions
- Asks AI to suggest a category
- Does NOT re-check rule-based categorizations

---

## Cost Control

AI categorization costs money. The tool provides several safeguards.

### Budget Limit

Set a maximum spend per run:

```bash
# Limit to $10
financial-consolidator -i ./statements --ai --ai-budget 10.00

# Default is $5.00 (from settings.yaml)
```

If the estimated cost exceeds the budget, processing stops with a warning.

### Dry Run (Preview Costs)

See what AI would cost without making API calls:

```bash
financial-consolidator -i ./statements --ai --ai-dry-run
```

Output:
```
AI Categorization Dry Run
─────────────────────────
Transactions to validate: 45
Transactions to categorize: 123
Estimated tokens: 52,000
Estimated cost: $2.34

No API calls made. Remove --ai-dry-run to proceed.
```

### Skip Confirmation Prompt

By default, you're asked to confirm before AI spending:

```
AI categorization will process 168 transactions.
Estimated cost: $2.34 (budget: $10.00)

Proceed? [Y/n]:
```

Skip this prompt for automation:

```bash
financial-consolidator -i ./statements --ai --skip-ai-confirm
```

---

## Confidence Threshold

The confidence threshold determines which transactions get AI attention.

```bash
# Lower threshold = more transactions validated
financial-consolidator -i ./statements --ai-validate --ai-confidence 0.5

# Higher threshold = fewer transactions validated
financial-consolidator -i ./statements --ai-validate --ai-confidence 0.9

# Default is 0.7
```

**How it works:**
- Rule-based categorization assigns a confidence score (0.0 - 1.0)
- Transactions below the threshold are sent to AI for validation
- Higher confidence rules (more specific keywords) have higher scores

---

## Configuration in settings.yaml

```yaml
ai:
  enabled: false                    # Default AI state
  api_key_env: ANTHROPIC_API_KEY   # Environment variable for API key
  budget: 5.00                      # Default budget per run
  confidence_threshold: 0.7         # Default confidence threshold
  model: claude-sonnet-4-5-20250929  # Model to use
```

CLI flags override these settings:

| Setting | CLI Override |
|---------|--------------|
| `enabled` | `--ai` |
| `budget` | `--ai-budget` |
| `confidence_threshold` | `--ai-confidence` |

---

## How AI Categorization Works

### The Process

1. **Collects** transactions needing AI attention
2. **Batches** them for efficient processing
3. **Sends** transaction descriptions to Claude
4. **Receives** category suggestions with confidence
5. **Applies** suggestions above confidence threshold

### What AI Sees

The AI receives:
- Transaction description
- Transaction amount
- Available categories and their descriptions

The AI does NOT see:
- Account details
- Your personal information
- Full transaction history

### Category Suggestions

AI suggestions are stored with source `ai`:

```
Date: 2025-01-15
Description: UBER EATS ORDER
Amount: -$32.50
Category: Dining
Source: ai
Confidence: 0.92
```

---

## Best Practices

### 1. Start with Dry Run

Always preview costs before enabling AI:

```bash
financial-consolidator -i ./statements --ai --ai-dry-run
```

### 2. Use Validation First

Validation is cheaper than categorization - it only checks uncertain cases:

```bash
financial-consolidator -i ./statements --ai-validate
```

### 3. Build Rules for Patterns

If AI consistently categorizes the same merchant, add a rule:

```yaml
# Instead of relying on AI every time
rules:
  - id: rule_uber_eats
    category: dining
    keywords:
      - "UBER EATS"
    priority: 50
```

### 4. Review AI Suggestions

AI isn't perfect. Review the output and:
- Import corrections for wrong suggestions
- Add rules for patterns you notice

### 5. Set Appropriate Budget

For large datasets, set a budget to avoid surprises:

```bash
# Conservative budget for testing
financial-consolidator -i ./statements --ai --ai-budget 2.00

# Higher budget for full analysis
financial-consolidator -i ./statements --ai --ai-budget 20.00
```

---

## Example Workflows

### First-Time Analysis

```bash
# 1. Preview AI costs
financial-consolidator -i ./statements --ai --ai-dry-run

# 2. Run with budget limit
financial-consolidator -i ./statements --ai --ai-budget 5.00 -o report.xlsx

# 3. Review and correct
financial-consolidator --import-corrections report.xlsx

# 4. Re-run without AI (rules + corrections handle it)
financial-consolidator -i ./statements -o report_final.xlsx
```

### Ongoing Analysis

```bash
# Monthly analysis with AI for new merchants
financial-consolidator -i ./new_statements \
  --ai-categorize \
  --ai-budget 2.00 \
  --skip-ai-confirm
```

### CI/CD Pipeline

```bash
# Automated processing without prompts
financial-consolidator -i ./statements \
  --ai \
  --ai-budget 10.00 \
  --skip-ai-confirm \
  --no-interactive \
  -o /output/report.xlsx
```

---

## Troubleshooting

### API Key Not Found

```
Error: ANTHROPIC_API_KEY environment variable not set
```

**Fix:** Set the environment variable or check your `.env` file.

### Budget Exceeded

```
Error: Estimated cost ($15.23) exceeds budget ($10.00)
```

**Fix:** Increase budget with `--ai-budget` or reduce scope with date filters.

### Low-Quality Suggestions

If AI suggestions are poor:
1. Check that `categories.yaml` has good category descriptions
2. Use `--ai-validate` instead of `--ai-categorize`
3. Lower confidence threshold to get more validation

### Rate Limiting

If you hit API rate limits:
1. Wait and retry
2. Use `--ai-budget` to process fewer transactions
3. Use date filtering to reduce scope

---

## Next Steps

- [Category Corrections](05-category-corrections.md) - Fix AI mistakes
- [Configuration Guide](02-configuration.md) - Add rules to reduce AI dependency
- [CLI Reference](08-cli-reference.md) - All AI-related flags

**Project: Financial Transaction Consolidation and Forensic Analysis Tool**

Build a Python utility that consolidates financial transactions from multiple downloaded files into a comprehensive Google Sheets-ready format for forensic financial review.

For parallel-safe implementation tasks, use multiple background agents, validating task completion for each agent by running 'cubic review --json', investigating any findings from the output code review, and instruct the agent to fix valid findings appropriately.

**Core Requirements:**

1. **File Input Support:**
   - CSV files (various bank formats)
   - OFX/QFX files (Quicken/Money formats)
   - PDF bank statements (extract tables)
   - Excel files (XLS/XLSX)
   - Auto-detect file format and institution where possible

2. **Transaction Processing:**
   - Parse date, description, amount, account name/number
   - Handle debits/credits correctly (positive/negative)
   - Detect and flag potential duplicates across files
   - Preserve original data alongside processed data
   - Track source file for each transaction

3. **Account Management:**
   - Allow user to map file → account name
   - Support multiple accounts per institution
   - Track account types (checking, credit card, loan, crypto, etc.)
   - Calculate running balances per account

4. **Transaction Categorization:**
   - Implement rule-based categorization (user-defined keywords)
   - Common categories: Housing, Transportation, Food, Debt Service, Cash Advances, Transfers, Income, etc.
   - Allow manual category assignment
   - Flag uncategorized transactions
   - Support sub-categories

5. **Output Sheets (CSV or Excel format):**
   
   **Sheet 1 - P&L Summary by Month/Year:**
   - Rows: Income categories, Expense categories, Net
   - Columns: Jan 2024, Feb 2024, ..., Dec 2025, Total
   - Include subtotals and grand totals
   
   **Sheet 2 - All Transactions (Master List):**
   - Date, Account, Description, Category, Sub-category, Amount, Balance, Source File, Duplicate Flag
   - Sorted by date (oldest first)
   
   **Sheet 3-N - Per Account Transaction History:**
   - One sheet per account
   - Same columns as master list
   - Running balance column
   
   **Sheet - Category Analysis:**
   - Category spending by month
   - Year-over-year comparison
   - Top merchants by category
   
   **Sheet - Anomaly Detection:**
   - Large transactions (user-defined threshold)
   - Unusual patterns
   - Gaps in transaction dates
   - Cash advances and fees

6. **Configuration:**
   - Config file for category rules (YAML or JSON)
   - Account mappings
   - Date range filtering
   - Amount threshold settings

7. **User Interface:**
   - Command-line interface with clear prompts
   - Progress indicators for large file processing
   - Summary statistics after processing
   - Error handling with clear messages

**Technical Specifications:**
- Python 3.10+
- Use pandas for data manipulation
- Use openpyxl for Excel output
- Use pdfplumber for PDF parsing
- Use ofxparse for OFX files
- Modular code structure
- Comprehensive error handling
- Logging to file for debugging

**Deliverables:**
1. Main processing script
2. Configuration file template
3. README with setup and usage instructions
4. Sample category rules file
5. Requirements.txt for dependencies

**Example Usage:**
```bash
python consolidate_transactions.py --input-dir ./downloads --output ./financial_analysis.xlsx --start-date 2024-01-01 --end-date 2025-12-31
```

Focus on accuracy, auditability, and handling edge cases. The output should be suitable for forensic financial review.
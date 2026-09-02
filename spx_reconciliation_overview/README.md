# SPX Bank Reconciliation Overview — Odoo 19 Enterprise

This add-on provides a Peachtree-style bank reconciliation worksheet using Odoo's natural Enterprise Accounting interface.

## What it does

- Shows bank credits/deposits and bank debits/checks in one clear Odoo list.
- Separates bank-cleared lines, unmatched bank lines, outstanding receipts and outstanding payments.
- Calculates statement ending balance, outstanding checks, deposits in transit, adjusted bank balance, G/L system balance and unreconciled difference.
- Reads native `account.bank.statement`, `account.bank.statement.line`, `account.payment` and `account.move.line` records.
- Opens native Odoo transactions and the Enterprise bank reconciliation client action.
- Provides informational interest-income and service-charge adjustments without posting custom accounting entries.
- Includes a printable landscape PDF reconciliation report.
- Respects Odoo company access and Accounting user permissions.

## Accounting design

This module does **not** replace or modify Odoo's reconciliation engine. A worksheet is a saved reporting snapshot that holds references to native Odoo records. Use **Refresh from Odoo** to rebuild its lines and totals. Use **Open Odoo Reconciliation** for the actual matching and posting.

## Installation on Cloudpepper

1. Copy the `spx_reconciliation_overview` folder into the custom-addons Git repository used by the Odoo 19 Enterprise instance.
2. Commit and push the folder to the branch deployed by Cloudpepper.
3. Wait for the deployment/build to complete.
4. In Odoo, enable developer mode and select **Apps → Update Apps List**.
5. Search for **SPX Bank Reconciliation Overview** in the Apps list.
6. Install the module.
7. Open the new **Bank Reconciliation** app, or use **Accounting → Reconciliation Overview**.

## First use

1. Create a worksheet.
2. Select the company, bank account and either an Odoo bank statement or a manual date range.
3. Enter/confirm the statement ending balance.
4. Save and select **Refresh from Odoo**.
5. Review the worksheet. Use **Open Odoo Reconciliation** to complete native matching.
6. Refresh again to see the updated Odoo status.

Worksheet interest and service-charge amounts are informational previews. After you create and reconcile the corresponding native bank transaction, clear the preview amount and refresh the worksheet so it is not counted twice.

## Requirements

- Odoo 19 Enterprise
- `account`
- `account_accountant`

Version: `19.0.1.0.3`

{
    "name": "SPX Bank Reconciliation Overview",
    "summary": "Peachtree-style bank reconciliation visibility using Odoo's native accounting flow",
    "version": "19.0.1.0.1",
    "category": "Accounting/Accounting",
    "author": "Spxcorp Limited",
    "website": "https://spxcorp.net",
    "license": "LGPL-3",
    "depends": [
        "account",
        "account_accountant",
    ],
    "data": [
        "security/reconciliation_security.xml",
        "security/ir.model.access.csv",
        "views/reconciliation_overview_views.xml",
        "reports/reconciliation_overview_report.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}

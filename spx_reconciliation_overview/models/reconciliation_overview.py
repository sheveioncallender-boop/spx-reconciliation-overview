from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SpxBankReconciliationOverview(models.Model):
    _name = "spx.bank.reconciliation.overview"
    _description = "Bank Reconciliation Overview"
    _order = "statement_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Worksheet",
        compute="_compute_name",
        store=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Bank Account",
        required=True,
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit')), ('company_id', '=', company_id)]",
        index=True,
    )
    statement_id = fields.Many2one(
        comodel_name="account.bank.statement",
        string="Bank Statement",
        check_company=True,
        domain="[('journal_id', '=', journal_id)]",
        index=True,
        help="Optional. Select a native Odoo bank statement to use its lines and ending balance.",
    )
    date_from = fields.Date(
        string="Period Start",
        required=True,
        default=lambda self: self._default_date_from(),
    )
    statement_date = fields.Date(
        string="Statement Date",
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    statement_ending_balance = fields.Monetary(
        string="Statement Ending Balance",
        currency_field="currency_id",
        help="The closing balance shown on the bank statement. Selecting an Odoo statement fills this automatically.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        compute="_compute_currency_id",
        store=True,
        precompute=True,
    )
    line_ids = fields.One2many(
        comodel_name="spx.bank.reconciliation.overview.line",
        inverse_name="overview_id",
        string="Transactions",
        copy=False,
    )
    data_last_refreshed = fields.Datetime(
        string="Last Refreshed",
        readonly=True,
        copy=False,
    )

    # Native Odoo position captured at the last refresh.
    bank_gl_balance = fields.Monetary(
        string="Bank G/L Balance",
        currency_field="currency_id",
        readonly=True,
        copy=False,
        help="Posted balance of the bank journal's liquidity account at the statement date.",
    )
    outstanding_checks = fields.Monetary(
        string="Outstanding Checks",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    deposits_in_transit = fields.Monetary(
        string="Deposits in Transit",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    gl_system_balance = fields.Monetary(
        string="G/L System Balance",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Book cash position: bank G/L balance plus deposits in transit less outstanding checks.",
    )
    adjusted_bank_balance = fields.Monetary(
        string="Adjusted Bank Balance",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )

    # Informational worksheet adjustments. They never post accounting entries.
    interest_income = fields.Monetary(
        string="Interest Income",
        currency_field="currency_id",
        help="Worksheet adjustment only. Use Prepare Native Transaction to create the actual Odoo bank transaction.",
    )
    interest_date = fields.Date(
        string="Interest Date",
        default=fields.Date.context_today,
    )
    interest_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Interest Account",
        check_company=True,
        domain="[('company_ids', 'in', [company_id]), ('active', '=', True)]",
    )
    service_charges = fields.Monetary(
        string="Service Charges",
        currency_field="currency_id",
        help="Worksheet adjustment only. Use Prepare Native Transaction to create the actual Odoo bank transaction.",
    )
    service_charge_date = fields.Date(
        string="Charge Date",
        default=fields.Date.context_today,
    )
    service_charge_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Bank Charge Account",
        check_company=True,
        domain="[('company_ids', 'in', [company_id]), ('active', '=', True)]",
    )
    adjusted_gl_balance = fields.Monetary(
        string="Adjusted G/L Balance",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    difference = fields.Monetary(
        string="Unreconciled Difference",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )

    line_count = fields.Integer(
        string="Transactions",
        compute="_compute_totals",
        store=True,
    )
    cleared_deposit_count = fields.Integer(
        string="Cleared Deposits",
        compute="_compute_totals",
        store=True,
    )
    cleared_deposit_amount = fields.Monetary(
        string="Cleared Deposit Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    cleared_check_count = fields.Integer(
        string="Cleared Checks",
        compute="_compute_totals",
        store=True,
    )
    cleared_check_amount = fields.Monetary(
        string="Cleared Check Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    outstanding_count = fields.Integer(
        string="Outstanding Items",
        compute="_compute_totals",
        store=True,
    )
    unmatched_bank_count = fields.Integer(
        string="Unmatched Bank Lines",
        compute="_compute_totals",
        store=True,
    )
    is_reconciled = fields.Boolean(
        string="Reconciled",
        compute="_compute_totals",
        store=True,
    )
    reconciliation_state = fields.Selection(
        selection=[
            ("not_refreshed", "Not Refreshed"),
            ("difference", "Difference Remaining"),
            ("needs_matching", "Needs Odoo Matching"),
            ("reconciled", "Reconciled"),
        ],
        string="Status",
        compute="_compute_totals",
        store=True,
    )

    @api.model
    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1)

    @api.depends("journal_id", "statement_date")
    def _compute_name(self):
        for record in self:
            if record.journal_id and record.statement_date:
                record.name = _(
                    "%(journal)s - %(date)s",
                    journal=record.journal_id.display_name,
                    date=fields.Date.to_string(record.statement_date),
                )
            else:
                record.name = _("New Reconciliation Worksheet")

    @api.depends("journal_id.currency_id", "company_id.currency_id")
    def _compute_currency_id(self):
        for record in self:
            record.currency_id = record.journal_id.currency_id or record.company_id.currency_id

    @api.depends(
        "line_ids.transaction_type",
        "line_ids.amount",
        "line_ids.is_cleared",
        "line_ids.native_status",
        "statement_ending_balance",
        "bank_gl_balance",
        "interest_income",
        "service_charges",
        "data_last_refreshed",
        "currency_id",
    )
    def _compute_totals(self):
        for record in self:
            cleared_deposits = record.line_ids.filtered(
                lambda line: line.transaction_type == "deposit" and line.is_cleared
            )
            cleared_checks = record.line_ids.filtered(
                lambda line: line.transaction_type == "check" and line.is_cleared
            )
            outstanding_receipts = record.line_ids.filtered(
                lambda line: line.native_status == "outstanding_receipt"
            )
            outstanding_payments = record.line_ids.filtered(
                lambda line: line.native_status == "outstanding_payment"
            )
            unmatched_bank_lines = record.line_ids.filtered(
                lambda line: line.native_status == "bank_unmatched"
            )

            record.line_count = len(record.line_ids)
            record.cleared_deposit_count = len(cleared_deposits)
            record.cleared_deposit_amount = sum(cleared_deposits.mapped("amount"))
            record.cleared_check_count = len(cleared_checks)
            record.cleared_check_amount = sum(cleared_checks.mapped("amount"))
            record.deposits_in_transit = sum(outstanding_receipts.mapped("amount"))
            record.outstanding_checks = sum(outstanding_payments.mapped("amount"))
            record.outstanding_count = len(outstanding_receipts | outstanding_payments)
            record.unmatched_bank_count = len(unmatched_bank_lines)

            record.gl_system_balance = (
                record.bank_gl_balance
                + record.deposits_in_transit
                - record.outstanding_checks
            )
            record.adjusted_bank_balance = (
                record.statement_ending_balance
                - record.outstanding_checks
                + record.deposits_in_transit
            )
            record.adjusted_gl_balance = (
                record.gl_system_balance
                + record.interest_income
                - record.service_charges
            )
            record.difference = record.adjusted_bank_balance - record.adjusted_gl_balance

            zero_difference = bool(
                record.currency_id and record.currency_id.is_zero(record.difference)
            )
            record.is_reconciled = bool(
                record.data_last_refreshed
                and zero_difference
                and not record.unmatched_bank_count
            )
            if not record.data_last_refreshed:
                record.reconciliation_state = "not_refreshed"
            elif not zero_difference:
                record.reconciliation_state = "difference"
            elif record.unmatched_bank_count:
                record.reconciliation_state = "needs_matching"
            else:
                record.reconciliation_state = "reconciled"

    @api.onchange("company_id")
    def _onchange_company_id(self):
        if self.journal_id and self.journal_id.company_id != self.company_id:
            self.journal_id = False
        self.statement_id = False
        self.line_ids = [Command.clear()]

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        if self.journal_id:
            self.company_id = self.journal_id.company_id
        self.statement_id = False
        self.statement_ending_balance = 0.0
        self.line_ids = [Command.clear()]

    @api.onchange("statement_id")
    def _onchange_statement_id(self):
        if not self.statement_id:
            return
        statement = self.statement_id
        self.journal_id = statement.journal_id
        self.company_id = statement.company_id
        self.statement_ending_balance = statement.balance_end_real
        statement_dates = statement.line_ids.mapped("date")
        if statement_dates:
            self.date_from = min(statement_dates)
            self.statement_date = max(statement_dates)
        elif statement.date:
            self.statement_date = statement.date

    @api.constrains("date_from", "statement_date")
    def _check_dates(self):
        for record in self:
            if record.date_from and record.statement_date and record.date_from > record.statement_date:
                raise ValidationError(_("The period start cannot be after the statement date."))

    @api.constrains("journal_id", "company_id", "statement_id")
    def _check_company_and_statement(self):
        for record in self:
            if record.journal_id.company_id != record.company_id:
                raise ValidationError(_("The bank account must belong to the selected company."))
            if record.statement_id and record.statement_id.journal_id != record.journal_id:
                raise ValidationError(_("The bank statement must belong to the selected bank account."))

    def _amount_in_overview_currency(self, move_line, residual=False):
        """Return a move-line amount in the worksheet/journal currency."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        currency = self.currency_id
        if residual:
            if currency == company_currency:
                return move_line.amount_residual
            if move_line.currency_id == currency:
                return move_line.amount_residual_currency
            return company_currency._convert(
                move_line.amount_residual,
                currency,
                self.company_id,
                move_line.date or self.statement_date,
            )
        if currency == company_currency:
            return move_line.balance
        if move_line.currency_id == currency:
            return move_line.amount_currency
        return company_currency._convert(
            move_line.balance,
            currency,
            self.company_id,
            move_line.date or self.statement_date,
        )

    def _get_bank_gl_balance(self):
        self.ensure_one()
        liquidity_account = self.journal_id.default_account_id
        if not liquidity_account:
            raise UserError(
                _(
                    "The bank journal %(journal)s has no default liquidity account configured.",
                    journal=self.journal_id.display_name,
                )
            )
        move_lines = self.env["account.move.line"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("account_id", "=", liquidity_account.id),
                ("parent_state", "=", "posted"),
                ("date", "<=", self.statement_date),
            ]
        )
        return sum(self._amount_in_overview_currency(line) for line in move_lines)

    def _prepare_bank_statement_line_values(self, bank_line):
        self.ensure_one()
        amount = bank_line.amount
        transaction_type = "deposit" if amount >= 0.0 else "check"
        return {
            "overview_id": self.id,
            "date": bank_line.date,
            "reference": (
                bank_line.payment_ref
                or bank_line.move_id.ref
                or bank_line.move_id.name
                or _("Bank Transaction")
            ),
            "partner_id": bank_line.partner_id.id,
            "description": bank_line.partner_name or bank_line.transaction_type or bank_line.payment_ref,
            "transaction_type": transaction_type,
            "amount": abs(amount),
            "is_cleared": bank_line.is_reconciled,
            "native_status": "bank_cleared" if bank_line.is_reconciled else "bank_unmatched",
            "source_type": "bank_transaction",
            "bank_statement_line_id": bank_line.id,
            "statement_id": bank_line.statement_id.id,
        }

    def _prepare_outstanding_payment_values(self, payment, liquidity_lines):
        self.ensure_one()
        amount = abs(
            sum(
                self._amount_in_overview_currency(line, residual=True)
                for line in liquidity_lines
            )
        )
        transaction_type = "deposit" if payment.payment_type == "inbound" else "check"
        native_status = (
            "outstanding_receipt"
            if payment.payment_type == "inbound"
            else "outstanding_payment"
        )
        return {
            "overview_id": self.id,
            "date": payment.date,
            "reference": (
                payment.payment_reference
                or payment.name
                or payment.memo
                or payment.move_id.name
                or _("Payment")
            ),
            "partner_id": payment.partner_id.id,
            "description": payment.memo or liquidity_lines[:1].name,
            "transaction_type": transaction_type,
            "amount": amount,
            "is_cleared": False,
            "native_status": native_status,
            "source_type": "payment",
            "payment_id": payment.id,
            "move_line_id": liquidity_lines[:1].id,
        }

    def action_refresh(self):
        for record in self:
            if not record.journal_id or not record.statement_date:
                raise UserError(_("Select a bank account and statement date before refreshing."))

            if record.statement_id:
                bank_line_domain = [("statement_id", "=", record.statement_id.id)]
                record.statement_ending_balance = record.statement_id.balance_end_real
            else:
                bank_line_domain = [
                    ("journal_id", "=", record.journal_id.id),
                    ("company_id", "=", record.company_id.id),
                    ("state", "=", "posted"),
                    ("date", ">=", record.date_from),
                    ("date", "<=", record.statement_date),
                ]
            bank_lines = self.env["account.bank.statement.line"].search(
                bank_line_domain,
                order="date, id",
            )

            payment_domain = [
                ("journal_id", "=", record.journal_id.id),
                ("company_id", "=", record.company_id.id),
                ("date", "<=", record.statement_date),
                ("state", "not in", ("draft", "canceled", "rejected")),
                ("move_id", "!=", False),
                ("outstanding_account_id", "!=", False),
            ]
            payments = self.env["account.payment"].search(payment_domain, order="date, id")

            record.line_ids.unlink()
            line_values = [
                record._prepare_bank_statement_line_values(bank_line)
                for bank_line in bank_lines
            ]
            for payment in payments:
                liquidity_lines = payment.move_id.line_ids.filtered(
                    lambda line: (
                        line.account_id == payment.outstanding_account_id
                        and not line.reconciled
                    )
                )
                if not liquidity_lines:
                    continue
                values = record._prepare_outstanding_payment_values(payment, liquidity_lines)
                if not record.currency_id.is_zero(values["amount"]):
                    line_values.append(values)

            if line_values:
                self.env["spx.bank.reconciliation.overview.line"].create(line_values)
            record.write(
                {
                    "bank_gl_balance": record._get_bank_gl_balance(),
                    "data_last_refreshed": fields.Datetime.now(),
                }
            )
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open_native_reconciliation(self):
        self.ensure_one()
        client_action = self.env["ir.actions.client"].search(
            [("tag", "=", "bank_statement_reconciliation_view")],
            limit=1,
        )
        if client_action:
            context = {
                **self.env.context,
                "journal_id": self.journal_id.id,
                "default_journal_id": self.journal_id.id,
            }
            if self.statement_id:
                context["statement_line_ids"] = self.statement_id.line_ids.ids
            return {
                "type": "ir.actions.client",
                "name": _("Bank Reconciliation"),
                "tag": "bank_statement_reconciliation_view",
                "context": context,
            }
        return self.action_find_missing_transactions()

    def action_find_missing_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Unmatched Bank Transactions"),
            "res_model": "account.bank.statement.line",
            "view_mode": "list,form",
            "domain": [
                ("journal_id", "=", self.journal_id.id),
                ("company_id", "=", self.company_id.id),
                ("date", "<=", self.statement_date),
                ("is_reconciled", "=", False),
            ],
            "context": {
                "default_journal_id": self.journal_id.id,
                "search_default_journal_id": self.journal_id.id,
            },
        }

    def action_view_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reconciliation Transactions"),
            "res_model": "spx.bank.reconciliation.overview.line",
            "view_mode": "list,form",
            "domain": [("overview_id", "=", self.id)],
            "context": {"create": False, "delete": False},
        }

    def _open_native_adjustment_transaction(self, amount, transaction_date, label):
        self.ensure_one()
        if not amount:
            raise UserError(_("Enter an amount before preparing the native transaction."))
        return {
            "type": "ir.actions.act_window",
            "name": label,
            "res_model": "account.bank.statement.line",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_journal_id": self.journal_id.id,
                "default_company_id": self.company_id.id,
                "default_date": transaction_date or self.statement_date,
                "default_amount": amount,
                "default_payment_ref": label,
            },
        }

    def action_prepare_interest_transaction(self):
        self.ensure_one()
        return self._open_native_adjustment_transaction(
            self.interest_income,
            self.interest_date,
            _("Interest Income"),
        )

    def action_prepare_charge_transaction(self):
        self.ensure_one()
        return self._open_native_adjustment_transaction(
            -self.service_charges,
            self.service_charge_date,
            _("Bank Service Charge"),
        )


class SpxBankReconciliationOverviewLine(models.Model):
    _name = "spx.bank.reconciliation.overview.line"
    _description = "Bank Reconciliation Overview Transaction"
    _order = "date desc, id desc"
    _rec_name = "reference"
    _check_company_auto = True

    overview_id = fields.Many2one(
        comodel_name="spx.bank.reconciliation.overview",
        string="Worksheet",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="overview_id.company_id",
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="overview_id.currency_id",
        store=True,
    )
    date = fields.Date(required=True, index=True)
    reference = fields.Char(required=True, index="trigram")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Payee / Partner",
        ondelete="set null",
    )
    description = fields.Char(string="Description")
    transaction_type = fields.Selection(
        selection=[
            ("deposit", "Deposit / Bank Credit"),
            ("check", "Check / Bank Debit"),
        ],
        required=True,
        index=True,
    )
    amount = fields.Monetary(
        required=True,
        currency_field="currency_id",
    )
    deposit_amount = fields.Monetary(
        string="Deposit / Bank Credit",
        compute="_compute_split_amounts",
        store=True,
        currency_field="currency_id",
    )
    check_amount = fields.Monetary(
        string="Check / Bank Debit",
        compute="_compute_split_amounts",
        store=True,
        currency_field="currency_id",
    )
    is_cleared = fields.Boolean(
        string="Bank Cleared",
        readonly=True,
    )
    native_status = fields.Selection(
        selection=[
            ("bank_cleared", "Bank Cleared"),
            ("bank_unmatched", "Bank Line Unmatched"),
            ("outstanding_receipt", "Outstanding Receipt"),
            ("outstanding_payment", "Outstanding Payment"),
        ],
        string="Odoo Status",
        required=True,
        index=True,
    )
    source_type = fields.Selection(
        selection=[
            ("bank_transaction", "Bank Transaction"),
            ("payment", "Payment"),
        ],
        string="Source",
        required=True,
    )
    bank_statement_line_id = fields.Many2one(
        comodel_name="account.bank.statement.line",
        string="Bank Transaction",
        ondelete="set null",
        check_company=True,
    )
    statement_id = fields.Many2one(
        comodel_name="account.bank.statement",
        string="Statement",
        ondelete="set null",
        check_company=True,
    )
    payment_id = fields.Many2one(
        comodel_name="account.payment",
        string="Payment",
        ondelete="set null",
        check_company=True,
    )
    move_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Journal Item",
        ondelete="set null",
        check_company=True,
    )

    @api.depends("transaction_type", "amount")
    def _compute_split_amounts(self):
        for line in self:
            line.deposit_amount = line.amount if line.transaction_type == "deposit" else 0.0
            line.check_amount = line.amount if line.transaction_type == "check" else 0.0

    def action_open_source(self):
        self.ensure_one()
        if self.bank_statement_line_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Bank Transaction"),
                "res_model": "account.bank.statement.line",
                "view_mode": "form",
                "res_id": self.bank_statement_line_id.id,
                "target": "current",
            }
        if self.payment_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Payment"),
                "res_model": "account.payment",
                "view_mode": "form",
                "res_id": self.payment_id.id,
                "target": "current",
            }
        if self.move_line_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Journal Entry"),
                "res_model": "account.move",
                "view_mode": "form",
                "res_id": self.move_line_id.move_id.id,
                "target": "current",
            }
        raise UserError(_("The native source record is no longer available."))

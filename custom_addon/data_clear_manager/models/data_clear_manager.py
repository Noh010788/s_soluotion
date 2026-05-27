from psycopg2 import sql

from odoo import _, fields, models
from odoo.exceptions import UserError


class DataClearManager(models.TransientModel):
    _name = "data.clear.manager"
    _description = "Data Clear Manager"

    clear_target = fields.Selection(
        [
            ("sale", "Sale"),
            ("purchase", "Purchase"),
            ("inventory", "Inventory"),
            ("rental", "Rental"),
            ("maintenance", "Maintenance"),
            ("accounting", "Accounting"),
        ],
        string="Data Type",
        readonly=True,
    )
    confirm_text = fields.Char(string="Confirmation")
    result_message = fields.Text(string="Result", readonly=True)

    def action_open_sale_clear(self):
        return self._open_confirm("sale")

    def action_open_purchase_clear(self):
        return self._open_confirm("purchase")

    def action_open_inventory_clear(self):
        return self._open_confirm("inventory")

    def action_open_rental_clear(self):
        return self._open_confirm("rental")

    def action_open_maintenance_clear(self):
        return self._open_confirm("maintenance")

    def action_open_accounting_clear(self):
        return self._open_confirm("accounting")

    def action_clear_data(self):
        self.ensure_one()
        if self.confirm_text != "CLEAR":
            raise UserError(_("Type CLEAR to confirm this operation."))
        if not self.clear_target:
            raise UserError(_("Please select data to clear."))

        clear_method = getattr(self, f"_clear_{self.clear_target}")
        deleted_count = clear_method()
        self.result_message = _("Cleared %(count)s record(s).") % {"count": deleted_count}
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Clear Data"),
                "message": self.result_message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _open_confirm(self, target):
        wizard = self.create({"clear_target": target})
        return {
            "name": _("Confirm Clear Data"),
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _table_exists(self, table):
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = %s
            """,
            [table],
        )
        return bool(self.env.cr.fetchone())

    def _column_exists(self, table, column):
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = %s
               AND column_name = %s
            """,
            [table, column],
        )
        return bool(self.env.cr.fetchone())

    def _delete_all(self, table):
        if not self._table_exists(table):
            return 0
        self.env.cr.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))
        return self.env.cr.rowcount

    def _delete_where(self, table, where_sql, params=None):
        if not self._table_exists(table):
            return 0
        self.env.cr.execute(
            sql.SQL("DELETE FROM {} WHERE ").format(sql.Identifier(table)) + sql.SQL(where_sql),
            params or [],
        )
        return self.env.cr.rowcount

    def _clear_chatter(self, model, record_ids):
        if not record_ids:
            return 0
        deleted = 0
        deleted += self._delete_where(
            "mail_activity",
            "res_model = %s AND res_id = ANY(%s)",
            [model, record_ids],
        )
        deleted += self._delete_where(
            "mail_message",
            "model = %s AND res_id = ANY(%s)",
            [model, record_ids],
        )
        return deleted

    def _fetch_ids(self, query, params=None):
        self.env.cr.execute(query, params or [])
        return [row[0] for row in self.env.cr.fetchall()]

    def _reset_sequences(self, codes):
        if not self._table_exists("ir_sequence"):
            return
        self.env.cr.execute(
            """
            UPDATE ir_sequence
               SET number_next = 1
             WHERE code = ANY(%s)
            """,
            [codes],
        )

    def _clear_sale_orders(self, order_type):
        operator = "=" if order_type == "rental" else "!="
        order_ids = self._fetch_ids(
            f"SELECT id FROM sale_order WHERE COALESCE(order_type, 'sale') {operator} %s",
            ["rental"],
        )
        if not order_ids:
            return 0

        line_ids = self._fetch_ids("SELECT id FROM sale_order_line WHERE order_id = ANY(%s)", [order_ids])
        self._clear_chatter("sale.order", order_ids)
        if line_ids:
            self._clear_chatter("sale.order.line", line_ids)

        if order_type == "rental":
            maintenance_ids = self._fetch_ids(
                "SELECT id FROM maintenance_request WHERE rental_order_id = ANY(%s)",
                [order_ids],
            )
            self._clear_chatter("maintenance.request", maintenance_ids)
            self._delete_where("maintenance_request", "id = ANY(%s)", [maintenance_ids])

        self._delete_where("sale_order", "id = ANY(%s)", [order_ids])
        self._reset_sequences(["sale.order"])
        return len(order_ids)

    def _clear_sale(self):
        return self._clear_sale_orders("sale")

    def _clear_rental(self):
        return self._clear_sale_orders("rental")

    def _clear_purchase(self):
        order_ids = self._fetch_ids("SELECT id FROM purchase_order")
        if not order_ids:
            return 0

        line_ids = self._fetch_ids("SELECT id FROM purchase_order_line WHERE order_id = ANY(%s)", [order_ids])
        self._clear_chatter("purchase.order", order_ids)
        if line_ids:
            self._clear_chatter("purchase.order.line", line_ids)
        self._delete_where("purchase_order", "id = ANY(%s)", [order_ids])
        self._reset_sequences(["purchase.order"])
        return len(order_ids)

    def _clear_maintenance(self):
        request_ids = self._fetch_ids("SELECT id FROM maintenance_request")
        if not request_ids:
            return 0
        self._clear_chatter("maintenance.request", request_ids)
        self._delete_where("maintenance_request", "id = ANY(%s)", [request_ids])
        return len(request_ids)

    def _clear_inventory(self):
        picking_ids = self._fetch_ids("SELECT id FROM stock_picking")
        move_ids = self._fetch_ids("SELECT id FROM stock_move")
        move_line_ids = self._fetch_ids("SELECT id FROM stock_move_line")
        deleted = len(picking_ids) + len(move_ids) + len(move_line_ids)

        self._clear_chatter("stock.picking", picking_ids)
        self._clear_chatter("stock.move", move_ids)
        self._clear_chatter("stock.move.line", move_line_ids)

        for table in [
            "stock_move_line_consume_rel",
            "stock_conflict_quant_rel",
            "stock_inventory_adjustment_name_stock_quant_rel",
            "stock_inventory_conflict_stock_quant_rel",
            "stock_inventory_warning_stock_quant_rel",
            "stock_quant_stock_quant_relocate_rel",
            "stock_quant_stock_request_count_rel",
            "stock_quant_stock_track_confirmation_rel",
            "stock_picking_backorder_rel",
            "purchase_order_stock_picking_rel",
            "stock_picking_sms_rel",
            "stock_move_move_rel",
            "stock_move_created_purchase_line_rel",
            "stock_route_move",
            "account_analytic_line_stock_move_rel",
        ]:
            self._delete_all(table)

        for table in [
            "stock_return_picking_line",
            "stock_return_picking",
            "stock_backorder_confirmation_line",
            "stock_backorder_confirmation",
            "stock_package_level",
            "stock_scrap",
            "stock_valuation_layer",
            "stock_move_line",
            "stock_move",
            "stock_picking",
            "stock_quant",
            "stock_quant_package",
            "stock_inventory_adjustment_name",
            "stock_inventory_conflict",
            "stock_inventory_warning",
            "stock_warn_insufficient_qty_scrap",
            "stock_track_line",
            "stock_track_confirmation",
            "stock_warehouse_orderpoint",
            "stock_orderpoint_snooze",
        ]:
            if table in {"stock_move", "stock_picking"}:
                deleted += max(self._delete_all(table) - (len(move_ids) if table == "stock_move" else len(picking_ids)), 0)
            else:
                self._delete_all(table)

        self._reset_sequences(["stock.picking"])
        return deleted

    def _clear_accounting(self):
        move_ids = self._fetch_ids("SELECT id FROM account_move")
        payment_ids = self._fetch_ids("SELECT id FROM account_payment")
        deleted = len(move_ids) + len(payment_ids)

        self._clear_chatter("account.move", move_ids)
        self._clear_chatter("account.payment", payment_ids)

        for table in [
            "account_partial_reconcile",
            "account_full_reconcile",
            "account_payment_account_bank_statement_line_rel",
            "account_move__account_payment",
            "account_invoice_transaction_rel",
            "account_move_account_move_send_batch_wizard_rel",
            "account_move_account_resequence_wizard_rel",
            "account_move_validate_account_move_rel",
            "account_move_reversal_move",
            "account_move_reversal_new_move",
            "account_payment_register_move_line_rel",
            "sale_order_line_invoice_rel",
        ]:
            self._delete_all(table)

        if self._column_exists("res_company", "account_opening_move_id"):
            self.env.cr.execute("UPDATE res_company SET account_opening_move_id = NULL")

        self._delete_all("account_bank_statement_line")
        self._delete_all("account_bank_statement")
        self._delete_all("account_payment")
        self._delete_all("account_move")
        self._delete_all("account_analytic_line")

        for table in [
            "account_move_send_wizard",
            "account_move_send_batch_wizard",
            "account_resequence_wizard",
            "account_move_reversal",
            "account_payment_register",
            "account_automatic_entry_wizard",
            "account_secure_entries_wizard",
            "account_autopost_bills_wizard",
            "account_accrued_orders_wizard",
        ]:
            self._delete_all(table)

        self._reset_sequences(["account.payment"])
        return deleted

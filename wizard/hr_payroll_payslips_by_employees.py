import logging

from odoo import _, fields, models
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    _name = "hr.payslip.employees"
    _description = "Generate payslips for all selected employees"

    employee_ids = fields.Many2many(
        "hr.employee", "hr_employee_group_rel", "payslip_id", "employee_id", "Employees"
    )

    def compute_sheet(self):
        _logger = logging.getLogger(__name__)
        payslips = self.env["hr.payslip"]
        [data] = self.read()
        active_id = self.env.context.get("active_id")
        if not active_id:
            raise UserError(
                _("No active Payslip Batch found. Open the wizard from a batch.")
            )
        if active_id:
            [run_data] = (
                self.env["hr.payslip.run"]
                .browse(active_id)
                .read(["date_start", "date_end", "credit_note", "struct_id"])
            )
        from_date = run_data.get("date_start")
        to_date = run_data.get("date_end")
        struct_id = run_data.get("struct_id")
        if not data["employee_ids"]:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        for employee in self.env["hr.employee"].browse(data["employee_ids"]):
            slip_data = self.env["hr.payslip"].get_payslip_vals(
                from_date, to_date, employee.id, contract_id=False, struct_id=struct_id
            )
            input_lines = slip_data["value"].get("input_line_ids") or []
            worked_days_lines = slip_data["value"].get("worked_days_line_ids") or []
            contract_id = slip_data["value"].get("contract_id") or False
            # fallback: nếu get_payslip_vals không trả về struct_id, dùng struct của batch
            batch_struct = None
            try:
                if hasattr(struct_id, "id"):
                    batch_struct = struct_id.id
                elif isinstance(struct_id, (list, tuple)):
                    batch_struct = struct_id[0]
                else:
                    batch_struct = struct_id
            except Exception:
                batch_struct = struct_id
            struct_id_val = slip_data["value"].get("struct_id") or batch_struct or False
            res = {
                "employee_id": employee.id,
                "name": slip_data["value"].get("name"),
                "struct_id": struct_id_val,
                "contract_id": contract_id,
                "payslip_run_id": active_id,
                "input_line_ids": [(0, 0, x) for x in input_lines],
                "worked_days_line_ids": [(0, 0, x) for x in worked_days_lines],
                "date_from": from_date,
                "date_to": to_date,
                "credit_note": run_data.get("credit_note"),
                "company_id": employee.company_id.id,
            }
            _logger.info(
                "Creating payslip for employee %s with values: %s", employee.id, res
            )
            payslips += self.env["hr.payslip"].create(res)
        payslips._compute_name()
        # Tự động compute và xác nhận từng payslip để tránh lỗi singleton
        payslips.compute_sheet()
        for slip in payslips:
            slip.with_context(without_compute_sheet=True).action_payslip_done()
        return {"type": "ir.actions.act_window_close"}

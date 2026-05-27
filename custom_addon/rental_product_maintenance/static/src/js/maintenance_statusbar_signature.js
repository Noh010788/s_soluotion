/** @odoo-module **/

import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(StatusBarField.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.orm = useService("orm");
    },

    async selectItem(item) {
        const { name, record } = this.props;
        if (record.resModel === "maintenance.request" && name === "stage_id" && record.resId) {
            const [stage] = await this.orm.read("maintenance.stage", [item.value], ["done"]);
            if (stage?.done) {
                const [request] = await this.orm.read(
                    "maintenance.request",
                    [record.resId],
                    ["customer_accepted", "customer_signature"]
                );
                if (!request?.customer_accepted || !request?.customer_signature) {
                    return this.actionService.doAction({
                        name: _t("Accept & Sign"),
                        type: "ir.actions.act_window",
                        res_model: "rental.maintenance.accept.sign.wizard",
                        views: [[false, "form"]],
                        target: "new",
                        context: {
                            default_request_id: record.resId,
                            default_target_stage_id: item.value,
                        },
                    });
                }
            }
        }
        return super.selectItem(item);
    },
});

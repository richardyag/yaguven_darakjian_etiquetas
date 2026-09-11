/** @odoo-module **/

/* The New button on the product views opens the guided wizard instead of the bare form.
 *
 * Why intercept it rather than add a second entry point: whoever loads a product will use
 * the button that is there, not the one further down the menu. If the guided path is a
 * separate menu item it simply does not get used, and the loading stays as it is -- 81%
 * of the watches printing one cell or none.
 *
 * A family with no setup yet opens the wizard with no attribute lines and creates the
 * product all the same, so nothing that can be loaded today stops being loadable. */

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";

const WIZARD = "yaguven_darakjian_etiquetas.action_yag_product_wizard";

// Guards against "Component is destroyed": the wizard can close after this controller's
// own component was already torn down by another action landing at the same time (found
// 2026-09-11 -- an UncaughtPromiseError left the wizard dialog stuck open, and a second
// click on "Create product" on that same dialog created a duplicate product).
function safeReload(model) {
    try {
        const result = model.load();
        if (result && typeof result.catch === "function") {
            result.catch(() => {});
        }
    } catch (_e) {
        // component already gone -- nothing to reload
    }
}

class GuidedListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }
    async createRecord() {
        return this.actionService.doAction(WIZARD, {
            onClose: () => safeReload(this.model),
        });
    }
}

class GuidedKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }
    async createRecord() {
        return this.actionService.doAction(WIZARD, {
            onClose: () => safeReload(this.model),
        });
    }
}

registry.category("views").add("product_guided_list", {
    ...listView,
    Controller: GuidedListController,
});
registry.category("views").add("product_guided_kanban", {
    ...kanbanView,
    Controller: GuidedKanbanController,
});

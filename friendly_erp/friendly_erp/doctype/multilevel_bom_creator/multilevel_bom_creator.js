// Copyright (c) 2025, iMORPHr Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Multilevel BOM Creator", {
    refresh(frm) {
        setup_bom_creator(frm);
    },

    rm_cost_as_per(frm) {
        set_plc_conversion_rate_from_price_list(frm);
    },

    buying_price_list(frm) {
        set_plc_conversion_rate_from_price_list(frm);
    }
});

function set_plc_conversion_rate_from_price_list(frm) {
    if (frm.doc.rm_cost_as_per !== "Price List") {
        return;
    }

    const price_list = frm.doc.buying_price_list;
    const company_currency = frm.doc.company_currency;

    if (!price_list || !company_currency) {
        return;
    }

    frappe.db.get_value("Price List", price_list, "currency")
        .then(r => {
            const price_list_currency = r?.message?.currency;
            if (!price_list_currency) return;

            if (price_list_currency === company_currency) {
                frm.set_value("plc_conversion_rate", 1);
                frm.set_df_property("plc_conversion_rate", "description", "");
            } else {
                frm.set_value("plc_conversion_rate", null);
                frm.set_df_property("plc_conversion_rate", "description", `1 ${price_list_currency} = [?] ${company_currency}`);
            }
        });
}

function setup_bom_creator(frm) {
    frm._tree_helper = new BOMTreeHelper(frm);
    frm._tree_helper.reset_tree_html();
    if (!frm.is_new()) {
        fetch_bom_tree_data(frm, frm._tree_helper);
    } else {
        make_new_entry(frm);
    }
}

function make_new_entry(frm) {
    const dialog = new NewFormDialogFactory(frm, on_new_document_creation_requested).create();
    dialog.show();
}

function on_new_document_creation_requested(new_doc, frm) {
    new_doc.doctype = frm.doc.doctype;
    frappe.db.insert(new_doc).then((saved_doc) => {
        frappe.set_route("Form", saved_doc.doctype, saved_doc.name);
    });
}

function fetch_bom_tree_data(frm, tree_helper) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.get_tree_flat",
        args: {
            multilevel_bom_creator_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __("Loading BOM structure..."),
        callback: function (r) {
            if (!r.exc && r.message) {
                tree_helper.render_tree(r.message);
            }
        }
    });
}

//============ Tree item handlers ============
function show_add_item_dialog(frm, parent, full_data_ctx) {
    const dialog = new NewChildItemDialogFactory(
        frm,
        (values, frm) => {
            add_item(frm, parent, values);
            dialog.hide();
        },
        "ITEM",
        "ADD",
        parent
    ).create();
    dialog.show();
}

function show_add_new_sub_assembly_dialog(frm, parent, full_data_ctx) {
    const dialog = new NewChildItemDialogFactory(
        frm,
        (values, frm) => {
            add_new_sub_assembly(frm, parent, values);
            dialog.hide();
        },
        "NEW_SUB_ASSEMBLY",
        "ADD",
        parent
    ).create();
    dialog.show();
}

function show_add_existing_sub_assembly_dialog(frm, parent, full_data_ctx) {
    const dialog = new NewChildItemDialogFactory(
        frm,
        (values, frm) => {
            add_existing_sub_assembly(frm, parent, values);
            dialog.hide();
        },
        "EXISTING_SUB_ASSEMBLY",
        "ADD",
        parent
    ).create();
    dialog.show();
}

function show_add_operation_dialog(frm, parent, full_data_ctx) {
    const dialog = new NewChildOperationDialogFactory(frm, (values, frm) => {
        add_operation(frm, parent, values);
        dialog.hide();
    },
        "ADD",
        parent).create();
    dialog.show();
}

function show_update_dialog(frm, ctx, full_data_ctx) {
    const parent = ctx.parent_node_unique_id ? full_data_ctx[ctx.parent_node_unique_id] : null;
    if (ctx.node_type === "ITEM") {
        show_update_item_dialog(frm, ctx, parent);
    } else if (ctx.node_type === "SUB_ASSEMBLY") {
        if (ctx.is_preexisting_bom) {
            show_update_existing_sub_assembly_dialog(frm, ctx, parent);
        } else {
            show_update_new_sub_assembly_dialog(frm, ctx, parent);
        }
    } else if (ctx.node_type === "OPERATION") {
        show_update_operation_dialog(frm, ctx, parent);
    }
}

function show_update_item_dialog(frm, ctx, parent) {
    const dlg_factory = new NewChildItemDialogFactory(
        frm,
        (values, frm) => {
            update_item(frm, ctx, values);
            dialog.hide();
        },
        "ITEM",
        "EDIT",
        parent
    );
    const dialog = dlg_factory.create();
    dlg_factory.prefill_item_dialog(dialog, ctx);
    dialog.show();
}

function show_update_new_sub_assembly_dialog(frm, ctx, parent) {
    const dlg_factory = new NewChildItemDialogFactory(
        frm,
        (values, frm) => {
            update_new_sub_assembly(frm, ctx, values);
            dialog.hide();
        },
        "NEW_SUB_ASSEMBLY",
        "EDIT",
        parent
    );
    const dialog = dlg_factory.create();
    dlg_factory.prefill_item_dialog(dialog, ctx);
    dialog.show();
}

function show_update_existing_sub_assembly_dialog(frm, ctx, parent) {
    const dlg_factory = new NewChildItemDialogFactory(
        frm,
        (values, frm) => {
            update_existing_sub_assembly(frm, ctx, values);
            dialog.hide();
        },
        "EXISTING_SUB_ASSEMBLY",
        "EDIT",
        parent
    );
    const dialog = dlg_factory.create();
    dlg_factory.prefill_item_dialog(dialog, ctx);
    dialog.show();
}

function show_update_operation_dialog(frm, ctx, parent) {
    const dlg_factory = new NewChildOperationDialogFactory(frm, (values, frm) => {
        update_operation(frm, ctx, values);
        dialog.hide();
    },
        "EDIT",
        parent);
    const dialog = dlg_factory.create();
    dlg_factory.prefill_operation_dialog(dialog, ctx);
    dialog.show();
}

function duplicate_bom(frm, parent) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.duplicate_bom_structure",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            node_unique_id: parent.node_unique_id,
        },
        freeze: true,
        freeze_message: __("Duplicating BOM..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function delete_item_or_operation(frm, parent) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.delete_item_or_operation",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            node_unique_id: parent.node_unique_id,
        },
        freeze: true,
        freeze_message: __("Deleting..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function add_item(frm, parent, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.add_item",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            parent_node_unique_id: parent.node_unique_id,
            item_code: values.item_code,
            component_qty_per_parent_bom_run: values.component_qty_per_parent_bom_run,
            uom: values.uom
        },
        freeze: true,
        freeze_message: __("Adding Item..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function update_item(frm, ctx, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.update_item",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            node_unique_id: ctx.node_unique_id,
            component_qty_per_parent_bom_run: values.component_qty_per_parent_bom_run,
            uom: values.uom
        },
        freeze: true,
        freeze_message: __("Updating Item..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function add_new_sub_assembly(frm, parent, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.add_new_sub_assembly",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            parent_node_unique_id: parent.node_unique_id,
            item_code: values.item_code,
            component_qty_per_parent_bom_run: values.component_qty_per_parent_bom_run,
            own_batch_size: values.own_batch_size,
            uom: values.uom
        },
        freeze: true,
        freeze_message: __("Adding new Sub-assembly..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function update_new_sub_assembly(frm, ctx, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.update_new_sub_assembly",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            node_unique_id: ctx.node_unique_id,
            component_qty_per_parent_bom_run: values.component_qty_per_parent_bom_run,
            own_batch_size: values.own_batch_size,
            uom: values.uom
        },
        freeze: true,
        freeze_message: __("Updating Sub-assembly..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function add_existing_sub_assembly(frm, parent, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.add_existing_sub_assembly",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            parent_node_unique_id: parent.node_unique_id,
            bom_no: values.bom_no,
            component_qty_per_parent_bom_run: values.component_qty_per_parent_bom_run,
            uom: values.uom
        },
        freeze: true,
        freeze_message: __("Adding existing Sub-assembly..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function update_existing_sub_assembly(frm, ctx, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.update_existing_sub_assembly",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            node_unique_id: ctx.node_unique_id,
            component_qty_per_parent_bom_run: values.component_qty_per_parent_bom_run
        },
        freeze: true,
        freeze_message: __("Updating existing Sub-assembly..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function add_operation(frm, parent, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.add_operation",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            parent_node_unique_id: parent.node_unique_id,
            operation: values.operation,
            time_in_mins: values.time_in_mins,
            fixed_time: values.fixed_time,
            workstation_type: values.workstation_type,
            workstation: values.workstation
        },
        freeze: true,
        freeze_message: __("Adding Operation..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function update_operation(frm, ctx, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.update_operation",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            node_unique_id: ctx.node_unique_id,
            time_in_mins: values.time_in_mins,
            fixed_time: values.fixed_time,
            workstation_type: values.workstation_type,
            workstation: values.workstation
        },
        freeze: true,
        freeze_message: __("Updating Operation..."),
        callback: function (r) {
            if (!r.exc) {
                frm.reload_doc();
            }
        }
    });
}

function get_bom_filter_object(frm, item_code) {
    return {
        item: item_code,
        is_active: 1,
        company: frm.doc.company,
        docstatus: 1
    }
}

//============ Helper Classes ============
class BOMTreeHelper {
    constructor(frm) {
        this.frm = frm;
        this.data = [];
        this.data_map = {}; // node_unique_id → data object map for quick lookup
        this.data_table = null;
        this.current_open_menu = null;
        this.NODE_TYPE_ICONS = {
            "SUB_ASSEMBLY": "fa fa-cubes",               // multi cube icon
            "ITEM": "fa fa-cube",                        // single cube
            "COMPOUND_OPERATION": "fa fa-cogs",          // multi gear icon
            "OPERATION": "fa fa-cog",                    // gear for operation
            "SUB_OPERATION": "fa fa-cog",                // gear for sub operation
            "OPERATION_WITH_SUB_OPERATION": "fa fa-cogs" //multi gear icon if operation has sub operations
        };
    }

    get_bom_tree_columns() {
        const self = this;
        return [
            {
                name: "Name",
                id: "display_name",
                width: 670,
                format: function (value, row, column, data) {
                    const icon_class = self.get_node_icon(data);
                    const icon_margin = data.child_count > 0
                        ? ''
                        : 'margin-left:19px;';
                    return `<i class="${icon_class}" style="${icon_margin} margin-right: 5px;"></i> ${value}`;
                }
            },
            {
                name: "UOM",
                id: "uom",
                width: 90
            },
            {
                name: "Batch Size",
                id: "own_batch_size",
                width: 110,
                format: function (value, row, column, data) {
                    if (!value) return "";

                    const batch_size = data.uom !== data.stock_uom ? `${value} (${data.stock_uom})` : value;
                    return batch_size;
                }
            },
            {
                name: "Component Qty",
                id: "component_qty_per_parent_bom_run",
                width: 130
            },
            {
                name: "Req. Qty",
                id: "total_required_qty",
                width: 110
            },
            {
                name: "Time (mins)",
                id: "time_in_mins",
                width: 100
            },
            {
                name: "Req. Time (mins)",
                id: "total_required_time_in_mins",
                width: 130
            },
            {
                name: "Rate",
                id: "rate",
                width: 130
            },
            {
                name: "Amount",
                id: "amount",
                width: 130
            },
            {
                name: "Total Amount",
                id: "total_required_amount",
                width: 130
            },
            {
                name: "",
                id: "action",
                width: 40,
                format: function (value, row, column, data) {
                    if (!self.is_action_present_for_node(data)) {
                        return "";
                    }

                    return `
                        <div class="dropdown bom-row-dropdown">
                            <span
                                class="row-action-menu"
                                data-nodeuniqueid="${data.node_unique_id}"
                                style="cursor:pointer;padding: 0 8px;"
                            >
                            ...
                            </span>
                            <div data-nodeuniqueid="${data.node_unique_id}" class="dropdown-menu">
                            </div>
                        </div>
                    `;
                }
            }
        ];
    }

    get_node_icon(data) {
        if ((data.node_type == "OPERATION" || data.node_type == "SUB_OPERATION") && data.child_count > 0)
            return this.NODE_TYPE_ICONS["OPERATION_WITH_SUB_OPERATION"];
        return this.NODE_TYPE_ICONS[data.node_type] || "fa fa-question-circle";
    }

    get_tree_parent_html_el() {
        return $(this.frm.fields_dict["bom_tree"].wrapper);
    }

    reset_tree_html() {
        const $parent = this.get_tree_parent_html_el();
        $parent.empty();
    }

    set_data(data) {
        this.data = data;
        this.data_map = {};
        data.forEach(item => {
            this.data_map[item.node_unique_id] = item;
        });
    }

    render_tree(data) {
        this.set_data(data);
        this.reset_tree_html();

        const $parent = this.get_tree_parent_html_el();
        const container = $('<div>').appendTo($parent);

        const columns = this.get_bom_tree_columns();
        // Compute width dynamically according to container width
        this.apply_dynamic_tree_column_width(columns, container);

        this.data_table = new frappe.DataTable(container[0], {
            columns: columns,
            data: data,
            treeView: true,
            inlineFilters: false
        });

        this.register_row_action_click_handler();
    }

    /**
     * Dynamically adjusts the tree (first) column width to fill the remaining
     * available space after fixed-width columns are applied.
     *
     * This ensures proper alignment and avoids layout issues when tree indentation
     * grows with hierarchy depth.
     * 
     * NOTE: Frappe data table ratio layout can do this thing automatically but
     * it messes up the first sequence number (index) column width when index are
     * greater than one digit. So instead of using ratio layout, we manually compute
     * and set the first column width here.
     */
    apply_dynamic_tree_column_width(columns, container) {
        // Total width available to DataTable
        const containerWidth = container.parent().width();

        // Row index column (empirically ~48px)
        const INDEX_COL_WIDTH = 48;

        // Scrollbar safety buffer
        const SCROLLBAR_WIDTH = 10;

        let fixedWidthSum = 0;

        columns.forEach((col, idx) => {
            if (idx !== 0) {
                fixedWidthSum += col.width || 0;
            }
        });

        const remaining =
            containerWidth
            - INDEX_COL_WIDTH
            - fixedWidthSum
            - SCROLLBAR_WIDTH;

        // Safety floor
        columns[0].width = Math.max(300, remaining);
    }


    is_action_present_for_node(data) {
        if (data.is_projected) {
            return false;
        }
        if (data.can_add_child_item || data.can_add_child_operation || data.can_delete) {
            return true;
        }
    }

    //====== Menu related functions =======
    register_row_action_click_handler() {
        const self = this;
        // Avoid multiple event handler registrations by unregistering first
        $(document).off('click.rowActionMenu', '.row-action-menu')
        $(document).on('click.rowActionMenu', '.row-action-menu', function (e) {
            e.stopPropagation();
            const $el = $(this);
            self.open_row_context_menu($el);
        });
    }

    open_row_context_menu($trigger) {
        const self = this;
        const $dropdown = $trigger.closest('.bom-row-dropdown');
        const $menu = $dropdown.find('.dropdown-menu');

        // Close previous menu if different
        if (this.current_open_menu && this.current_open_menu[0] !== $menu[0]) {
            this.close_current_menu();
        }

        // Toggle current menu
        const isShown = $menu.hasClass('show');
        if (isShown) {
            this.close_current_menu();
            return;
        }

        this.current_open_menu = $menu;
        $menu.data('original-parent', $dropdown);

        // Move menu to body so it can overflow table cell
        $('body').append($menu);

        const GAP = 4;
        const SHIFT_LEFT = 30;

        const rect = $trigger[0].getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const openUpwards = rect.top > viewportHeight * 0.8; // open upwards if in bottom 20% of viewport

        let top;
        if (openUpwards) {
            // anchor menu above the row and move it upward via transform
            top = rect.top - GAP;
            $menu.css({
                transform: 'translateY(-100%)',
                transformOrigin: 'bottom'
            });
        } else {
            // normal downward opening
            top = rect.bottom + GAP;
            $menu.css({
                transform: 'none',
                transformOrigin: 'top'
            });
        }

        $menu.css({
            position: 'fixed',
            top: top,
            left: rect.left - SHIFT_LEFT,
            zIndex: 9999
        }).addClass('show');

        this.render_row_context_menu($menu);

        // Outside click → close menu
        setTimeout(() => { // defer to prevent immediate closure
            $(document).off('click.bomDropdown').on('click.bomDropdown', function (e) {
                if (!$(e.target).closest($menu).length && !$(e.target).is($trigger)) {
                    self.close_current_menu();
                }
            });
        }, 0);
    }

    render_row_context_menu($menu) {
        const node_unique_id = $menu.data('nodeuniqueid');
        const menu_ctx = this.data_map[node_unique_id];
        const full_data_ctx = this.data_map;
        const items = MenuProvider.getRowMenuItems(menu_ctx) || [];

        $menu.empty();

        items.forEach(item => {
            const $el = $(`
            <a class="dropdown-item" href="#">${item.label}</a>
        `);

            $el.on("click", (e) => {
                e.preventDefault();
                e.stopPropagation();

                const can_execute = this.can_execute_menu_handler();
                if (!can_execute) {
                    this.close_current_menu();
                    frappe.throw({
                        title: __("Unsaved Changes"),
                        message: __("Please save the document first and then try this operation.")
                    });
                }

                item.action(this.frm, menu_ctx, full_data_ctx);
                this.close_current_menu();
            });

            $menu.append($el);
        });
    }

    close_current_menu() {
        if (!this.current_open_menu) return;
        this.current_open_menu.removeClass('show');
        const parent = this.current_open_menu.data('original-parent');
        if (parent) parent.append(this.current_open_menu); // restore menu inside row
        this.current_open_menu = null;
        $(document).off('click.bomDropdown'); // remove outside click handler
    }

    can_execute_menu_handler() {
        return this.frm.is_new() || !this.frm.is_dirty();
    }
}

class MenuProvider {
    static getRowMenuItems(ctx) {

        const items = [];
        if (ctx.can_add_child_item) {
            items.push(
                { label: "Add Item", action: show_add_item_dialog },
                { label: "Add New Sub-Assembly", action: show_add_new_sub_assembly_dialog },
                { label: "Add Existing Sub-Assembly", action: show_add_existing_sub_assembly_dialog }
            );
        }

        if (ctx.can_add_child_operation) {
            items.push(
                { label: "Add Operation", action: show_add_operation_dialog }
            );
        }

        if (ctx.can_edit) {
            items.push({ label: "Edit", action: show_update_dialog });
        }

        if (ctx.can_duplicate_bom) {
            items.push(
                { label: "Duplicate BOM", action: duplicate_bom }
            );
        }

        if (ctx.can_delete) {
            items.push(
                { label: "Delete", action: delete_item_or_operation },
            );
        }

        return items;
    }
}

class NewFormDialogFactory {
    constructor(frm, action) {
        this.frm = frm;
        this.action = action;
        this.company_currency = null;
    }

    create() {
        const self = this;
        const dialog = new frappe.ui.Dialog({
            title: __("Multilevel BOM Creator"),
            fields: [
                {
                    label: __("Item Code (Final Product)"),
                    fieldtype: "Link",
                    fieldname: "item_code",
                    options: "Item",
                    reqd: 1,
                    onchange: () => {
                        const item_code = dialog.get_value("item_code");
                        if (!item_code) {
                            return;
                        }

                        frappe.db.get_value(
                            "Item",
                            item_code,
                            "stock_uom"
                        ).then((r) => {
                            if (r && r.message && r.message.stock_uom) {
                                dialog.set_value("uom", r.message.stock_uom);
                            }
                        });
                    },
                },
                { fieldtype: "Column Break" },
                {
                    label: __("Company"),
                    fieldtype: "Link",
                    fieldname: "company",
                    options: "Company",
                    reqd: 1,
                    default: frappe.defaults.get_user_default("Company"),
                    onchange: () => self.set_currency(dialog)
                },
                { fieldtype: "Section Break" },
                {
                    label: __("UOM"),
                    fieldtype: "Link",
                    fieldname: "uom",
                    options: "UOM",
                    read_only: 1
                },
                { fieldtype: "Column Break" },
                {
                    label: __("Quantity"),
                    fieldtype: "Float",
                    fieldname: "qty",
                    reqd: 1,
                    default: 1.0,
                },
                { fieldtype: "Section Break" },
                {
                    label: __("Currency"),
                    fieldtype: "Link",
                    fieldname: "currency",
                    options: "Currency",
                    reqd: 1,
                    onchange: () => self.update_conversion_rate_description(dialog)
                },
                { fieldtype: "Column Break" },
                {
                    label: __("Conversion Rate"),
                    fieldtype: "Float",
                    fieldname: "conversion_rate",
                    reqd: 1,
                    default: 1,
                    precision: 9
                },
            ],
            primary_action_label: __("Create"),
            primary_action: (values) => {
                this.action(values, this.frm);
            },
        });

        dialog.fields_dict.item_code.get_query = "erpnext.controllers.queries.item_query";
        self.set_currency(dialog);
        return dialog;
    }

    set_currency(dialog) {
        const company = dialog.get_value("company");
        if (!company) {
            this.company_currency = null;
            return;
        }

        frappe.db.get_value(
            "Company",
            company,
            "default_currency"
        ).then(r => {
            if (r?.message?.default_currency) {
                dialog.set_value("currency", r.message.default_currency);
                this.company_currency = r.message.default_currency;
                this.update_conversion_rate_description(dialog);
            }
        });
    }

    update_conversion_rate_description(dialog) {
        const selected_currency = dialog.get_value("currency");
        const company_currency = this.company_currency;

        if (!selected_currency || !company_currency || (selected_currency === company_currency)) {
            dialog.set_df_property(
                "conversion_rate",
                "description",
                ""
            );
            return;
        }

        const description = __(
            `1 ${selected_currency} = [?] ${company_currency}`
        );

        dialog.set_df_property(
            "conversion_rate",
            "description",
            description
        );
    }
}

class NewChildItemDialogFactory {
    constructor(frm, action, item_type, mode, parent_node) {
        this.frm = frm;
        this.action = action;
        this.item_type = item_type; // item_type can be 'ITEM', 'NEW_SUB_ASSEMBLY', or 'EXISTING_SUB_ASSEMBLY'
        this.mode = mode; // mode can be 'ADD' or 'EDIT'
        this.parent_node = parent_node;
    }

    create() {
        const self = this;
        const fields = [];
        if (this.item_type === "ITEM" || this.item_type === "NEW_SUB_ASSEMBLY") {
            fields.push({
                label: __("Item Code"),
                fieldtype: "Link",
                fieldname: "item_code",
                options: "Item",
                reqd: 1,
                read_only: this.mode === "EDIT" ? 1 : 0
            });
        } else if (this.item_type === "EXISTING_SUB_ASSEMBLY") {
            fields.push({
                label: __("BOM"),
                fieldtype: "Link",
                fieldname: "bom_no",
                options: "BOM",
                reqd: 1,
                read_only: this.mode === "EDIT" ? 1 : 0
            });
        }
        fields.push({ fieldtype: "Section Break" });
        fields.push({
            label: __("UOM"),
            fieldtype: "Link",
            fieldname: "uom",
            options: "UOM",
            reqd: 1
        });
        const component_qty_label = this.parent_node
            ? __(`Component Qty Required For Batch Size (${this.parent_node.own_batch_size} ${this.parent_node.stock_uom}) of ${this.parent_node.item_code}`)
            : __("Component Qty");
        fields.push({
            label: component_qty_label,
            fieldtype: "Float",
            fieldname: "component_qty_per_parent_bom_run",
            reqd: 1,
            default: 1.0
        });
        if (this.item_type === "NEW_SUB_ASSEMBLY" || this.item_type === "EXISTING_SUB_ASSEMBLY") {
            fields.push({ fieldtype: "Section Break" });
            fields.push({
                label: __("Batch Size UOM"),
                fieldtype: "Link",
                fieldname: "stock_uom",
                options: "UOM",
                read_only: 1
            });
            const batch_size_label = this.item_type === "NEW_SUB_ASSEMBLY"
                ? __("Batch Size of this new sub-assembly BOM")
                : __("Batch Size");
            fields.push({
                label: batch_size_label,
                fieldtype: "Float",
                fieldname: "own_batch_size",
                reqd: 1,
                default: 1.0,
                read_only: this.item_type === "EXISTING_SUB_ASSEMBLY" ? 1 : 0
            });
        }

        const dialog = new frappe.ui.Dialog({
            title: this.get_title(),
            fields: fields,
            primary_action_label: this.mode === "ADD" ? __("Create") : __("Update"),
            primary_action: (values) => {
                this.action(values, this.frm);
            }
        });

        if (fields.some(f => f.fieldname === "item_code")) {
            dialog.fields_dict.item_code.get_query = "erpnext.controllers.queries.item_query";
            dialog.fields_dict.item_code.df.onchange = () => self.on_item_change(dialog);
        }

        if (this.item_type === "EXISTING_SUB_ASSEMBLY") {
            dialog.fields_dict.bom_no.df.onchange = () => self.on_bom_change(dialog);
        }
        return dialog;
    }

    prefill_item_dialog(dialog, ctx) {
        if (this.item_type === "ITEM" || this.item_type === "NEW_SUB_ASSEMBLY") {
            dialog.set_value("item_code", ctx.item_code);
        } else if (this.item_type === "EXISTING_SUB_ASSEMBLY") {
            dialog.set_value("bom_no", ctx.bom_no);
        }

        dialog.set_value("component_qty_per_parent_bom_run", ctx.component_qty_per_parent_bom_run);
        dialog.set_value("uom", ctx.uom);

        if (this.item_type === "EXISTING_SUB_ASSEMBLY" || this.item_type === "NEW_SUB_ASSEMBLY") {
            dialog.set_value("stock_uom", ctx.stock_uom);
            dialog.set_value("own_batch_size", ctx.own_batch_size);
        }
    }

    on_item_change(dialog) {
        if (this.mode === "EDIT") {
            return;
        }
        const item_code = dialog.get_value("item_code");
        if (!item_code) {
            return;
        }
        frappe.db.get_value(
            "Item",
            item_code,
            "stock_uom"
        ).then((r) => {
            if (r && r.message && r.message.stock_uom) {
                dialog.set_value("uom", r.message.stock_uom);
                dialog.set_value("stock_uom", r.message.stock_uom);
            }
        });
    }

    on_bom_change(dialog) {
        if (this.mode === "EDIT") {
            return;
        }
        const bom_no = dialog.get_value("bom_no");
        if (!bom_no) {
            return;
        }
        frappe.db.get_value(
            "BOM",
            bom_no,
            ["uom", "quantity"]
        ).then((r) => {
            if (r && r.message && r.message.uom) {
                dialog.set_value("uom", r.message.uom);
                dialog.set_value("stock_uom", r.message.uom);
                dialog.set_value("own_batch_size", r.message.quantity);
            }
        });
    }

    get_title() {
        if (this.mode === "ADD") {
            if (this.item_type === "ITEM") {
                return __("Add Item");
            }

            if (this.item_type === "NEW_SUB_ASSEMBLY") {
                return __("Add New Sub-Assembly");
            }

            if (this.item_type === "EXISTING_SUB_ASSEMBLY") {
                return __("Add Existing Sub-Assembly");
            }

            return __("Add");
        }

        if (this.mode === "EDIT") {
            if (this.item_type === "ITEM") {
                return __("Edit Item");
            }

            if (this.item_type === "NEW_SUB_ASSEMBLY" || this.item_type === "EXISTING_SUB_ASSEMBLY") {
                return __("Edit Sub-Assembly");
            }

            return __("Edit");
        }
    }
}

class NewChildOperationDialogFactory {
    constructor(frm, action, mode, parent_node) {
        this.frm = frm;
        this.action = action;
        this.mode = mode;   // mode can be 'ADD' or 'EDIT'
        this.parent_node = parent_node;
    }

    create() {
        const operation_time_label = this.parent_node
            ? __(`Operation Time Required For Batch Size (${this.parent_node.own_batch_size} ${this.parent_node.uom}) of ${this.parent_node.item_code}`)
            : __("Operation Time");
        const dialog = new frappe.ui.Dialog({
            title: this.get_title(),
            fields: [
                {
                    label: __("Operation"),
                    fieldtype: "Link",
                    fieldname: "operation",
                    options: "Operation",
                    reqd: 1,
                    read_only: this.mode === "EDIT" ? 1 : 0,
                    onchange: () => this.on_operation_change(dialog)
                },
                { fieldtype: "Section Break" },
                {
                    label: __("Workstation Type"),
                    fieldtype: "Link",
                    fieldname: "workstation_type",
                    options: "Workstation Type",
                    reqd: 0,
                    onchange: () => this.on_workstation_type_change(dialog)
                },
                { fieldtype: "Column Break" },
                {
                    label: __("Workstation"),
                    fieldtype: "Link",
                    fieldname: "workstation",
                    options: "Workstation",
                    reqd: 0,
                },

                { fieldtype: "Section Break" },
                {
                    label: operation_time_label,
                    fieldtype: "Float",
                    fieldname: "time_in_mins",
                    reqd: 1,
                    description: __("in mins")
                },
                {
                    label: __("Fixed Time"),
                    fieldtype: "Check",
                    fieldname: "fixed_time",
                    description: __("Operation time does not depend on quantity to produce")
                },

            ],
            primary_action_label: this.mode === "ADD" ? __("Create") : __("Update"),
            primary_action: (values) => {
                this.action(values, this.frm);
            },
        });

        return dialog;
    }

    prefill_operation_dialog(dialog, ctx) {
        dialog.set_value("operation", ctx.operation);
        dialog.set_value("time_in_mins", ctx.time_in_mins);
        dialog.set_value("fixed_time", ctx.fixed_time);
        dialog.set_value("workstation_type", ctx.workstation_type);
        dialog.set_value("workstation", ctx.workstation);
    }

    on_operation_change(dialog) {
        const operation = dialog.get_value("operation");
        if (!operation) {
            dialog.set_value("workstation_type", r.message.default_workstation_type);
            dialog.set_value("workstation", r.message.default_workstation);
            return;
        }

        frappe.db.get_value(
            "Operation",
            operation,
            ["total_operation_time", "workstation"]
        ).then((r) => {
            if (r && r.message) {
                if (r.message.total_operation_time) {
                    dialog.set_value("time_in_mins", r.message.total_operation_time);
                }
                if (r.message.workstation) {
                    dialog.set_value("workstation", r.message.workstation);
                }
            }
        });
    }

    on_workstation_type_change(dialog) {
        const workstation_type = dialog.get_value("workstation_type");
        dialog.set_df_property("workstation", "hidden", workstation_type ? true : false);
    }

    get_title() {
        if (this.mode === "ADD") {
            return __("Add Operation");
        }

        if (this.mode === "EDIT") {
            return __("Edit Operation");
        }
    }
}
// Copyright (c) 2025, iMORPHr Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Multilevel BOM Creator", {
    refresh(frm) {
        setup_bom_creator(frm);
    },
});

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
    }).create();
    dialog.show();
}

function show_edit_dialog(frm, ctx, full_data_ctx) {
    const parent = ctx.parent_node_unique_id ? full_data_ctx[ctx.parent_node_unique_id] : null;
    if (ctx.node_type === "ITEM") {
        show_edit_item_dialog(frm, ctx, parent);
    } else if (ctx.node_type === "SUB_ASSEMBLY") {
        if (ctx.is_preexisting_bom) {
            show_edit_existing_sub_assembly_dialog(frm, ctx, parent);
        } else {
            show_edit_new_sub_assembly_dialog(frm, ctx, parent);
        }
    } else if (ctx.node_type === "OPERATION") {
        show_edit_operation_dialog(frm, ctx, parent);
    }
}

function show_edit_item_dialog(frm, ctx, parent) {
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

function show_edit_new_sub_assembly_dialog(frm, ctx, parent) {
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

function show_edit_existing_sub_assembly_dialog(frm, ctx, parent) {
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

function show_edit_operation_dialog(frm, ctx, parent) {

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
            component_qty_per_parent_bom_run: values.component_qty_per_parent_bom_run
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
            operation_name: values.operation_name,
            time_in_mins: values.time_in_mins,
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
                width: 80
            },
            {
                name: "Batch Size",
                id: "own_batch_size",
                width: 130
            },
            {
                name: "Component Qty",
                id: "component_qty_per_parent_bom_run",
                width: 160
            },
            {
                name: "Req. Qty",
                id: "total_required_qty",
                width: 90
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

        const columns = this.get_bom_tree_columns();
        const $parent = this.get_tree_parent_html_el();
        const container = $('<div>').appendTo($parent);

        this.data_table = new frappe.DataTable(container[0], {
            columns: columns,
            data: data,
            treeView: true,
            inlineFilters: false
        });

        this.register_row_action_click_handler();
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

        const rect = $trigger[0].getBoundingClientRect();
        $menu.css({
            position: 'fixed',
            top: rect.bottom + 4,
            left: rect.left,
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
            items.push({ label: "Edit", action: show_edit_dialog });
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
    }

    create() {
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
                {
                    label: __("UOM"),
                    fieldtype: "Link",
                    fieldname: "uom",
                    options: "UOM",
                    reqd: 1,
                },
                { fieldtype: "Column Break" },
                {
                    label: __("Company"),
                    fieldtype: "Link",
                    fieldname: "company",
                    options: "Company",
                    reqd: 1,
                    default: frappe.defaults.get_user_default("Company"),
                },
                {
                    label: __("Quantity"),
                    fieldtype: "Float",
                    fieldname: "qty",
                    reqd: 1,
                    default: 1.0,
                },
            ],
            primary_action_label: __("Create"),
            primary_action: (values) => {
                this.action(values, this.frm);
            },
        });

        dialog.fields_dict.item_code.get_query = "erpnext.controllers.queries.item_query";
        return dialog;
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
            reqd: 1,
            read_only: this.item_type === "EXISTING_SUB_ASSEMBLY" ? 1 : 0
        });
        const component_qty_label = this.parent_node 
            ? __(`Component Qty Required For Batch Size (${this.parent_node.own_batch_size} ${this.parent_node.uom}) of ${this.parent_node.item_code}`)
            : __("Component Qty");
        fields.push({
            label: component_qty_label,
            fieldtype: "Float",
            fieldname: "component_qty_per_parent_bom_run",
            reqd: 1,
            default: 1.0,
            description: "Quantity needed for one execution of parent BOM"
        });
        if (this.item_type === "NEW_SUB_ASSEMBLY") {
            fields.push({ fieldtype: "Section Break" });
            fields.push({
                label: __("Batch Size"),
                fieldtype: "Float",
                fieldname: "own_batch_size",
                reqd: 1,
                default: 1.0,
                description: "Batch size of this sub-assembly's own BOM"
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
            dialog.fields_dict.item_code.df.onchange = () => this.on_item_change(dialog);
        }

        if (this.item_type === "EXISTING_SUB_ASSEMBLY") {
            dialog.fields_dict.bom_no.df.onchange = () => this.on_bom_change(dialog);
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
        if (this.item_type !== "EXISTING_SUB_ASSEMBLY") {
            dialog.set_value("uom", ctx.uom);
        }

        if (this.item_type === "NEW_SUB_ASSEMBLY") {
            dialog.set_value("own_batch_size", ctx.own_batch_size);
        }
    }

    on_item_change(dialog) {
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
    }

    on_bom_change(dialog) {
        const bom_no = dialog.get_value("bom_no");
        if (!bom_no) {
            return;
        }
        frappe.db.get_value(
            "BOM",
            bom_no,
            "uom"
        ).then((r) => {
            if (r && r.message && r.message.uom) {
                dialog.set_value("uom", r.message.uom);
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
    constructor(frm, action) {
        this.frm = frm;
        this.action = action;
    }

    create() {
        const dialog = new frappe.ui.Dialog({
            title: __("Add New Operation"),
            fields: [
                {
                    label: __("Operation"),
                    fieldtype: "Link",
                    fieldname: "operation_name",
                    options: "Operation",
                    reqd: 1,
                },
                {
                    label: __("Workstation Type"),
                    fieldtype: "Link",
                    fieldname: "workstation_type",
                    options: "Workstation Type",
                    reqd: 0,
                },
                { fieldtype: "Column Break" },
                {
                    label: __("Operation Time (in mins)"),
                    fieldtype: "Float",
                    fieldname: "time_in_mins",
                    reqd: 1,
                },
                {
                    label: __("Workstation"),
                    fieldtype: "Link",
                    fieldname: "workstation",
                    options: "Workstation",
                    reqd: 0,
                },
            ],
            primary_action_label: __("Create"),
            primary_action: (values) => {
                this.action(values, this.frm);
            },
        });

        return dialog;
    }
}
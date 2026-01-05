// Copyright (c) 2025, iMORPHr Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Multilevel BOM Creator", {
    refresh(frm) {
        setup_bom_creator(frm);

        if (!frm.is_new()) {
            frm.add_custom_button(
                __("Create BOMs"),
                () => {
                    create_boms(frm);
                },
                ""
            );
        }
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

function create_boms(frm) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.create_boms",
        args: {
            multilevel_bom_creator_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __("Creating BOMs..."),
        callback: function (r) {
            if (!r.exc && r.message) {
                frm.reload_doc();
            }
        }
    });
}

//============ Tree item handlers ============
function show_item_dialog(frm, parent) {
    const dialog = new NewChildItemDialogFactory(frm, (values, frm) => {
        const bom_name = values.bom_name;
        if (bom_name !== null && bom_name !== undefined && bom_name.trim().length > 0) {
            add_existing_sub_assembly(frm, parent, values);
        } else {
            add_item(frm, parent, values);
        }
        dialog.hide();
    }).create();
    dialog.show();
}

function show_operation_dialog(frm, parent) {
    const dialog = new NewChildOperationDialogFactory(frm, (values, frm) => {
        add_operation(frm, parent, values);
        dialog.hide();
    }).create();
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

function add_item(frm, parent, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.add_item",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            parent_node_unique_id: parent.node_unique_id,
            item_code: values.item_code,
            quantity: values.qty,
            uom: "" // TODO: fetch UOM from item master
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

function add_existing_sub_assembly(frm, parent, values) {
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.add_existing_sub_assembly",
        args: {
            multilevel_bom_creator_name: frm.doc.name,
            parent_node_unique_id: parent.node_unique_id,
            bom_name: values.bom_name,
            quantity: values.qty,
            uom: "" // TODO: fetch UOM from item master
        },
        freeze: true,
        freeze_message: __("Adding Sub-assembly..."),
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

function delete_item(frm, item) {
    frappe.msgprint(`Delete clicked for ${item.name}`);
}

function delete_sub_assembly(frm, sub_assembly) {
    frappe.msgprint(`Delete Sub-Assembly clicked for ${sub_assembly.name}`);
}

function delete_operation(frm, operation) {
    frappe.msgprint(`Delete Operation clicked for ${operation.name}`);
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
            "SUB_ASSEMBLY": "fa fa-cubes",              // multi cube icon
            "ITEM": "fa fa-cube",                       // single cube
            "COMPOUND_OPERATION": "fa fa-cogs",         // multi gear icon
            "OPERATION": "fa fa-cog"                    // gear for operation
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
                    const icon_class = self.NODE_TYPE_ICONS[data.node_type] || "fa fa-question-circle";
                    const icon_margin = (data.node_type === "ITEM" || data.node_type === "OPERATION")
                        ? 'margin-left:19px;'
                        : '';
                    return `<i class="${icon_class}" style="${icon_margin} margin-right: 5px;"></i> ${value}`;
                }
            },
            {
                name: "Qty",
                id: "quantity",
                width: 80
            },
            {
                name: "UOM",
                id: "uom",
                width: 80
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
        const items = MenuProvider.getRowMenuItems(menu_ctx) || [];

        $menu.empty();

        items.forEach(item => {
            const $el = $(`
            <a class="dropdown-item" href="#">${item.label}</a>
        `);

            $el.on("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                item.action(this.frm, menu_ctx);
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
                { label: "Add Item", action: show_item_dialog }
            );
        }

        if (ctx.can_add_child_operation) {
            items.push(
                { label: "Add Operation", action: show_operation_dialog },
            );
        }

        if (ctx.can_duplicate_bom) {
            items.push(
                { label: "Duplicate BOM", action: duplicate_bom }
            );
        }

        if (ctx.can_delete) {
            const delete_handler = ctx.node_type === "ITEM"
                ? delete_item
                : (ctx.node_type === "SUB_ASSEMBLY" ? delete_sub_assembly : delete_operation);
            items.push(
                { label: "Delete", action: delete_handler },
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
                    label: __("Name"),
                    fieldtype: "Data",
                    fieldname: "name",
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
                { fieldtype: "Section Break" },
                {
                    label: __("Item Code (Final Product)"),
                    fieldtype: "Link",
                    fieldname: "item_code",
                    options: "Item",
                    reqd: 1,
                },
                { fieldtype: "Column Break" },
                {
                    label: __("Quantity"),
                    fieldtype: "Float",
                    fieldname: "qty",
                    reqd: 1,
                    default: 1.0,
                },
                // { fieldtype: "Section Break" },
                // {
                //     label: __("Currency"),
                //     fieldtype: "Link",
                //     fieldname: "currency",
                //     options: "Currency",
                //     reqd: 1,
                //     default: frappe.defaults.get_global_default("currency"),
                // },
                // { fieldtype: "Column Break" },
                // {
                //     label: __("Conversion Rate"),
                //     fieldtype: "Float",
                //     fieldname: "conversion_rate",
                //     reqd: 1,
                //     default: 1.0,
                // },
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
    constructor(frm, action) {
        this.frm = frm;
        this.action = action;
    }

    create() {
        const self = this;
        const dialog = new frappe.ui.Dialog({
            title: __("Add Item"),
            fields: [
                {
                    label: __("Item Code"),
                    fieldtype: "Link",
                    fieldname: "item_code",
                    options: "Item",
                    reqd: 1,
                },
                { fieldtype: "Column Break" },
                {
                    label: __("BOM"),
                    fieldtype: "Link",
                    fieldname: "bom_name",
                    options: "BOM",
                    hidden: 1,
                    description: __(
                        "Select a BOM if you want to use an existing structure. Leave it blank to add the item and create a new structure."
                    )
                },
                { fieldtype: "Section Break" },
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
            }
        });

        dialog.fields_dict.item_code.get_query = "erpnext.controllers.queries.item_query";
        dialog.fields_dict.item_code.df.onchange = () => this.on_item_change(dialog);
        dialog.fields_dict.bom_name.get_query = function () {
            return {
                filters: get_bom_filter_object(self.frm, dialog.get_value("item_code"))
            };
        }
        return dialog;
    }

    on_item_change(dialog) {
        const item_code = dialog.get_value("item_code");
        dialog.set_value("bom_name", null);

        if (!item_code) {
            dialog.set_df_property("bom_name", "hidden", 1);
            return;
        }

        frappe.db.get_list("BOM", {
            filters: get_bom_filter_object(this.frm, item_code),
            fields: ["name"]
        }).then(boms => {
            if ((boms || []).length > 0) {
                dialog.set_df_property("bom_name", "hidden", 0);
            } else {
                dialog.set_df_property("bom_name", "hidden", 1);
            }
        });
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
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
function add_item(frm, parent) {
    // frappe.msgprint(`Add Item clicked for ${parent.name}`);
    frappe.show_alert(`Add Item clicked for ${parent.name}`);
    frm.reload_doc();
}

function add_existing_sub_assembly(frm, parent) {
    frappe.msgprint(`Add Existing Sub-Assembly clicked for ${parent.name}`);
}

function add_operation(frm, parent) {
    frappe.msgprint(`Add Operation clicked for ${parent.name}`);
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

//============ Helper Classes ============
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

class BOMTreeHelper {
    constructor(frm) {
        this.frm = frm;
        this.data = [];
        this.data_map = {}; // node_guid → data object map for quick lookup
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
                name: "Action",
                id: "action",
                width: 70,
                format: function (value, row, column, data) {
                    return `
                        <div class="dropdown bom-row-dropdown">
                            <span
                                class="row-action-menu"
                                data-nodeguid="${data.node_guid}"
                                style="cursor:pointer;padding: 0 8px;"
                            >
                            ⋮
                            </span>
                            <div data-nodeguid="${data.node_guid}" class="dropdown-menu">
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
            this.data_map[item.node_guid] = item;
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
        const node_guid = $menu.data('nodeguid');
        const menu_ctx = this.data_map[node_guid];
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

        if (ctx.node_type === "ITEM") {
            items.push(
                { label: "Add Operation", action: add_operation },
                { label: "Add Item", action: add_item },
                { label: "Add Existing Sub-Assembly", action: add_existing_sub_assembly },
                { label: "Delete", action: delete_item }
            );
        }
        else if (ctx.node_type === "SUB_ASSEMBLY") {
            if (!ctx.parent_node_guid || !ctx.bom_no) {
                items.push(
                    { label: "Add Operation", action: add_operation },
                    { label: "Add Item", action: add_item },
                    { label: "Add Existing Sub-Assembly", action: add_existing_sub_assembly }
                );
            }

            if (ctx.parent_node_guid) {
                items.push(
                    { label: "Delete", action: delete_sub_assembly }
                );
            }
        }

        return items;
    }
}
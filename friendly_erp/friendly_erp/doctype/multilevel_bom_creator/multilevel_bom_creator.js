// Copyright (c) 2025, iMORPHr Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Multilevel BOM Creator", {
    refresh(frm) {
        get_tree(frm);
    },
});

const NODE_TYPE_ICONS = {
    "SUB_ASSEMBLY": "fa fa-cubes",          // multi cube icon
    "ITEM": "fa fa-cube",                   // single cube
    "COMPOUND_OPERATION": "fa fa-cogs",    // multi gear icon
    "OPERATION": "fa fa-cog"                // gear for operation
};

function reset_tree_html(frm) {
    const $parent = $(frm.fields_dict["bom_tree"].wrapper);
    $parent.empty();
}

function get_tree(frm) {
    reset_tree_html(frm);

    if (frm.is_new() || !frm.doc.item_code) {
        return;
    }
    
    let $parent = $(frm.fields_dict["bom_tree"].wrapper);
    $parent.empty();
    frappe.call({
        method: "friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator.get_tree_flat",
        args: {
            multilevel_bom_creator_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __("Loading BOM structure..."),
        callback: function (r) {
            if (!r.exc && r.message) {
                const columns = get_bom_tree_columns();
                const data = r.message;
                const container = $('<div>').appendTo($parent);
                const data_table = new frappe.DataTable(container[0], {
                    columns: columns,
                    data: data,
                    treeView: true,
                    inlineFilters: false
                });
            }
        }
    })
}

function get_bom_tree_columns() {
    return [
        {
            "name": "Name",
            "id": "display_name",
            "width": 570,
            "format": function (value, row, column, data) {
                const icon_class = NODE_TYPE_ICONS[data.node_type] || "fa fa-question-circle";
                const icon_margin = (data.node_type === "ITEM" || data.node_type === "OPERATION")
                    ? 'margin-left:19px;'
                    : '';
                return `<i class="${icon_class}" style="${icon_margin} margin-right: 5px;"></i> ${value}`;
            }
        },
        {
            "name": "Qty",
            "id": "quantity",
            "width": 80
        },
        {
            "name": "UOM",
            "id": "uom",
            "width": 80
        },
    ];
}

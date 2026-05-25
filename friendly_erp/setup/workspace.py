import frappe

DOCTYPE = "Multilevel BOM Creator"
WORKSPACE = "Manufacturing"
TOOLS_CARD = "Tools"

LINK = {
    "type": "Link",
    "label": DOCTYPE,
    "link_type": "DocType",
    "link_to": DOCTYPE,
    "dependencies": "",
    "onboard": 0,
    "hidden": 0,
    "is_query_report": 0,
}


def add_multilevel_bom_creator_to_manufacturing_workspace():
    if not frappe.db.exists("Workspace", WORKSPACE):
        return

    if _link_exists():
        return

    workspace = frappe.get_doc("Workspace", WORKSPACE)
    insert_idx = _get_tools_insert_index(workspace.links)

    if insert_idx is None:
        return

    workspace.append("links", LINK.copy(), position=insert_idx)
    workspace.save(ignore_permissions=True)


def remove_multilevel_bom_creator_from_manufacturing_workspace():
    if not frappe.db.exists("Workspace", WORKSPACE):
        return

    workspace = frappe.get_doc("Workspace", WORKSPACE)
    removed = False

    for link in list(workspace.links):
        if link.type == "Link" and link.link_to == DOCTYPE and link.link_type == "DocType":
            workspace.remove(link)
            removed = True

    if not removed:
        return

    workspace.save(ignore_permissions=True)


def _get_tools_insert_index(links):
    tools_idx = _get_card_break_index(links, TOOLS_CARD)

    if tools_idx is None:
        return None

    for idx in range(tools_idx + 1, len(links)):
        if links[idx].type == "Card Break":
            return idx

    return len(links)


def _get_card_break_index(links, label):
    for idx, link in enumerate(links):
        if link.type == "Card Break" and link.label == label:
            return idx

    return None


def _link_exists():
    return frappe.db.exists(
        "Workspace Link",
        {
            "parent": WORKSPACE,
            "parenttype": "Workspace",
            "link_to": DOCTYPE,
            "link_type": "DocType",
        },
    )
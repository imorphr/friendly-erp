import frappe

MANUFACTURING_WORKSPACE = "Manufacturing"
MANUFACTURING_SIDEBAR = "Manufacturing"
TOOLS_CARD_LABEL = "Tools"
MULTILEVEL_BOM_CREATOR_DOCTYPE = "Multilevel BOM Creator"
MULTILEVEL_BOM_CREATOR_LABEL = "Multilevel BOM Creator"


def add_multilevel_bom_creator_to_manufacturing_workspace():
    add_multilevel_bom_creator_to_manufacturing_workspace_links()
    add_multilevel_bom_creator_to_manufacturing_sidebar()


def remove_multilevel_bom_creator_from_manufacturing_workspace():
    remove_multilevel_bom_creator_from_manufacturing_workspace_links()
    remove_multilevel_bom_creator_from_manufacturing_sidebar()


def add_multilevel_bom_creator_to_manufacturing_workspace_links():
    if not frappe.db.exists("Workspace", MANUFACTURING_WORKSPACE):
        return

    if _workspace_link_exists(MULTILEVEL_BOM_CREATOR_DOCTYPE):
        return

    workspace = frappe.get_doc("Workspace", MANUFACTURING_WORKSPACE)
    tools_idx = _find_tools_card_index(workspace.links)

    if tools_idx is None:
        return

    insert_idx = _find_tools_card_insert_index(workspace.links, tools_idx)
    tools_card = workspace.links[tools_idx]
    tools_card.link_count = (tools_card.link_count or 0) + 1

    workspace.append(
        "links",
        {
            "type": "Link",
            "label": MULTILEVEL_BOM_CREATOR_LABEL,
            "link_type": "DocType",
            "link_to": MULTILEVEL_BOM_CREATOR_DOCTYPE,
            "dependencies": "",
            "hidden": 0,
            "is_query_report": 0,
            "onboard": 0,
            "link_count": 0,
        },
        position=insert_idx,
    )

    workspace.flags.ignore_permissions = True
    workspace.save(ignore_permissions=True)


def remove_multilevel_bom_creator_from_manufacturing_workspace_links():
    if not frappe.db.exists("Workspace", MANUFACTURING_WORKSPACE):
        return

    workspace = frappe.get_doc("Workspace", MANUFACTURING_WORKSPACE)
    link_idx = _find_link_index(workspace.links, MULTILEVEL_BOM_CREATOR_DOCTYPE)

    if link_idx is None:
        return

    tools_idx = _find_tools_card_index_before(workspace.links, link_idx)
    if tools_idx is not None:
        tools_card = workspace.links[tools_idx]
        if tools_card.link_count:
            tools_card.link_count -= 1

    workspace.remove(workspace.links[link_idx])
    workspace.flags.ignore_permissions = True
    workspace.save(ignore_permissions=True)


def add_multilevel_bom_creator_to_manufacturing_sidebar():
    if not frappe.db.exists("Workspace Sidebar", MANUFACTURING_SIDEBAR):
        return

    if _sidebar_item_exists(MULTILEVEL_BOM_CREATOR_DOCTYPE):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", MANUFACTURING_SIDEBAR)
    insert_idx = _find_sidebar_tools_insert_index(sidebar.items)

    if insert_idx is None:
        return

    sidebar.append(
        "items",
        {
            "type": "Link",
            "label": MULTILEVEL_BOM_CREATOR_LABEL,
            "link_type": "DocType",
            "link_to": MULTILEVEL_BOM_CREATOR_DOCTYPE,
            "child": 1,
            "collapsible": 1,
            "indent": 0,
            "keep_closed": 0,
            "show_arrow": 0,
        },
        position=insert_idx,
    )

    sidebar.flags.ignore_permissions = True
    sidebar.save(ignore_permissions=True)


def remove_multilevel_bom_creator_from_manufacturing_sidebar():
    if not frappe.db.exists("Workspace Sidebar", MANUFACTURING_SIDEBAR):
        return

    sidebar_item_names = frappe.get_all(
        "Workspace Sidebar Item",
        filters={
            "parent": MANUFACTURING_SIDEBAR,
            "parenttype": "Workspace Sidebar",
            "link_to": MULTILEVEL_BOM_CREATOR_DOCTYPE,
            "type": "Link",
        },
        pluck="name",
    )

    if not sidebar_item_names:
        return

    for sidebar_item_name in sidebar_item_names:
        frappe.delete_doc(
            "Workspace Sidebar Item",
            sidebar_item_name,
            force=False,
            ignore_permissions=True,
        )


def _workspace_link_exists(link_to):
    return frappe.db.exists(
        "Workspace Link",
        {
            "parent": MANUFACTURING_WORKSPACE,
            "parenttype": "Workspace",
            "link_to": link_to,
            "type": "Link",
        },
    )


def _sidebar_item_exists(link_to):
    return frappe.db.exists(
        "Workspace Sidebar Item",
        {
            "parent": MANUFACTURING_SIDEBAR,
            "parenttype": "Workspace Sidebar",
            "link_to": link_to,
            "type": "Link",
        },
    )


def _find_tools_card_index(links):
    for index, link in enumerate(links):
        if link.type == "Card Break" and link.label == TOOLS_CARD_LABEL:
            return index

    return None


def _find_tools_card_index_before(links, link_idx):
    for index in range(link_idx - 1, -1, -1):
        if links[index].type == "Card Break":
            return index

    return None


def _find_tools_card_insert_index(links, tools_idx):
    insert_idx = tools_idx + 1
    for index in range(tools_idx + 1, len(links)):
        if links[index].type == "Card Break":
            break
        insert_idx = index + 1

    return insert_idx


def _find_link_index(links, link_to):
    for index, link in enumerate(links):
        if link.type == "Link" and link.link_to == link_to:
            return index

    return None


def _find_sidebar_tools_section_index(items):
    for index, item in enumerate(items):
        if item.type == "Section Break" and item.label == TOOLS_CARD_LABEL:
            return index

    return None


def _find_sidebar_tools_insert_index(items):
    tools_idx = _find_sidebar_tools_section_index(items)
    if tools_idx is None:
        return None

    for index in range(tools_idx + 1, len(items)):
        item = items[index]
        if item.type == "Section Break" and not item.child:
            break
        if item.type == "Link" and item.link_to == "BOM Creator":
            return index + 1

    return _find_sidebar_tools_end_index(items, tools_idx)


def _find_sidebar_tools_end_index(items, tools_idx):
    insert_idx = tools_idx + 1
    for index in range(tools_idx + 1, len(items)):
        if items[index].type == "Section Break" and not items[index].child:
            break
        insert_idx = index + 1

    return insert_idx
import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node import BOMTreeNode, BOMTreeNodeFactory
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item.multilevel_bom_creator_item import MultilevelBOMCreatorItem


class BOMTree:
    def __init__(self, root_node: BOMTreeNode):
        self.root = root_node

    def to_dict(self) -> dict:
        """
        Convert Node (and its children) into a JSON-serializable dict.
        """
        return self._to_dict_recursive(self.root)

    def _to_dict_recursive(self, node: BOMTreeNode) -> dict:
        data = dict(node.__dict__)

        # Recursively convert children
        data["children"] = [
            self._to_dict_recursive(child) for child in node.children
        ]

        return data

    def to_depth_first_flat_list(self) -> list[dict]:
        rows: list[dict] = []
        self._to_depth_first_flat_list_recursive(self.root, rows)
        return rows

    def _to_depth_first_flat_list_recursive(self, node: BOMTreeNode, rows: list[dict]) -> None:
        row = dict(node.__dict__)
        row_children = node.children if node.children else []

        # Remove children property from flat row
        row.pop("children", None)

        rows.append(row)

        for child in row_children:
            self._to_depth_first_flat_list_recursive(child, rows)


class BOMTreeFactory:
    def __init__(self, bom_creator_doc):
        self.bom_creator_doc = bom_creator_doc
        self.items: list[MultilevelBOMCreatorItem] = bom_creator_doc.get("items", [
        ])

    def create(self) -> BOMTree:
        return self._build_tree()

    def _build_tree(self) -> BOMTree:
        if not self.bom_creator_doc:
            frappe.throw("BOM Creator document is required to build BOM Tree.")

        root_item = next((
            item for item in self.items if not item.parent_node_guid
        ), None)
        if not root_item:
            frappe.throw("BOM Creator document has no root item.")

        root_node = BOMTreeNodeFactory.create_from_multilevel_bom_creator_item(
            root_item)
        self._add_child_item_nodes_recursively(root_node)

        tree = BOMTree(root_node)
        return tree

    def _add_child_item_nodes_recursively(self, parent_node: BOMTreeNode):
        child_items = [
            item for item in self.items if item.parent_node_guid == parent_node.node_guid and (item.node_type == "ITEM" or item.node_type == "SUB_ASSEMBLY")
        ]
        sorted_child_items = sorted(child_items, key=lambda x: x.sequence)

        for item in sorted_child_items:
            child_node = BOMTreeNodeFactory.create_from_multilevel_bom_creator_item(
                item)
            self._add_child_item_nodes_recursively(child_node)
            parent_node.add_child(child_node)

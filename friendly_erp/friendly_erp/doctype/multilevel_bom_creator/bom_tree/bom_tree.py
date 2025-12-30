import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node import BOMTreeNode, BOMTreeNodeFactory
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item.multilevel_bom_creator_item import MultilevelBOMCreatorItem


class BOMTree:
    def __init__(self, root_node: BOMTreeNode, node_map: dict, leaf_nodes: list[BOMTreeNode]):
        self.root = root_node
        self.node_map = node_map
        self.leaf_nodes: list[BOMTreeNode] = leaf_nodes

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
        for child in data["children"]:
            # Remove parent references to avoid circular references in JSON
            child.pop("parent_node_ref", None)

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
        # Remove parent reference to avoid circular refs
        row.pop("parent_node_ref", None)

        rows.append(row)

        for child in row_children:
            self._to_depth_first_flat_list_recursive(child, rows)

    def find_node_by_unique_id(self, node_unique_id: str) -> BOMTreeNode | None:
        return self.node_map.get(node_unique_id, None)


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
            item for item in self.items if not item.parent_node_unique_id
        ), None)
        if not root_item:
            frappe.throw("BOM Creator document has no root item.")

        root_node = BOMTreeNodeFactory.create_from_multilevel_bom_creator_item(
            root_item, None)
        node_map = {root_node.node_unique_id: root_node}
        leaf_node_list: list[BOMTreeNode] = []

        self._add_children_recursively(
            root_node, node_map, leaf_node_list)
        
        tree = BOMTree(root_node, node_map, leaf_node_list)
        return tree
    
    def _add_children_recursively(self, parent_node: BOMTreeNode, node_map: dict, leaf_node_list: list[BOMTreeNode]):
        self._add_child_operation_nodes_recursively(
            parent_node, node_map, leaf_node_list)
        self._add_child_item_nodes_recursively(
            parent_node, node_map, leaf_node_list)

    def _add_child_item_nodes_recursively(self, parent_node: BOMTreeNode, node_map: dict, leaf_node_list: list[BOMTreeNode]):
        child_items = [
            item for item in self.items if item.parent_node_unique_id == parent_node.node_unique_id and (item.node_type == "ITEM" or item.node_type == "SUB_ASSEMBLY")
        ]

        # LEAF NODE DETECTION
        if not child_items:
            leaf_node_list.append(parent_node)
            return

        sorted_child_items = sorted(child_items, key=lambda x: x.sequence)

        for item in sorted_child_items:
            child_node = BOMTreeNodeFactory.create_from_multilevel_bom_creator_item(
                item, parent_node)
            parent_node.add_child(child_node)
            node_map[child_node.node_unique_id] = child_node
            self._add_children_recursively(
                child_node, node_map, leaf_node_list)
            
    def _add_child_operation_nodes_recursively(self, parent_node: BOMTreeNode, node_map: dict, leaf_node_list: list[BOMTreeNode]):
        child_items = [
            item for item in self.items if item.parent_node_unique_id == parent_node.node_unique_id and (item.node_type == "OPERATION")
        ]

        # LEAF NODE DETECTION
        if not child_items:
            leaf_node_list.append(parent_node)
            return

        sorted_child_items = sorted(child_items, key=lambda x: x.sequence)

        for item in sorted_child_items:
            child_node = BOMTreeNodeFactory.create_from_multilevel_bom_creator_item(
                item, parent_node)
            parent_node.add_child(child_node)
            node_map[child_node.node_unique_id] = child_node
            self._add_children_recursively(
                child_node, node_map, leaf_node_list)

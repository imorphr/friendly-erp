import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node import (
    BOMTreeNode, 
    BOMCreatorTreeNodeFactory,
    ExistingBOMTreeNodeFactory
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode


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


class BOMCreatorTreeBuilder:
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

        root_node = BOMCreatorTreeNodeFactory.create_from_multilevel_bom_creator_item(
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
            child_node = BOMCreatorTreeNodeFactory.create_from_multilevel_bom_creator_item(
                item, parent_node)
            parent_node.add_child(child_node)
            node_map[child_node.node_unique_id] = child_node
            self._add_children_recursively(
                child_node, node_map, leaf_node_list)
            if item.node_type == "SUB_ASSEMBLY" and item.bom_no and not child_node.children:
                existing_bom_tree =ExistingBOMTreeBuilder(
                    item.bom_no, child_node, item.sequence, node_map, leaf_node_list
                ).create()
                # Attach existing BOM tree's children to the current child_node
                for existing_child in existing_bom_tree.root.children:
                    child_node.add_child(existing_child)
            
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
            child_node = BOMCreatorTreeNodeFactory.create_from_multilevel_bom_creator_item(
                item, parent_node)
            parent_node.add_child(child_node)
            node_map[child_node.node_unique_id] = child_node
            self._add_children_recursively(
                child_node, node_map, leaf_node_list)

# TODO: leaf_node_list population is pending
class ExistingBOMTreeBuilder:
    def __init__(self, bom_name: str, parent_node_ref: BOMTreeNode | None = None, sequence: int = 0, node_map: dict = None, leaf_node_list: list[BOMTreeNode] = None):
        self.bom_name = bom_name
        self.node_map = node_map if node_map is not None else {}
        self.leaf_node_list = leaf_node_list if leaf_node_list is not None else []
        self.parent_node_ref = parent_node_ref
        self.sequence = sequence

    def create(self) -> BOMTree:
        root_node = self._traverse_bom(self.bom_name, self.parent_node_ref, self.sequence)
        tree = BOMTree(root_node, self.node_map, self.leaf_node_list)
        return tree

    def _traverse_bom(self, bom_name, parent_node_ref, sequence) -> BOMTreeNode:
        bom = frappe.get_doc("BOM", bom_name)
        if not bom:
            frappe.throw(f"BOM '{bom_name}' not found.")

        root_node = ExistingBOMTreeNodeFactory.create_from_existing_bom(
            bom, parent_node_ref, sequence)
        self.node_map[root_node.node_unique_id] = root_node
        self._add_children_recursively(bom, root_node)
        return root_node
        
    def _add_children_recursively(self, bom, parent_node: BOMTreeNode):
        self._add_child_operation_nodes(bom, parent_node)
        self._add_child_item_nodes(bom, parent_node)

    def _add_child_item_nodes(self, bom, parent_node_ref: BOMTreeNode):
        items = bom.items or []
        for bom_item in items:
            is_sub_assembly = self._is_item_representing_sub_assembly(bom_item)
            should_not_explode = self._should_not_explode(bom_item)
            child_node = None
            if is_sub_assembly and not should_not_explode:
                child_node = self._traverse_bom(
                    bom_item.bom_no, parent_node_ref, bom_item.idx)
            else:
                child_node = ExistingBOMTreeNodeFactory.create_from_existing_bom_item(
                    bom_item, parent_node_ref, bom_item.idx)
            parent_node_ref.add_child(child_node)
            self.node_map[child_node.node_unique_id] = child_node

    def _add_child_operation_nodes(self, bom, parent_node_ref: BOMTreeNode):
        operations = bom.operations or []
        for bom_operation in operations:
            child_node = ExistingBOMTreeNodeFactory.create_from_existing_bom_operation(
                bom_operation, parent_node_ref, bom_operation.idx)
            parent_node_ref.add_child(child_node)
            self.node_map[child_node.node_unique_id] = child_node

    def _is_item_representing_sub_assembly(self, item) -> bool:
        return bool(item.bom_no)


    def _should_not_explode(self, item) -> bool:
        return item.do_not_explode
        
# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext.stock.get_item_details import get_conversion_factor

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeSubAssemblyNode
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_builders import BOMCreatorTreeBuilder
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_cost_calculator import BOMTreeCostCalculationHelper, BOMTreeCostCalculator
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node_factories import BOMTreeNodeToCreatorItemConverter
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_qty_time_calculator import BOMTreeQtyTimeCalculator
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.tree_to_bom import TreeToBOMConverter
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.multilevel_bom_creator_name_generator import MultilevelBOMCreatorNameGenerator
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode


class MultilevelBOMCreator(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

        amended_from: DF.Link | None
        buying_price_list: DF.Link | None
        company: DF.Link
        company_currency: DF.Link | None
        conversion_rate: DF.Float
        currency: DF.Link
        description: DF.LongText | None
        item_code: DF.Link
        item_nodes: DF.Table[MultilevelBOMCreatorItemNode]
        operation_nodes: DF.Table[MultilevelBOMCreatorOperationNode]
        plc_conversion_rate: DF.Float
        price_list_currency: DF.Link | None
        qty: DF.Float
        rm_cost_as_per: DF.Literal["Valuation Rate",
                                   "Last Purchase Rate", "Price List"]
        set_rate_of_sub_assembly_item_based_on_bom: DF.Check
        uom: DF.Link
    # end: auto-generated types

    def autoname(self):
        self.name = MultilevelBOMCreatorNameGenerator.generate(self)

    def validate(self) -> None:
        if not self.item_code:
            frappe.throw("Item Code is required.")
        if not self.company:
            frappe.throw("Company is required.")
        if not self.qty or self.qty <= 0:
            frappe.throw("Quantity must be greater than zero.")

        self.assert_price_list_currency_is_valid()

        if self.is_new():
            stock_uom = self._get_stock_uom(self.item_code)
            self.uom = stock_uom

    def before_save(self) -> None:
        if not self.item_nodes:
            self.add_root_item()

        if not self.company_currency:
            self.company_currency = frappe.get_value(
                "Company", self.company, "default_currency"
            )

        if not self.is_new() and self._has_rm_cost_relevant_change():
            # Update cost calculation for whole tree as cost related fields has been changed
            # Passing "*" for "fetch_fresh_rate_for_node_ids" to fetch fresh rate for all nodes.
            self.update_quantity_time_and_cost(
                BOMCreatorTreeBuilder(self).create(), {"*"}
            )

    def before_submit(self) -> None:
        total_count = len(self.item_nodes or []) + \
            len(self.operation_nodes or [])
        if total_count < 2:
            frappe.throw("No child items or operations found.")
        self.create_boms()

    def _has_rm_cost_relevant_change(self) -> bool:
        """
        Returns True if rm_cost_as_per or buying_price_list
        has changed compared to previous saved state.
        """
        if self.is_new():
            return True

        before = self.get_doc_before_save()
        if not before:
            return True

        return (
            before.rm_cost_as_per != self.rm_cost_as_per
            or before.buying_price_list != self.buying_price_list
            or before.plc_conversion_rate != self.plc_conversion_rate
        )

    def assert_price_list_currency_is_valid(self) -> None:
        """
        Validate that Price List currency matches either:
        - Multilevel BOM Creator currency, or
        - Company default currency
        """
        if not self.rm_cost_as_per == "Price List":
            return

        if not self._has_rm_cost_relevant_change():
            return

        if not self.buying_price_list:
            frappe.throw(
                _("Buying Price List is required when RM Cost As Per is 'Price List'."))

        price_list_currency = frappe.get_value(
            "Price List", self.buying_price_list, "currency"
        )

        if not price_list_currency:
            frappe.throw(_("Currency not found for Price List {0}.").format(
                self.buying_price_list))

        if price_list_currency not in {self.currency, self.company_currency}:
            frappe.throw(
                _(
                    "Currency mismatch in Buying Price List.<br><br>"
                    "Price List Currency: <b>{0}</b><br>"
                    "Allowed Currencies: <b>{1}</b>, <b>{2}</b>"
                ).format(price_list_currency, self.currency, self.company_currency)
            )

    def assert_unique_node_id(self, unique_id: str) -> None:
        """
        Ensure the given unique_id is not already used in item or operation nodes.
        """

        if not unique_id:
            frappe.throw("Unique ID cannot be empty.")

        # Check item nodes
        for node in self.item_nodes:
            if node.node_unique_id == unique_id:
                frappe.throw(
                    f"Duplicate node unique_id detected: '{unique_id}' "
                    f"(already used in Item nodes)"
                )

        # Check operation nodes
        for node in self.operation_nodes:
            if node.node_unique_id == unique_id:
                frappe.throw(
                    f"Duplicate node unique_id detected: '{unique_id}' "
                    f"(already used in Operation nodes)"
                )

    def add_root_item(self) -> None:
        """Add the root item to the BOM creator document."""
        self.ensure_draft_status()
        if self.item_nodes:
            frappe.throw("Root item already exists.")

        item: MultilevelBOMCreatorItemNode = frappe.new_doc(
            "Multilevel BOM Creator Item Node")
        # Here use shorter unique id as it is going to be stored in db
        unique_id = frappe.generate_hash(length=10)
        self.assert_unique_node_id(unique_id)
        item.node_unique_id = unique_id
        item.parent_node_unique_id = None
        item.node_type = "SUB_ASSEMBLY"
        item.item_code = self.item_code
        item.component_qty_per_parent_bom_run = self.qty or 1.0
        item.own_batch_size = self.qty or 1.0
        item.total_required_qty = self.qty or 1.0
        item.bom_run_count = 1  # For root node bom run count is 1
        item.uom = self.uom
        item.stock_uom = self.uom  # For root node bom uom is same as item's stock uom
        # For root node bom conversion factor is 1 as uom and stock uom are same
        item.conversion_factor = 1.0
        item.sequence = 1
        self.append("item_nodes", item)

    def add_item(self, parent_node_unique_id: str, item_code: str, component_qty_per_parent_bom_run: float, uom: str, rate: float) -> None:
        """Add a new item under the specified parent node."""
        self.ensure_draft_status()
        if not component_qty_per_parent_bom_run or component_qty_per_parent_bom_run <= 0:
            frappe.throw(
                "Quantity per parent BOM run must be greater than zero.")

        has_bom = self._has_active_bom(item_code)
        stock_uom = self._get_stock_uom(item_code)
        conversion_factor = self._get_conversion_factor_for_uom_to_stock_uom(
            item_code, uom)

        item: MultilevelBOMCreatorItemNode = frappe.new_doc(
            "Multilevel BOM Creator Item Node")
        # Here use shorter unique id as it is going to be stored in db
        unique_id = frappe.generate_hash(length=10)
        self.assert_unique_node_id(unique_id)
        item.node_unique_id = unique_id
        item.parent_node_unique_id = parent_node_unique_id
        item.node_type = "ITEM"
        item.item_code = item_code
        item.do_not_explode = True if has_bom else False
        item.component_qty_per_parent_bom_run = component_qty_per_parent_bom_run
        item.own_batch_size = None  # Leaf items are not boms, so own_batch_size is None
        item.uom = uom
        item.stock_uom = stock_uom
        item.conversion_factor = conversion_factor
        item.component_stock_qty_per_parent_bom_run = component_qty_per_parent_bom_run * \
            conversion_factor

        item.sequence = self._get_child_item_node_sequence(
            parent_node_unique_id)
        item.is_stock_item = self._is_stock_item(item_code)
        # For non stock item consider user given rate
        if not item.is_stock_item and rate:
            item.base_rate = rate * (self.conversion_rate or 1.0)
        self.append("item_nodes", item)

        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        parent_node = tree.find_node_by_unique_id(parent_node_unique_id)
        if not parent_node:
            frappe.throw(
                f"Parent node with ID {parent_node_unique_id} not found.")

        if not parent_node.can_add_child_item:
            frappe.throw(
                f"Cannot add item under node '{parent_node.display_name}'. "
                f"Adding child items is not allowed for this node."
            )

        if tree.item_node_exists_in_upward_path(parent_node_unique_id, item_code):
            frappe.throw(
                f"Item '{item_code}' already exists as a direct or indirect parent. Item can not be child of itself."
            )

        parent_item = next((
            item for item in self.item_nodes if item.node_unique_id == parent_node_unique_id
        ), None)

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            frappe.throw(
                f"Parent node '{parent_item.display_name}' is not a Sub-Assembly. "
                f"Adding child items is not allowed for this node."
            )

        self.update_quantity_time_and_cost(tree, {unique_id})

    def update_item(self, node_unique_id: str, component_qty_per_parent_bom_run: float, uom: str, rate: float) -> None:
        self.ensure_draft_status()

        if not component_qty_per_parent_bom_run or component_qty_per_parent_bom_run <= 0:
            frappe.throw(
                _("Quantity per parent BOM run must be greater than zero."))

        item = next(
            (row for row in self.item_nodes if row.node_unique_id == node_unique_id),
            None
        )

        if not item:
            frappe.throw(_("Item node not found."))

        if item.node_type != "ITEM":
            frappe.throw(_("update_item can only be used for ITEM nodes."))

        stock_uom = self._get_stock_uom(item.item_code)
        conversion_factor = self._get_conversion_factor_for_uom_to_stock_uom(
            item.item_code, uom)

        item.component_qty_per_parent_bom_run = component_qty_per_parent_bom_run
        item.uom = uom
        item.stock_uom = stock_uom
        item.conversion_factor = conversion_factor
        item.component_stock_qty_per_parent_bom_run = component_qty_per_parent_bom_run * \
            conversion_factor
        # For non stock item consider user given rate
        if not item.is_stock_item:
            item.base_rate = rate * (self.conversion_rate or 1.0) if rate else 0.0
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        self.update_quantity_time_and_cost(tree, {item.node_unique_id})

    def add_new_sub_assembly(self, parent_node_unique_id: str, item_code: str, component_qty_per_parent_bom_run: float, own_batch_size: float, uom: str) -> None:
        self._add_sub_assembly_internal(
            parent_node_unique_id, item_code, None, component_qty_per_parent_bom_run, own_batch_size, uom)

    def update_new_sub_assembly(self, node_unique_id: str, component_qty_per_parent_bom_run: float, own_batch_size: float, uom: str) -> None:
        self._update_sub_assembly_internal(
            node_unique_id, component_qty_per_parent_bom_run, own_batch_size, uom)

    def add_existing_sub_assembly(self, parent_node_unique_id: str, bom_no: str, component_qty_per_parent_bom_run: float, uom: str) -> None:
        self._add_sub_assembly_internal(
            parent_node_unique_id, None, bom_no, component_qty_per_parent_bom_run, None, uom)

    def update_existing_sub_assembly(self, node_unique_id: str, component_qty_per_parent_bom_run: float) -> None:
        self._update_sub_assembly_internal(
            node_unique_id, component_qty_per_parent_bom_run, None, None)

    def _add_sub_assembly_internal(self, parent_node_unique_id: str, item_code: str, bom_no: str, component_qty_per_parent_bom_run: float, own_batch_size: float, uom: str) -> None:
        self.ensure_draft_status()
        if not bom_no and not item_code:
            frappe.throw("Either BOM name or Item code must be provided.")

        is_stock_item = 0
        if not bom_no:
            is_stock_item = self._is_stock_item(item_code)
            # To create BOM for an item, item must be stock item
            if not is_stock_item:
                frappe.throw(f"Item {item_code} is not a stock item.")

        if not component_qty_per_parent_bom_run or component_qty_per_parent_bom_run <= 0:
            frappe.throw(
                "Quantity per parent BOM run must be greater than zero.")

        if not bom_no and not own_batch_size > 0:
            frappe.throw(
                "Own BOM Quantity must be provided for new sub-assembly.")

        bom = None
        if bom_no:
            # Existing Sub-Assembly
            bom = frappe.get_doc("BOM", bom_no)
            if not bom:
                frappe.throw(f"Could not find bom {bom.name}")
            if bom.docstatus != 1:
                frappe.throw(_("Selected BOM must be submitted"))
            if not bom.is_active:
                frappe.throw(_("Selected BOM is not active"))
            if bom.company != self.company:
                frappe.throw(_("Selected BOM belongs to a different company"))
            if bom.currency != self.currency:
                frappe.throw(
                    _("Selected BOM currency does not match Multilevel BOM Creator currency"))

        item_code_to_use = bom.item if bom else item_code
        stock_uom = bom.uom if bom else self._get_stock_uom(item_code_to_use)
        conversion_factor = self._get_conversion_factor_for_uom_to_stock_uom(
            item_code_to_use, uom)

        item: MultilevelBOMCreatorItemNode = frappe.new_doc(
            "Multilevel BOM Creator Item Node")
        # Here use shorter unique id as it is going to be stored in db
        unique_id = frappe.generate_hash(length=10)
        self.assert_unique_node_id(unique_id)
        item.node_unique_id = unique_id
        item.parent_node_unique_id = parent_node_unique_id
        item.node_type = "SUB_ASSEMBLY"
        item.item_code = item_code_to_use
        # For new sub-assembly, bom_no is None
        item.bom_no = bom_no if bom_no else None
        # For new sub-assembly, is_preexisting_bom is False
        item.is_preexisting_bom = True if bom_no else False
        item.do_not_explode = False
        item.component_qty_per_parent_bom_run = component_qty_per_parent_bom_run
        # if it is existing bom get own_batch_size from bom else from parameter
        # own_batch_size is always in "Stock UOM"
        item.own_batch_size = bom.quantity if bom else own_batch_size
        item.uom = uom
        item.stock_uom = stock_uom
        item.conversion_factor = conversion_factor
        item.component_stock_qty_per_parent_bom_run = component_qty_per_parent_bom_run * \
            conversion_factor

        item.sequence = self._get_child_item_node_sequence(
            parent_node_unique_id)
        item.is_stock_item = 1  # When we reach here item must be stock item
        self.append("item_nodes", item)

        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        parent_node = tree.find_node_by_unique_id(parent_node_unique_id)
        if not parent_node:
            frappe.throw(
                f"Parent node with ID {parent_node_unique_id} not found.")

        if not parent_node.can_add_child_item:
            frappe.throw(
                f"Cannot add sub-assembly under node '{parent_node.display_name}'. "
                f"Adding child sub-assembly is not allowed for this node."
            )

        parent_item = next((
            item for item in self.item_nodes if item.node_unique_id == parent_node_unique_id
        ), None)

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            frappe.throw(
                f"Parent node '{parent_item.display_name}' is not a Sub-Assembly. "
                f"Adding child items is not allowed for this node."
            )

        if tree.item_node_exists_in_upward_path(parent_node_unique_id, item_code_to_use):
            frappe.throw(
                f"Item '{item_code_to_use}' already exists as a direct or indirect parent. Item can not be child of itself."
            )

        self.update_quantity_time_and_cost(tree, {unique_id})

    def _update_sub_assembly_internal(self, node_unique_id: str, component_qty_per_parent_bom_run: float, own_batch_size: float, uom: str) -> None:
        self.ensure_draft_status()

        if not component_qty_per_parent_bom_run or component_qty_per_parent_bom_run <= 0:
            frappe.throw(
                _("Quantity per parent BOM run must be greater than zero."))

        item = next(
            (row for row in self.item_nodes if row.node_unique_id == node_unique_id),
            None
        )

        if not item:
            frappe.throw(_("Sub-Assembly node not found."))

        if item.node_type != "SUB_ASSEMBLY":
            frappe.throw(
                _("update_new_sub_assembly can only be used for Sub-Assembly nodes."))

        if not item.is_preexisting_bom and (not own_batch_size or own_batch_size <= 0):
            frappe.throw(_("Own BOM Quantity must be greater than zero."))

        item.component_qty_per_parent_bom_run = component_qty_per_parent_bom_run
        if not item.is_preexisting_bom:
            item.own_batch_size = own_batch_size

        item.uom = uom
        conversion_factor = self._get_conversion_factor_for_uom_to_stock_uom(
            item.item_code, item.uom)

        item.conversion_factor = conversion_factor
        item.component_stock_qty_per_parent_bom_run = component_qty_per_parent_bom_run * \
            conversion_factor

        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        self.update_quantity_time_and_cost(tree, {item.node_unique_id})

    def add_operation(self, parent_node_unique_id: str, operation: str, time_in_mins: float, fixed_time: bool, workstation_type: str, workstation: str) -> None:
        """Add a new operation under the specified parent node."""
        self.ensure_draft_status()
        if not workstation and not workstation_type:
            frappe.throw(
                "Provide atleast one of Workstation Type and Workstation")
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        parent_node = tree.find_node_by_unique_id(parent_node_unique_id)
        if not parent_node:
            frappe.throw(
                f"Parent node with ID {parent_node_unique_id} not found.")

        if not parent_node.can_add_child_operation:
            frappe.throw(
                f"Cannot add operation under node '{parent_node.display_name}'. "
                f"Adding child operations is not allowed for this node."
            )

        parent_item = next((
            item for item in self.item_nodes if item.node_unique_id == parent_node_unique_id
        ), None)

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            frappe.throw(
                f"Parent node '{parent_item.display_name}' is not a Sub-Assembly. "
                f"Adding child operation is not allowed for this node."
            )

        operation_doc: MultilevelBOMCreatorOperationNode = frappe.new_doc(
            "Multilevel BOM Creator Operation Node")
        # Here use shorter unique id as it is going to be stored in db
        unique_id = frappe.generate_hash(length=10)
        self.assert_unique_node_id(unique_id)
        operation_doc.node_unique_id = unique_id
        operation_doc.parent_node_unique_id = parent_node_unique_id
        operation_doc.node_type = "OPERATION"
        operation_doc.operation = operation
        operation_doc.time_in_mins = time_in_mins
        operation_doc.fixed_time = fixed_time
        operation_doc.workstation_type = workstation_type
        operation_doc.workstation = workstation if not workstation_type else None
        operation_doc.sequence = self._get_child_operation_node_sequence(
            parent_node_unique_id)
        self.append("operation_nodes", operation_doc)

        self.update_quantity_time_and_cost(tree, {unique_id})

    def update_operation(self, node_unique_id: str, time_in_mins: float, fixed_time: bool, workstation_type: str, workstation: str) -> None:
        self.ensure_draft_status()
        if not workstation and not workstation_type:
            frappe.throw(
                "Provide atleast one of Workstation Type and Workstation")

        operation_doc = next(
            (
                row for row in self.operation_nodes
                if row.node_unique_id == node_unique_id
            ),
            None
        )

        if not operation_doc:
            frappe.throw("Operation node not found.")

        operation_doc.time_in_mins = time_in_mins
        operation_doc.fixed_time = fixed_time
        operation_doc.workstation_type = workstation_type
        operation_doc.workstation = workstation if not workstation_type else None

        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        self.update_quantity_time_and_cost(
            tree, {operation_doc.node_unique_id})

    def duplicate_bom_structure(self, node_unique_id: str) -> None:
        self.ensure_draft_status()
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        node: BOMTreeSubAssemblyNode = tree.find_node_by_unique_id(
            node_unique_id)
        if not node:
            frappe.throw(_("Invalid node. Node does not exist in BOM tree."))
        if node.node_type != "SUB_ASSEMBLY":
            frappe.throw(
                _("BOM structure can only be duplicated for Sub-Assembly nodes.")
            )
        if not node.parent_node_ref:
            frappe.throw(
                _("Root node can not be duplicated.")
            )
        if node.is_projected:
            frappe.throw(
                _("Projected nodes cannot be expanded or duplicated.")
            )
        if not node.is_preexisting_bom:
            frappe.throw(
                _("Only pre-existing BOMs can be duplicated.")
            )
        if not node.bom_no:
            frappe.throw(
                _("BOM is not present for the node")
            )

        # All existing children (if any) must be projected nodes
        for child in node.children or []:
            if not child.is_projected:
                frappe.throw(
                    _(
                        "BOM structure cannot be duplicated because this Sub-Assembly "
                        "already contains non-projected child nodes."
                    )
                )
            if child.node_type == "ITEM":
                item = BOMTreeNodeToCreatorItemConverter.convert_item_node(
                    child)
                self.assert_unique_node_id(item.node_unique_id)
                self.append("item_nodes", item)
            elif child.node_type == "SUB_ASSEMBLY":
                sub_assembly = BOMTreeNodeToCreatorItemConverter.convert_sub_assembly_node(
                    child)
                self.assert_unique_node_id(sub_assembly.node_unique_id)
                self.append("item_nodes", sub_assembly)
            elif child.node_type == "OPERATION":
                operation = BOMTreeNodeToCreatorItemConverter.convert_operation_node(
                    child)
                self.assert_unique_node_id(operation.node_unique_id)
                self.append("operation_nodes", operation)

        # change parent item as now it has actual children
        parent_creator_item = next(
            (
                row for row in self.item_nodes
                if row.node_unique_id == node_unique_id
            ),
            None
        )

        if not parent_creator_item:
            frappe.throw(
                _("Internal error: Sub-Assembly item not found in creator document.")
            )

        parent_creator_item.bom_no = None
        parent_creator_item.is_preexisting_bom = False
        parent_creator_item.do_not_explode = False

    def delete_item_or_operation(self, node_unique_id: str) -> None:
        self.ensure_draft_status()
        if not node_unique_id:
            frappe.throw("Node unique id is required")

        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        node = tree.find_node_by_unique_id(node_unique_id)
        if not node:
            frappe.throw(f"Node '{node_unique_id}' not found")
        if not node.can_delete:
            frappe.throw(f"Node '{node.display_name}' cannot be deleted")
        node_ids_to_delete = tree.get_descendant_node_ids(node_unique_id)
        # Delete operation nodes
        self.operation_nodes = [
            row for row in (self.operation_nodes or [])
            if row.node_unique_id not in node_ids_to_delete
        ]
        # Delete item nodes
        self.item_nodes = [
            row for row in (self.item_nodes or [])
            if row.node_unique_id not in node_ids_to_delete
        ]

        updated_tree = BOMCreatorTreeBuilder(self).create()
        self.update_quantity_time_and_cost(updated_tree, None)

    def create_boms(self) -> dict[str, str]:
        """
        Create ERPNext BOMs from the multilevel BOM tree and
        persist bom_no back to creator items.
        Returns: {node_unique_id: bom_no}
        """

        # 1. Build tree
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()

        # 2. Convert tree → BOMs
        converter = TreeToBOMConverter(tree, self)
        converter.convert()

        # 3. Persist bom_no back to child table
        node_id_to_bom = converter.newly_created_boms or {}

        for row in self.item_nodes:
            bom_no = node_id_to_bom.get(row.node_unique_id)
            if bom_no:
                row.bom_no = bom_no

        return node_id_to_bom

    def _get_child_item_node_sequence(self, parent_node_unique_id: str) -> int:
        """Get the next sequence number for a child item under the specified parent node."""
        child_item_nodes = [
            item_nd for item_nd in self.item_nodes if item_nd.parent_node_unique_id == parent_node_unique_id
        ]
        if not child_item_nodes:
            return 1
        return max(nd.sequence for nd in child_item_nodes) + 1

    def _get_child_operation_node_sequence(self, parent_node_unique_id: str) -> int:
        """Get the next sequence number for a child operation under the specified parent node."""
        child_operation_nodes = [
            op_nd for op_nd in self.operation_nodes if op_nd.parent_node_unique_id == parent_node_unique_id
        ]
        if not child_operation_nodes:
            return 1
        return max(nd.sequence for nd in child_operation_nodes) + 1

    def _has_active_bom(self, item_code: str) -> bool:
        return frappe.db.exists(
            "BOM",
            {
                "item": item_code,
                "company": self.company,
                "is_active": 1,
                "docstatus": 1
            }
        )

    def ensure_draft_status(self):
        if self.docstatus != 0:
            frappe.throw("Can not change submitted document.")

    def _get_stock_uom(self, item_code: str) -> str:
        return frappe.get_value(
            "Item",
            item_code,
            "stock_uom"
        )

    def _is_stock_item(self, item_code: str) -> bool:
        return frappe.get_value(
            "Item",
            item_code,
            "is_stock_item"
        )

    def _get_conversion_factor_for_uom_to_stock_uom(self, item_code: str, uom: str) -> float:
        return get_conversion_factor(item_code, uom).get("conversion_factor") or 1.0

    def _get_node_item_map(self) -> dict:
        node_item_map = {}
        for item in self.item_nodes:
            node_item_map[item.node_unique_id] = item
        for operation in self.operation_nodes:
            node_item_map[operation.node_unique_id] = operation
        return node_item_map

    def update_quantity_time_and_cost(self, tree: BOMTree, fetch_fresh_rate_for_node_ids: set) -> None:
        self._update_qty_and_time(tree)
        self._update_cost(tree, fetch_fresh_rate_for_node_ids)

    def _update_qty_and_time(self, tree: BOMTree) -> None:
        qty_time_calculator = BOMTreeQtyTimeCalculator(
            tree.root, self._get_node_item_map())
        qty_time_calculator.calculate()

    def _update_cost(self, tree: BOMTree, fetch_fresh_rate_for_node_ids: set) -> None:
        cost_calculator = BOMTreeCostCalculator(
            self, tree.root, self._get_node_item_map(), fetch_fresh_rate_for_node_ids)
        cost_calculator.calculate()


@frappe.whitelist()
def get_tree_flat(multilevel_bom_creator_name: str) -> list[dict]:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    tree: BOMTree = BOMCreatorTreeBuilder(
        multilevel_bom_creator, True).create()
    return tree.to_depth_first_flat_list()


@frappe.whitelist()
def add_item(multilevel_bom_creator_name: str, parent_node_unique_id: str, item_code: str, component_qty_per_parent_bom_run: float, uom: str, rate: float=None) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_item(
        parent_node_unique_id, item_code, component_qty_per_parent_bom_run, uom, rate)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def update_item(multilevel_bom_creator_name: str, node_unique_id: str, component_qty_per_parent_bom_run: float, uom: str, rate: float=None) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.update_item(
        node_unique_id, component_qty_per_parent_bom_run, uom, rate)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def add_new_sub_assembly(multilevel_bom_creator_name: str, parent_node_unique_id: str, item_code: str, component_qty_per_parent_bom_run: float, own_batch_size: float, uom: str) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_new_sub_assembly(
        parent_node_unique_id, item_code, component_qty_per_parent_bom_run, own_batch_size, uom)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def update_new_sub_assembly(multilevel_bom_creator_name: str, node_unique_id: str, component_qty_per_parent_bom_run: float, own_batch_size: float, uom: str) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.update_new_sub_assembly(
        node_unique_id, component_qty_per_parent_bom_run, own_batch_size, uom)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def add_existing_sub_assembly(multilevel_bom_creator_name: str, parent_node_unique_id: str, bom_no: str, component_qty_per_parent_bom_run: float, uom: str) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_existing_sub_assembly(
        parent_node_unique_id, bom_no, component_qty_per_parent_bom_run, uom)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def update_existing_sub_assembly(multilevel_bom_creator_name: str, node_unique_id: str, component_qty_per_parent_bom_run: float) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.update_existing_sub_assembly(
        node_unique_id, component_qty_per_parent_bom_run)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def add_operation(multilevel_bom_creator_name: str, parent_node_unique_id: str, operation: str, time_in_mins: float, fixed_time: bool, workstation_type: str = None, workstation: str = None) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_operation(
        parent_node_unique_id, operation, time_in_mins, fixed_time, workstation_type, workstation)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def update_operation(multilevel_bom_creator_name: str, node_unique_id: str, time_in_mins: float, fixed_time: bool, workstation_type: str = None, workstation: str = None) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.update_operation(
        node_unique_id, time_in_mins, fixed_time, workstation_type, workstation)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def duplicate_bom_structure(
    multilevel_bom_creator_name: str,
    node_unique_id: str
) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.duplicate_bom_structure(node_unique_id)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def delete_item_or_operation(multilevel_bom_creator_name: str, node_unique_id: str) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.delete_item_or_operation(node_unique_id)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()

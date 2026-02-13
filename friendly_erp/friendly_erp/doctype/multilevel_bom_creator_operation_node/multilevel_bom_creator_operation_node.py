# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class MultilevelBOMCreatorOperationNode(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		base_amount: DF.Currency
		base_hour_rate: DF.Currency
		base_rate: DF.Currency
		batch_size: DF.Int
		fixed_time: DF.Check
		hour_rate: DF.Currency
		node_type: DF.Literal["OPERATION"]
		node_unique_id: DF.Data | None
		operation: DF.Link | None
		parent: DF.Data
		parent_node_unique_id: DF.Data | None
		parentfield: DF.Data
		parenttype: DF.Data
		rate: DF.Currency
		sequence: DF.Int
		set_cost_based_on_bom_qty: DF.Check
		time_in_mins: DF.Float
		total_required_amount: DF.Currency
		total_required_time_in_mins: DF.Float
		workstation: DF.Link | None
		workstation_type: DF.Link | None
	# end: auto-generated types
	pass

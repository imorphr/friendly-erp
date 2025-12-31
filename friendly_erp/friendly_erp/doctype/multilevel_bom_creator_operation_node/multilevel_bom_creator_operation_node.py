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

		node_type: DF.Literal["OPERATION"]
		node_unique_id: DF.Data | None
		operation: DF.Link | None
		parent: DF.Data
		parent_node_unique_id: DF.Data | None
		parentfield: DF.Data
		parenttype: DF.Data
		sequence: DF.Int
		time_in_mins: DF.Float
		workstation: DF.Link | None
		workstation_type: DF.Link | None
	# end: auto-generated types
	pass

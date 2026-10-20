# -*- coding: utf-8 -*-
"""The tag, printed from the PIECE.

Why the piece
-------------
A serial number belongs to the piece, not to the model: two identical rings share one
product and carry a number each. The tag is what tells them apart on the counter, so it
has to be printable from the record that holds the number -- and that record is the lot.

This is also the more operative of the two doors. The serial and the GIA certificate are
typed in when the goods are received, on this very screen, so the tag can be printed in
the same movement instead of hunting for the model afterwards.

No drawing of its own
---------------------
Both methods hand off to the variant, passing the serial. There is ONE geometry and one
chatter format for the whole module; what changes here is only where the number comes from
and where the record of the print is kept -- on the piece, which is what was printed.

The method names are the variant's on purpose: the button widget reads the model off the
record it sits on, so the same button works on both screens with no branch in the browser.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = "stock.lot"

    # The piece's real weight, in grams -- NOT a product attribute. A chain model sells
    # at a different weight piece to piece (it is precious metal, not a manufactured
    # tolerance), so a per-model attribute would mean a new value, and for serialised
    # metal a new variant, for every gram the scale happens to read. The piece is what
    # carries one weight, which is why this lives next to the serial, the same place the
    # GIA certificate goes (see the module docstring above).
    weight_grams = fields.Float(
        "Weight (g)", digits=(16, 2),
        help="Actual weight of THIS piece, in grams. Varies piece to piece even for the "
             "same model -- that is why it lives on the serial number, not on a product "
             "attribute.")

    def get_jewelry_label_zpl(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("This serial number has no product, so there is no tag to "
                              "print: the tag reads the model's SKU, description and "
                              "price."))
        return self.product_id.get_jewelry_label_zpl(serial=self.name)

    def action_log_printed_label(self, impreso=True):
        self.ensure_one()
        return self.product_id._post_label_to(
            self, self.get_jewelry_label_zpl(), impreso=impreso)

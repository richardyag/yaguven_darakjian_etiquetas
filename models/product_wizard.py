# -*- coding: utf-8 -*-
"""Guided product creation: the category decides what is asked.

Why
---
Loading a product today means choosing among 189 attributes with nothing telling you
which eight matter for the piece in your hand. Measured on this catalogue: 81% of the
watches print one cell or none. The tag is where the shop meets the system, so the moment
to get the data right is when it is typed, not afterwards.

Here the category comes first and the form builds itself from its setup: the attributes
are given, the person only picks values, and the dropdown is already narrowed to that
attribute. Nobody has to know which eight matter.

No dynamic fields
-----------------
The wizard has ONE one2many. The onchange on `categ_id` fills it with a line per
configured attribute. Add an attribute to a category and the line shows up by itself, with
no code and no view to touch -- which is what makes the whole thing configurable by
whoever knows the pieces.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class YagProductWizard(models.TransientModel):
    _name = "yag.product.wizard"
    _description = "Guided product creation"

    name = fields.Char("Product name", required=True)
    categ_id = fields.Many2one("product.category", "Category", required=True)
    default_code = fields.Char("Internal reference")
    standard_price = fields.Float("Cost")
    list_price = fields.Float("Sales price")
    image_1920 = fields.Image("Photo", max_width=1920, max_height=1920)
    # Odoo 19 splits what used to be one field: `type` says what it is, `is_storable`
    # whether its stock is followed, and `tracking` how each unit is told apart.
    type = fields.Selection(
        [("consu", "Goods"), ("service", "Service"), ("combo", "Combo")],
        "Product type", required=True, default="consu")
    is_storable = fields.Boolean("Track inventory", default=True)
    tracking = fields.Selection(
        [("none", "By quantity"), ("lot", "By lots"), ("serial", "By unique serial number")],
        "Traceability", required=True, default="none",
        help="A serial number is where the identity of the physical piece lives -- it is "
             "where the GIA certificate goes. Choose it for a piece that is unique.")
    line_ids = fields.One2many("yag.product.wizard.line", "wizard_id", "Attributes")

    # Surfaced, never acted on by itself: whether this looks like a model already loaded.
    # Manual loading should SHOW the collision and let the person decide -- merging two
    # models silently is how a catalogue ends up wrong in a way nobody can trace.
    modelo_existente_id = fields.Many2one(
        "product.template", "Existing model", readonly=True)
    # When it is opened from a purchase, the piece goes straight onto the order: the
    # moment the buyer has the supplier's information in front of them is the moment the
    # data is right, and asking them to come back later is asking for the empty cells this
    # whole thing exists to prevent.
    purchase_order_id = fields.Many2one("purchase.order", readonly=True)
    aviso = fields.Char("Notice", readonly=True)

    @api.onchange("type")
    def _onchange_type(self):
        """A service has no stock to follow and no unit to tell apart."""
        if self.type != "consu":
            self.is_storable = False
            self.tracking = "none"

    @api.onchange("is_storable")
    def _onchange_is_storable(self):
        if not self.is_storable:
            self.tracking = "none"

    @api.onchange("categ_id")
    def _onchange_categ_id(self):
        """The category builds the form. This is the whole idea of the wizard."""
        self.line_ids = [(5, 0, 0)]
        if not self.categ_id:
            return
        _origen, config = self.categ_id._yag_tag_config()
        self.line_ids = [(0, 0, {
            "attribute_id": linea.attribute_id.id,
            "sequence": linea.sequence,
            # La casilla dejo de ser un texto en la linea y paso a ser un registro
            # (`yag.tag.cell`) el 2026-08-31: esta lectura quedo apuntando al campo viejo
            # y reventaba el onchange -- el wizard entero, que es la pantalla por la que la
            # tienda carga cada pieza.
            "slot": linea.cell_id.name or "",
            "admite_varios": linea.admite_varios,
            "obligatorio": linea.obligatorio,
        }) for linea in config.sorted("sequence")]
        if not config:
            self.aviso = _("This category has no tag setup yet, so there is nothing to "
                           "ask for. Set it up on the category first.")
        else:
            self.aviso = False

    @api.onchange("name", "categ_id")
    def _onchange_name(self):
        """Look for a model that already exists before creating another one.

        Our loading scripts created one template per SKU and split models the shop keeps
        together -- the same watch in two dial colours ended up as two products. Manual
        loading would repeat it one piece at a time.
        """
        self.modelo_existente_id = False
        if not self.name or not self.categ_id:
            return
        tmpl = self.env["product.template"].search(
            [("name", "=ilike", self.name.strip()),
             ("categ_id", "=", self.categ_id.id)], limit=1)
        if tmpl:
            self.modelo_existente_id = tmpl
            self.aviso = _(
                "A model with this name already exists in this category with %s "
                "version(s). If this piece is another version of it -- another dial "
                "colour, another size -- add the value there instead of creating a "
                "second model."
            ) % tmpl.product_variant_count

    def action_crear(self):
        self.ensure_one()
        # Required attributes and "at least one value loaded" used to block saving here
        # (raise UserError). Business decision 2026-09-11: loading must never be blocked
        # by missing attribute data -- receiving staff often don't have every spec on hand
        # yet. An empty cell on the tag is acceptable and expected; it gets filled in later
        # from the product form. Both blocking checks were removed for that reason.
        cargadas = self.line_ids.filtered("value_ids")

        tmpl = self.env["product.template"].create({
            "name": self.name.strip(),
            "categ_id": self.categ_id.id,
            "type": self.type,
            "is_storable": self.is_storable if self.type == "consu" else False,
            "tracking": self.tracking if self.is_storable and self.type == "consu" else "none",
            "list_price": self.list_price,
            "standard_price": self.standard_price,
            "image_1920": self.image_1920,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": l.attribute_id.id,
                "value_ids": [(6, 0, l.value_ids.ids)],
            }) for l in cargadas],
        })
        variantes = tmpl.product_variant_ids
        if len(variantes) == 1 and self.default_code:
            variantes.default_code = self.default_code

        if self.purchase_order_id and len(variantes) == 1:
            self.env["purchase.order.line"].create({
                "order_id": self.purchase_order_id.id,
                "product_id": variantes.id,
                "product_qty": 1,
                "price_unit": self.standard_price,
            })
            return {"type": "ir.actions.act_window",
                    "res_model": "purchase.order",
                    "res_id": self.purchase_order_id.id,
                    "view_mode": "form", "target": "current"}
        # Several versions came out and we do not guess which one was bought: the list
        # opens so the codes go in and the buyer picks the ones that belong on the order.
        # More than one version means one code each, and they are filled in a list rather
        # than opening them one by one: with thirteen colours that is thirteen openings.
        return {
            "type": "ir.actions.act_window",
            "name": _("Codes for each version of %s") % tmpl.name,
            "res_model": "product.product",
            "view_mode": "list,form",
            "domain": [("id", "in", variantes.ids)],
            "context": {"create": False},
        }


class YagProductWizardLine(models.TransientModel):
    _name = "yag.product.wizard.line"
    _description = "Guided product creation line"
    _order = "sequence, id"

    wizard_id = fields.Many2one("yag.product.wizard", required=True, ondelete="cascade")
    sequence = fields.Integer("Sequence", default=10)
    # None of these four is `readonly=True` on the field, and that is deliberate: from 17
    # on, the web client leaves a field the MODEL declares readonly out of the payload it
    # sends. The lines here are born in an onchange on the client, so their attribute_id
    # never reached the server and the create died on `required=True` -- the wizard could
    # not save a single product. The person still must not type over them: the view marks
    # them `readonly="1" force_save="1"`, which locks the cell and keeps the value.
    attribute_id = fields.Many2one("product.attribute", required=True)
    value_ids = fields.Many2many("product.attribute.value", string="Value")
    admite_varios = fields.Boolean("Several values allowed")
    obligatorio = fields.Boolean("Required")
    slot = fields.Char("Tag cell")

    @api.constrains("value_ids", "admite_varios")
    def _check_varios(self):
        """Several values are what makes Odoo generate the versions. Where the family did
        not allow it, one value: otherwise a piece that should be one turns into several,
        each with its own stock, and undoing that is not a one-liner."""
        for line in self:
            if len(line.value_ids) > 1 and not line.admite_varios:
                raise UserError(_(
                    "'%s' takes a single value on this family. Loading several would "
                    "create one version of the product per value."
                ) % line.attribute_id.name)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_yag_nuevo_producto(self):
        """Open the guided wizard from the purchase and come back with the line loaded."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "New product (guided)",
            "res_model": "yag.product.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_purchase_order_id": self.id},
        }

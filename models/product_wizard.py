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
    # What the tag will print empty, said WHILE there is still time to type it.
    # This used to be a UserError on the way out. That was the wrong place for it: the
    # person is holding the piece, and a wall at the last click does not get the value
    # typed -- it gets the load abandoned, or the "Required" flag torn off the category,
    # which breaks the setup for every piece that comes after. Here it says the same
    # thing with the form still open, and creating stays possible.
    aviso_vacias = fields.Char("Empty cells", compute="_compute_aviso_vacias")

    @api.depends("line_ids.value_ids", "line_ids.obligatorio")
    def _compute_aviso_vacias(self):
        for wiz in self:
            vacias = wiz.line_ids.filtered(
                lambda l: l.obligatorio and not l.value_ids)
            if vacias:
                wiz.aviso_vacias = _(
                    "These cells will print empty on the tag: %s. You can create the "
                    "product anyway."
                ) % ", ".join(vacias.mapped("attribute_id.name"))
            elif wiz.line_ids and not wiz.line_ids.filtered("value_ids"):
                wiz.aviso_vacias = _("No attribute carries a value: the tag will print "
                                     "empty. You can create the product anyway.")
            else:
                wiz.aviso_vacias = False

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
            "condicion_attribute_id": linea.condicion_attribute_id.id,
            "condicion_value_id": linea.condicion_value_id.id,
        }) for linea in config.sorted("sequence") if not linea.condicion_attribute_id]
        if not config:
            self.aviso = _("This category has no tag setup yet, so there is nothing to "
                           "ask for. Set it up on the category first.")
        else:
            self.aviso = False
        # Las lineas condicionadas (las que dependen de otro atributo) no entran todavia:
        # las agrega _onchange_line_values en cuanto la respuesta de la que dependen llega.

    def action_recalcular_atributos(self):
        """Button next to the list, not an automatic onchange.

        Tried twice to make this live as the person types -- onchange('line_ids') on the
        wizard (2026-10-21), then onchange('value_ids') on the line calling back into the
        wizard (2026-10-22). Confirmed over RPC both times that the computation itself is
        right: called directly, Diamond Shape comes in exactly when Diamond Origin is set
        to Lab Grown. What does not survive the trip is the CLIENT applying an onchange
        result that adds new rows to the very list being edited inline -- the same class
        of Owl rendering bug `tag_config_views.xml` already worked around by moving row
        edits into a dialog instead of inline (see its comment on that). A button is not
        magic, but a click is a plain server round-trip with nothing to reconcile live,
        which is the one thing confirmed not to break here.
        """
        self.ensure_one()
        self._recompute_condicionales()

    def _recompute_condicionales(self):
        """Add or drop conditional lines as the answers that gate them change.

        Rebuilding the whole set from scratch would lose whatever the person already
        typed on a line that stays visible, so this keeps what is there for every
        attribute that still applies and only adds or removes what changed.
        """
        if not self.categ_id or not self.line_ids:
            return
        _origen, config = self.categ_id._yag_tag_config()
        contestado = {l.attribute_id: l.value_ids for l in self.line_ids}

        def aplica(linea):
            if not linea.condicion_attribute_id:
                return True
            dado = contestado.get(linea.condicion_attribute_id)
            return bool(dado and linea.condicion_value_id in dado)

        deberian_estar = {l.attribute_id for l in config if aplica(l)}
        estan = set(contestado.keys())
        if deberian_estar == estan:
            return  # nada cambio, no tocar lo que la persona esta tipeando

        conservadas_vals = {attr: vals for attr, vals in contestado.items()
                            if attr in deberian_estar}
        nuevas = [(0, 0, {
            "attribute_id": linea.attribute_id.id,
            "sequence": linea.sequence,
            "slot": linea.cell_id.name or "",
            "admite_varios": linea.admite_varios,
            "obligatorio": linea.obligatorio,
            "condicion_attribute_id": linea.condicion_attribute_id.id,
            "condicion_value_id": linea.condicion_value_id.id,
            "value_ids": [(6, 0, conservadas_vals.get(linea.attribute_id, self.env["product.attribute.value"]).ids)],
        }) for linea in config.sorted("sequence") if linea.attribute_id in deberian_estar]
        self.line_ids = [(5, 0, 0)] + nuevas

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
        # Nothing here refuses the save any more. An empty cell is announced by
        # `aviso_vacias` while the form is open and the piece is in the person's hand;
        # what it must never do is leave them with no way out but to go and untick
        # "Required" on the category, which is what happened in QA on 2026-09-11 and
        # takes the requirement away from every piece of that family, not just this one.
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
    # Carried over from `yag.tag.line` purely so `_recompute_condicionales` on the
    # wizard can tell, without a second trip to the category config, whether THIS line
    # is the one that gates some other line. Not shown on the form.
    condicion_attribute_id = fields.Many2one("product.attribute")
    condicion_value_id = fields.Many2one("product.attribute.value")

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

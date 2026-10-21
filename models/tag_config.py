# -*- coding: utf-8 -*-
"""What each family prints on its tag, configured on the product category.

Why the configuration lives here
--------------------------------
The eight cells were laid out for a ring with stones -- carat, clarity, colour, diamond
origin -- and the module decided what filled them with lists written in the code. That
worked while every piece was a jewel: a watch has none of those four, so the whole branch
printed them blank while the data a watch does carry had nowhere to go.

Measured over the 2,921 watch templates: with the jewellery lists only 3 watches print
four cells or more; reading the same attributes into cells that mean something for a
watch, 419 do. No data is loaded to get that.

The configuration hangs off `product.category` because the product already carries its
`categ_id`: the family is decided, nobody has to tag a piece by hand. And it inherits
along `parent_id`, so the branch is configured once -- 14 to 16 of them cover 99% of the
catalogue -- and its 146 leaves follow.

The line that does NOT belong here
----------------------------------
Whether a piece has versions is NOT a family decision, it is decided piece by piece when
loading: `Material` appears on 15,692 templates in the old system and opens variants on
744 of them, 4%. The same attribute, in the same category, sometimes describes and
sometimes offers a choice. So this model says WHAT IS PRINTED; how many values a given
product loads into a line stays with that product.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class YagTagCell(models.Model):
    """A printable spot on the cardboard.

    The eight cells used to be a list in the code, so adding one meant a deploy. They are
    records now: a cell is a position, and the caption is only ever shown on screen --
    THE TAG PRINTS THE VALUE ALONE, never a label, which is why adding a cell costs no
    room for text and only room for the value itself.

    What does not become configurable is the paper. The spec block has 72 usable dots of
    height and at the current type four rows fit and five do not; that is measured, not
    assumed. A third column fits across but narrow. So a ninth cell is possible and
    something has to give -- smaller type, or narrower columns -- and the point of having
    this as data is that the trade can be tried and undone without a deploy.
    """
    _name = "yag.tag.cell"
    _description = "A printable cell on the jewelry tag"
    _order = "fila, columna, id"

    name = fields.Char("Caption", required=True,
                       help="Shown on screen only. The tag prints the value alone.")
    code = fields.Char(required=True, help="Technical name, used by the tag builder.")
    fila = fields.Integer("Row", required=True, default=1)
    columna = fields.Integer("Column", required=True, default=1)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint("unique(code)", "That cell code already exists.")
    _pos_uniq = models.Constraint(
        "unique(fila, columna)", "There is already a cell in that row and column.")

    @api.constrains("fila", "columna")
    def _check_posicion(self):
        """The paper is what it is. Four rows fit at the current type and five do not --
        measured on the die-cut, not assumed -- so a fifth row would print off the card."""
        for cell in self:
            if cell.fila < 1 or cell.columna < 1:
                raise ValidationError("Row and column start at 1.")
            if cell.fila > 4:
                raise ValidationError(
                    "The spec block holds four rows at the current type: a fifth would "
                    "print off the cardboard. To fit more, the type has to get smaller "
                    "first.")


class YagTagLine(models.Model):
    _name = "yag.tag.line"
    _description = "Tag configuration line for a product category"
    _order = "sequence, id"

    category_id = fields.Many2one(
        "product.category", required=True, ondelete="cascade", index=True)
    attribute_id = fields.Many2one("product.attribute", required=True)
    sequence = fields.Integer("Sequence", default=10)
    cell_id = fields.Many2one(
        "yag.tag.cell", string="Tag cell", ondelete="restrict",
        help="Which of the eight cells this attribute prints in. Leave it empty for an "
             "attribute that should be loaded but not printed. Several attributes may "
             "share a cell: they are tried in order and the first one with a value wins.")
    admite_varios = fields.Boolean(
        "Several values allowed", default=False,
        help="Whether a product of this family may carry more than one value here, which "
             "is what makes Odoo generate its versions.")
    obligatorio = fields.Boolean(
        "Required", default=False,
        help="Counts towards the family's completeness figure and warns when it is empty.")
    create_variant = fields.Selection(
        related="attribute_id.create_variant", readonly=True)

    # Gating: this line is only asked when another line of the SAME category already
    # carries a specific value. "Does this piece have a center stone?" -> No means the
    # five Center Stone lines never show up for this product at all, instead of printing
    # blank cells someone has to notice are wrong. Left empty, the line always applies --
    # today's behaviour, unchanged.
    condicion_attribute_id = fields.Many2one(
        "product.attribute", "Only ask when",
        help="Leave empty to always ask this attribute. Set it to make this line "
             "conditional on another attribute of the same category already carrying "
             "the value chosen below -- it must already be configured on this category, "
             "or saving refuses it.")
    condicion_value_id = fields.Many2one(
        "product.attribute.value", "...equals",
        domain="[('attribute_id', '=', condicion_attribute_id)]")

    @api.constrains("condicion_attribute_id", "category_id")
    def _check_condicion_en_misma_categoria(self):
        for line in self:
            if not line.condicion_attribute_id:
                continue
            if line.condicion_attribute_id == line.attribute_id:
                raise ValidationError(_(
                    "'%s' cannot depend on itself.") % line.attribute_id.name)
            hermana = self.env["yag.tag.line"].search([
                ("category_id", "=", line.category_id.id),
                ("attribute_id", "=", line.condicion_attribute_id.id),
            ], limit=1)
            if not hermana:
                raise ValidationError(_(
                    "'%s' is set to depend on '%s', but that attribute is not "
                    "configured on this category yet -- add it first."
                ) % (line.attribute_id.name, line.condicion_attribute_id.name))

    # Odoo 19 declares SQL constraints as class attributes. `_sql_constraints` is NOT
    # honoured any more and fails SILENTLY: verified on 2026-08-31 against the live
    # database, where only the foreign keys had been created for this model -- and the
    # same is true of `yaguven_darakjian_pos_ticket`, which believes it has a unique
    # constraint and does not.
    _attr_por_categoria = models.Constraint(
        "unique(category_id, attribute_id)",
        "That attribute is already configured on this category.",
    )

    # A cell may hold SEVERAL attributes, and that is on purpose: the tag has always
    # worked by cascade -- Measure tries Ring Size, then Length, then Width, nine
    # candidates -- because those attributes are mutually exclusive by piece type. A
    # ring has a ring size, a necklace has a length, and no piece has both. The order
    # you drag them into IS the cascade, and the first one carrying a value wins.

    @api.constrains("admite_varios", "attribute_id")
    def _check_admite_varios(self):
        """The trap this constraint exists for: an attribute set to `no_variant` does NOT
        generate versions when it carries several values -- and on top of that it stops
        printing, because the tag reads single-valued lines from the template and the rest
        from the variant. It would be wrong both ways, with no error anywhere."""
        for line in self:
            if line.admite_varios and line.attribute_id.create_variant != "always":
                raise ValidationError(
                    "'%s' cannot take several values: it is set to '%s'. Only an "
                    "attribute that generates variants can, otherwise the versions are "
                    "never created and the attribute stops printing on the tag."
                    % (line.attribute_id.name, line.attribute_id.create_variant))


class ProductCategory(models.Model):
    _inherit = "product.category"

    yag_tag_line_ids = fields.One2many("yag.tag.line", "category_id", string="Tag setup")
    yag_tag_heredada_de = fields.Many2one(
        "product.category", compute="_compute_yag_tag", string="Setup inherited from",
        help="The branch this category takes its tag setup from.")
    yag_tag_lineas = fields.Integer(compute="_compute_yag_tag", string="Attributes printed")

    def _yag_tag_config(self):
        """The setup in force for this category: its own, or the nearest parent's.

        Walking up `parent_id` is what lets a branch be configured once. A leaf that
        really needs something different sets its own lines and stops inheriting.
        """
        # An empty recordset is a normal state, not an error: a product form that has
        # not been given a category yet computes its tag cells all the same, and asking
        # for the setup of no category has to answer "none" instead of blowing up.
        if not self:
            return self.browse(), self.env["yag.tag.line"]
        self.ensure_one()
        nodo = self
        while nodo:
            if nodo.yag_tag_line_ids:
                return nodo, nodo.yag_tag_line_ids
            nodo = nodo.parent_id
        return self.browse(), self.env["yag.tag.line"]

    @api.depends("yag_tag_line_ids", "parent_id")
    def _compute_yag_tag(self):
        for cat in self:
            origen, lineas = cat._yag_tag_config()
            cat.yag_tag_heredada_de = origen if origen != cat else False
            cat.yag_tag_lineas = len(lineas.filtered("cell_id"))


class YagTagOverride(models.Model):
    """One cell of one model, printing something other than what its family prints.

    Why a piece needs to disagree with its family
    ---------------------------------------------
    The family setup (`yag.tag.line`) is right for the family and wrong for the odd
    piece: a necklace in the Pearl branch prints the pearl type in the second cell
    because that is what the other four hundred pearls carry, and the one piece that
    has no pearl type but does have a gemstone printed that cell empty. Until now the
    only way out was to change the cell for all four hundred.

    So the override is per CELL, not per tag: the cells nobody touched keep following
    the family, and a branch that gets reorganised still reaches every piece except the
    one spot somebody deliberately moved.

    Why it hangs off the TEMPLATE and not off the variant
    -----------------------------------------------------
    Two reasons, and the second is the one that bites. First, what the tag prints comes
    from attributes that mostly live on the template: the gemological ones are
    `no_variant`, so they never hang off the variant at all. Second, adding a value to a
    variant-generating attribute makes Odoo ARCHIVE the live variants and create new
    ones -- the same trap `ProductTemplateAttributeLine` guards against below -- and an
    override stored on the variant would disappear with it, silently, leaving the tag
    quietly back on the family setup with nobody told.

    An empty `attribute_id` is a decision, not a blank record: it means this cell prints
    NOTHING on this model, which is the way to free a spot the family fills with
    something that does not apply here.
    """
    _name = "yag.tag.override"
    _description = "Tag cell override for one product model"
    _order = "cell_id, id"

    product_tmpl_id = fields.Many2one(
        "product.template", required=True, ondelete="cascade", index=True)
    cell_id = fields.Many2one(
        "yag.tag.cell", string="Tag cell", required=True, ondelete="cascade",
        help="The cell whose content this model changes.")
    attribute_id = fields.Many2one(
        "product.attribute", string="Prints instead",
        help="What this cell reads on this model. Leave it empty for the cell to print "
             "nothing here, which is how a spot the family fills is freed up.")

    # Odoo 19 declares SQL constraints as class attributes: `_sql_constraints` is not
    # honoured any more and fails SILENTLY -- see the note on `yag.tag.line`.
    _cell_por_modelo = models.Constraint(
        "unique(product_tmpl_id, cell_id)",
        "That cell already has an override on this model.",
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    yag_tag_override_ids = fields.One2many(
        "yag.tag.override", "product_tmpl_id", string="Tag cell overrides")

    def _yag_tag_overrides(self):
        """`{cell code: attribute name or None}` for this model.

        A key that is present with a value of None is NOT the same as a missing key: the
        first says "this model prints nothing here", the second says "this model has no
        opinion, follow the family". Collapsing the two would make an emptied cell fall
        back to the family setup, which is exactly what somebody emptying it did not want.
        """
        if not self:
            return {}
        self.ensure_one()
        return {ov.cell_id.code: (ov.attribute_id.name or None)
                for ov in self.yag_tag_override_ids if ov.cell_id}


class ProductTemplateAttributeLine(models.Model):
    """The guard against the silent archiving.

    Measured 2026-08-20, corrected 2026-09-04. What loses track of a piece is not a line
    that carries two values: it is a live variant whose COMBINATION stops existing. Odoo
    then archives it and creates fresh ones, and the code, the stock and the movements
    stay on the archived variant. Accounting still balances and the QA on amounts passes;
    what breaks is that the shop looks for the piece and finds it at zero. Nothing warns.

        no_variant, any number of values -> variants untouched, no risk
        ADDING a value to a live line    -> the existing combinations stay valid, so the
                                            live variant survives with its id and its code
        REPLACING or REMOVING a value    -> that combination is gone: Odoo archives it
        OPENING a new attribute line     -> every existing combination needs a value it
                                            does not have: same archiving

    The first version of this guard refused any second value on a variant-generating
    attribute whenever the variant held stock or had moved. That reads the risk from the
    wrong place: it blocked regrouping two pieces that v16 kept under one product (checked
    on production 2026-09-04 with a throwaway product: the live variant came out untouched)
    and stayed silent about the case that does break the link.

    So it no longer predicts: it lets Odoo recompute and then looks at the result, asking
    whether a variant holding stock or movements was left without its variant. Raising
    rolls the whole thing back, which is what makes checking afterwards both safe and
    exact.
    """
    _inherit = "product.template.attribute.line"

    @api.onchange("attribute_id")
    def _onchange_attribute_id(self):
        """From the Tag tab, an attribute starts with no values: the person picks one.

        Odoo fills in EVERY value of an attribute that does not create variants the moment
        it is chosen (core `_onchange_attribute_id`). On the template's own attributes tab
        that is a sensible default; on the Tag tab it is the opposite of what the person is
        doing, which is typing the one value of the piece in hand. Checked on production
        2026-09-12: picking Case Diameter to load "41mm" saved the watch with every
        diameter in the catalogue, and the tag reads from those lines.

        Only the Tag tab passes `yag_tag_tab`; everywhere else the core behaviour stays.
        """
        if not self.env.context.get("yag_tag_tab"):
            return super()._onchange_attribute_id()
        self.value_ids = self.value_ids.filtered(
            lambda pav: pav.attribute_id == self.attribute_id)

    @api.model
    def _yag_capturar(self, tmpl_ids):
        """The pieces at risk on these templates, before touching anything.

        Returns {variant id: label}. Only variants that hold stock or have already moved
        are worth protecting: an empty one that gets archived loses nothing.
        """
        tmpl_ids = [t for t in tmpl_ids if t]
        if not tmpl_ids:
            return {}
        variantes = self.env["product.product"].with_context(active_test=False).search(
            [("product_tmpl_id", "in", tmpl_ids)])
        if not variantes:
            return {}
        con_stock = variantes.filtered(lambda v: v.qty_available)
        # One read_group instead of one query per variant: this runs on every save of an
        # attribute line, and a model with thirteen colours would be thirteen queries.
        movidas_ids = {g["product_id"][0] for g in self.env["stock.move.line"].read_group(
            [("product_id", "in", variantes.ids)], ["product_id"], ["product_id"])}
        riesgo = con_stock | variantes.filtered(lambda v: v.id in movidas_ids)
        return {v.id: (v.default_code or v.display_name) for v in riesgo}

    @api.model
    def _yag_verificar(self, antes):
        """Did any of those pieces lose its variant? Raising rolls the whole thing back."""
        if not antes:
            return
        variantes = self.env["product.product"].with_context(
            active_test=False).browse(list(antes)).exists()
        # Gone entirely, or still there but archived: either way the piece lost the
        # variant that carried its code, its stock and its movements.
        perdidas = (set(antes) - set(variantes.ids)) | {v.id for v in variantes if not v.active}
        if perdidas:
            raise ValidationError(
                "This change leaves these pieces without their variant, and they carry "
                "stock or movements: %s.\n\n"
                "Their code, their stock and their history would stay behind on a variant "
                "nobody can see, and the shop would find them at zero. Adding a value to "
                "an existing attribute is safe; what breaks the link is replacing or "
                "removing one that a live piece is using, or opening a new attribute on a "
                "template that already has pieces. Move the stock out first, or keep the "
                "new version as its own product."
                % ", ".join(sorted(antes[i] for i in perdidas)))

    # The three doors that reach _create_variant_ids. An @api.constrains covers none of
    # them properly: it runs inside the model's own write, while Odoo recomputes the
    # variants afterwards, so it sees everything still alive and lets the damage through
    # (measured on production 2026-09-04 with a product carrying stock and a movement).
    # Capture before, let super() recompute, then look at what actually happened.

    @api.model_create_multi
    def create(self, vals_list):
        antes = self._yag_capturar([v.get("product_tmpl_id") for v in vals_list])
        lineas = super().create(vals_list)
        self._yag_verificar(antes)
        return lineas

    def write(self, vals):
        if not ({"value_ids", "attribute_id", "product_tmpl_id"} & set(vals)):
            return super().write(vals)
        antes = self._yag_capturar(self.product_tmpl_id.ids)
        res = super().write(vals)
        self._yag_verificar(antes)
        return res

    def unlink(self):
        antes = self._yag_capturar(self.product_tmpl_id.ids)
        res = super().unlink()
        self._yag_verificar(antes)
        return res

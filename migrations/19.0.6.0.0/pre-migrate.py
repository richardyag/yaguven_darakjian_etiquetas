# -*- coding: utf-8 -*-
"""Fixes an upgrade that fails on environments jumping straight from an old
version (5.2.0 and earlier, before data/tag_cells.xml was wired into the
manifest) to a much newer one in one shot.

`yag_tag_cell` rows with these codes can already exist on such environments
(created by an earlier, differently-shaped version of this module, before
the "cells are records, seeded by this noupdate XML" design existed) and can
already be referenced by real data in `yag_tag_line` — so they are NOT safe
to delete. Without this fix, the noupdate data file tries to INSERT a new
row with the same `code` and hits the unique constraint.

This instead adopts each pre-existing row under the external ID the data
file is about to use, so Odoo treats it as "already created" and updates it
in place (preserving its id, and therefore every `yag_tag_line` reference to
it) instead of trying to insert a duplicate.
"""

CELL_CODES = {
    "cell_carat_qty": "carat_qty",
    "cell_clarity": "clarity",
    "cell_color": "color",
    "cell_origin": "origin",
    "cell_clasp": "clasp",
    "cell_measure": "measure",
    "cell_karatage": "karatage",
    "cell_metal": "metal",
}

MODULE = "yaguven_darakjian_etiquetas"


def migrate(cr, version):
    cr.execute("SELECT to_regclass('yag_tag_cell')")
    if cr.fetchone()[0] is None:
        return

    for xml_id, code in CELL_CODES.items():
        cr.execute("SELECT id FROM yag_tag_cell WHERE code = %s", (code,))
        row = cr.fetchone()
        if not row:
            continue
        res_id = row[0]

        cr.execute(
            "SELECT id FROM ir_model_data WHERE module = %s AND name = %s",
            (MODULE, xml_id),
        )
        if cr.fetchone():
            continue

        cr.execute(
            """
            INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
            VALUES (%s, %s, 'yag.tag.cell', %s, true)
            """,
            (xml_id, MODULE, res_id),
        )

# -*- coding: utf-8 -*-
"""Fixes an upgrade that fails on environments jumping straight from an old
version (5.2.0 and earlier, before data/tag_cells.xml was wired into the
manifest) to a much newer one in one shot.

A previous failed attempt at that same jump can leave `yag_tag_cell` rows
committed without their matching `ir.model.data` entry (the table gets
created and populated, but the overall module upgrade then errors out later
and the bookkeeping that would let Odoo recognise "already applied" never
gets written). On retry, the noupdate data file tries to INSERT the same
rows again and hits the unique constraint on `code`.

This removes any such untracked/orphaned rows before the data file loads,
so the real (tracked) seed can be (re)created cleanly.
"""


def migrate(cr, version):
    cr.execute("SELECT to_regclass('yag_tag_cell')")
    if cr.fetchone()[0] is None:
        return
    cr.execute("""
        DELETE FROM yag_tag_cell t
        WHERE NOT EXISTS (
            SELECT 1 FROM ir_model_data d
            WHERE d.model = 'yag.tag.cell' AND d.res_id = t.id
        )
    """)

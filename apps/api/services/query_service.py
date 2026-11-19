"""Reusable selection of the most recent history row for each stock."""
from sqlalchemy import func, select
from sqlalchemy.orm import aliased


def latest_per_symbol(model, date_column):
    ranked = select(
        model,
        func.row_number().over(
            partition_by=model.nse_symbol,
            order_by=date_column.desc(),
        ).label("_rn"),
    ).subquery()
    return aliased(model, ranked), ranked.c._rn == 1

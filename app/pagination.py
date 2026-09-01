"""The `page`/`size` convention shared by every list endpoint.

`GET /api/instances` established the query pair and the `PageResponse` envelope; the
other list endpoints reuse both from here so the bounds, the counting and the page
arithmetic exist once rather than six times. The rules this module implements are
documented in docs/api/CONVENTIONS.md § 1, and why the other endpoints needed it is
docs/performance/PERFORMANCE_BUGS.md § PERF-07.
"""

from typing import Annotated, Any

from fastapi import Query
from sqlalchemy.orm import Query as OrmQuery
from sqlalchemy.sql import func

DEFAULT_SIZE = 10
MAX_SIZE = 100

# Reusable Annotated aliases rather than a `Query(...)` default repeated per endpoint:
# one definition means `size` cannot end up capped at 100 on one route and 50 on the
# next, and the descriptions below are what Swagger shows for all seven.
PageParam = Annotated[int, Query(ge=1, description="1-based page number")]
SizeParam = Annotated[
    int, Query(ge=1, le=MAX_SIZE, description=f"Rows per page (1-{MAX_SIZE})")
]


def paginate(
    query: OrmQuery, count_column: Any, page: int, size: int
) -> tuple[list, int, int]:
    """Return one page of `query` as `(items, total, totalPages)`.

    `total` is the row count after the query's filters and role scoping, which is what
    the envelope reports — never the table's row count.

    The count drops the `ORDER BY` first. A sort cannot change how many rows there are,
    but leaving it on makes the database sort the whole filtered set in order to count
    it, and on any non-primary-key sort that is a temp B-tree built and thrown away on
    every request (docs/performance/PERFORMANCE_BUGS.md § PERF-08). `count_column` is
    the entity's primary key, so the count selects one indexed column instead of every
    column of every row.
    """
    total = query.order_by(None).with_entities(func.count(count_column)).scalar() or 0
    items = query.offset((page - 1) * size).limit(size).all()
    total_pages = (total + size - 1) // size
    return items, total, total_pages

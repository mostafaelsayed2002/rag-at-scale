from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from ..core.config import settings

pool = AsyncConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    open=False,
)

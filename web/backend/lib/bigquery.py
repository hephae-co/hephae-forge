"""
BigQuery DML insert helper — mirrors src/lib/db/bigquery.ts.

Uses DML INSERT (not streaming insert) so rows are immediately available
for DML DELETE — critical for reliable test teardown.
"""

from __future__ import annotations

import datetime
from typing import Any

from google.cloud import bigquery

_PROJECT_ID = "hephae-co-dev"
DATASET = "hephae"

# Singleton BigQuery client
_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=_PROJECT_ID)
    return _client


async def bq_insert(table: str, row: dict[str, Any]) -> None:
    """
    Insert a single row via DML INSERT.

    Pass datetime objects for TIMESTAMP columns.
    None values are omitted (BigQuery inserts NULL by default for unspecified nullable columns).
    """
    client = _get_client()

    # Omit None values — BQ inserts NULL by default, and the client cannot infer
    # parameter types for None without explicit type hints.
    entries = {k: v for k, v in row.items() if v is not None}
    cols = list(entries.keys())
    params = []
    query_params = []

    for col in cols:
        val = entries[col]
        params.append(f"@{col}")

        if isinstance(val, datetime.datetime):
            query_params.append(bigquery.ScalarQueryParameter(col, "TIMESTAMP", val))
        elif isinstance(val, bool):
            query_params.append(bigquery.ScalarQueryParameter(col, "BOOL", val))
        elif isinstance(val, int):
            query_params.append(bigquery.ScalarQueryParameter(col, "INT64", val))
        elif isinstance(val, float):
            query_params.append(bigquery.ScalarQueryParameter(col, "FLOAT64", val))
        else:
            query_params.append(bigquery.ScalarQueryParameter(col, "STRING", str(val)))

    query = f"""
        INSERT INTO `{_PROJECT_ID}.{DATASET}.{table}`
        ({', '.join(cols)})
        VALUES ({', '.join(params)})
    """

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    query_job = client.query(query, job_config=job_config, location="US")
    query_job.result()  # Wait for completion

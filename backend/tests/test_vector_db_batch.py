"""Batch embedding similarity — single API call, preserved order."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import vector_db as vdb


@pytest.mark.asyncio
async def test_find_similar_clients_batch_single_embed_call_and_order():
    embed_inputs = []

    async def _fake_aembed_documents(texts):
        embed_inputs.extend(list(texts))
        return [[0.01] * vdb.EMBEDDING_DIMENSIONS for _ in texts]

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = _fake_aembed_documents

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 2

    fake_row = {
        "id": "c0",
        "name": "Client",
        "country": "PT",
        "profile_text": "profile",
        "similarity_score": 0.85,
    }

    async def _fake_fetch(_conn, _embedding, _n):
        return vdb._rows_to_similar_clients([fake_row])

    class _Acquire:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *args):
            pass

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = _Acquire()

    with patch.object(vdb, "get_azure_embeddings", return_value=mock_embeddings), patch.object(
        vdb.PostgresManager, "get_pool", AsyncMock(return_value=mock_pool)
    ), patch.object(vdb, "_fetch_similar_for_embedding", _fake_fetch):
        results = await vdb.find_similar_clients_batch(
            ["profile alpha", "profile beta"], n_results=1
        )

    assert embed_inputs == ["profile alpha", "profile beta"]
    assert len(results) == 2
    assert results[0][0]["similarity"] == 85.0
    assert results[1][0]["similarity"] == 85.0

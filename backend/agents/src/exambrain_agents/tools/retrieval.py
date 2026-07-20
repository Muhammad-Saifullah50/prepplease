"""Read-only semantic retrieval tool (contracts/tools.md, FR-012).

``search_course_content`` embeds the query via the platform embedding
gateway and runs a course-scoped pgvector cosine search over
``document_chunks``. Read-only: never inserts/updates/deletes (FR-019).
"""

import uuid
from typing import Any


async def search_course_content(
    course_id: uuid.UUID,
    query: str,
    limit: int = 8,
    *,
    embedder: Any = None,
    repo: Any = None,
) -> list[dict[str, Any]]:
    """Return ``{chunk_id, content, hierarchy, similarity}`` rows, best first.

    ``embedder``/``repo`` default to the platform LLMClient and the
    ingestion repository; tests inject fakes.
    """
    if embedder is None:
        from exambrain_shared.llm import LLMClient

        embedder = LLMClient()
    if repo is None:
        from exambrain_agents.repositories.ingestion import IngestionRepository

        repo = IngestionRepository()

    embedding = await embedder.embed(query)
    results: list[dict[str, Any]] = await repo.search_chunks(
        course_id, embedding, limit=limit
    )
    return results

"""Retrieval tool tests (T030, FR-012) — fake session, no model."""

import uuid

from exambrain_agents.tools.retrieval import search_course_content
from tests.conftest import FakeEmbedder, FakeIngestionRepo


async def test_search_embeds_query_and_ranks_by_cosine(
    fake_embedder: FakeEmbedder, ingestion_repo: FakeIngestionRepo
) -> None:
    course_id = uuid.uuid4()
    paper_id = ingestion_repo.add_paper(course_id, "k.pdf")
    # Chunk embedded with the same fake embedder → identical vector for
    # identical text, so the matching chunk ranks first.
    for i, content in enumerate(["entropy basics", "gas laws", "kinematics"]):
        emb = await fake_embedder.embed(content)
        await ingestion_repo.replace_chunks(
            course_id=course_id,
            source_s3_key=f"s{i}",
            past_paper_id=paper_id,
            chunks=[
                {
                    "content": content,
                    "position": 0,
                    "hierarchy": {"kind": "course_material", "slide": i},
                    "embedding": emb,
                }
            ],
        )

    results = await search_course_content(
        course_id,
        "entropy basics",
        limit=2,
        embedder=fake_embedder,
        repo=ingestion_repo,
    )
    assert len(results) == 2
    top = results[0]
    assert top["content"] == "entropy basics"
    assert set(top) == {"chunk_id", "content", "hierarchy", "similarity"}
    assert top["similarity"] >= results[1]["similarity"]
    # The query text itself was embedded (read-only path).
    assert "entropy basics" in fake_embedder.calls


async def test_search_is_course_scoped(
    fake_embedder: FakeEmbedder, ingestion_repo: FakeIngestionRepo
) -> None:
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    emb = await fake_embedder.embed("shared text")
    for course in (mine, theirs):
        await ingestion_repo.replace_chunks(
            course_id=course,
            source_s3_key=f"k-{course}",
            past_paper_id=None,
            chunks=[
                {
                    "content": "shared text",
                    "position": 0,
                    "hierarchy": {},
                    "embedding": emb,
                }
            ],
        )
    results = await search_course_content(
        mine, "shared text", embedder=fake_embedder, repo=ingestion_repo
    )
    chunk_courses = {
        ingestion_repo.chunks[r["chunk_id"]]["course_id"] for r in results
    }
    assert chunk_courses == {mine}

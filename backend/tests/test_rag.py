import pytest

from app.rag.ingest import load_and_chunk
from app.services.rag import RagService
from app.core.config import get_settings


@pytest.fixture(scope="module")
def rag_service():
    return RagService()


def test_ingestion_produces_expected_sections():
    settings = get_settings()
    chunks = load_and_chunk(settings.policy_doc_path, settings.chunk_size, settings.chunk_overlap)
    sections = {c.section for c in chunks}
    assert "Section 1: Home Water Damage Coverage" in sections
    assert "Section 2: Personal Property Protection" in sections


def test_relevant_query_returns_grounded_result_with_correct_source(rag_service):
    result = rag_service.query("Is water damage covered?")
    assert result.grounded is True
    assert any("Water Damage" in s["section"] for s in result.sources)
    assert any("pipe burst" in c.lower() for c in result.context_chunks)


def test_relevant_query_personal_property(rag_service):
    result = rag_service.query("Are jewelry items covered?")
    assert result.grounded is True
    assert any("Personal Property" in s["section"] for s in result.sources)


def test_irrelevant_query_is_not_grounded(rag_service):
    result = rag_service.query("What is the weather like today?")
    assert result.grounded is False
    assert result.context_chunks == []
    assert result.sources == []


def test_citations_come_from_actual_retrieved_sections(rag_service):
    """Guards against fabricated citations (Section 12): every source
    returned must be one of the real section titles in the policy doc."""
    settings = get_settings()
    chunks = load_and_chunk(settings.policy_doc_path, settings.chunk_size, settings.chunk_overlap)
    valid_sections = {c.section for c in chunks}

    result = rag_service.query("Is water damage covered?")
    for source in result.sources:
        assert source["section"] in valid_sections

"""Evaluate real local retrieval against expected PDF/page hits, without LLM calls."""

import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.database import Database
from app.providers.embeddings import OnnxMiniLmEmbeddingProvider
from app.providers.vector_store import ChromaVectorStore
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService


POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")
CASE_PATH = Path("evaluation/retrieval_cases.json")
CONVERSATION_ID = "retrieval-evaluation"


def main() -> None:
    """Index eight samples in temporary storage and fail if expected pages are missing.

    Page inclusion does not prove every relevant passage on that page was retrieved.
    """

    cases = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    policy_paths = sorted(POLICY_DIRECTORY.glob("*.pdf"))
    if len(policy_paths) != 8:
        raise RuntimeError(f"Expected 8 policy PDFs, found {len(policy_paths)}.")

    with TemporaryDirectory(prefix="adc-retrieval-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        settings = Settings(
            database_url=f"sqlite:///{temporary_path / 'evaluation.db'}",
            vector_store_path=str(temporary_path / "chroma"),
        )
        database = Database(settings.database_url)
        database.create_tables()
        embeddings = OnnxMiniLmEmbeddingProvider(
            cache_path=settings.model_cache_path,
            model_name=settings.embedding_model_name,
            dimension=settings.embedding_dimension,
        )
        vectors = ChromaVectorStore(
            path=settings.vector_store_path,
            collection_name=settings.vector_collection_name,
        )
        ingestion = IngestionService(
            database=database,
            embedding_provider=embeddings,
            vector_store=vectors,
            settings=settings,
        )
        retrieval = RetrievalService(
            embedding_provider=embeddings,
            vector_store=vectors,
            default_top_k=settings.retrieval_top_k,
        )

        for policy_path in policy_paths:
            ingestion.ingest(
                conversation_id=CONVERSATION_ID,
                filename=policy_path.name,
                content=policy_path.read_bytes(),
            )

        passed = 0
        answerable = 0
        category_totals: Counter[str] = Counter()
        category_passes: Counter[str] = Counter()

        for case in cases:
            results = retrieval.retrieve(
                conversation_id=CONVERSATION_ID,
                question=case["question"],
            )
            expected = {
                (item["filename"], item["page"])
                for item in case["expected_evidence"]
            }
            actual = {(result.filename, result.page_number) for result in results}

            if expected:
                answerable += 1
                category_totals[case["category"]] += 1
                case_passed = expected <= actual
                passed += int(case_passed)
                category_passes[case["category"]] += int(case_passed)
                status = "PASS" if case_passed else "MISS"
            else:
                status = "DIAGNOSTIC (no expected source)"

            print(f"\n[{status}] {case['id']}: {case['question']}")
            if expected:
                missing = sorted(expected - actual)
                if missing:
                    print(f"  missing: {missing}")
            for rank, result in enumerate(results, start=1):
                print(
                    f"  {rank}. {result.filename} p.{result.page_number} "
                    f"similarity={result.similarity:.3f} chunk={result.chunk_index}"
                )

        print("\nRetrieval summary")
        print(f"  answerable cases passed: {passed}/{answerable}")
        for category in sorted(category_totals):
            print(
                f"  {category}: "
                f"{category_passes[category]}/{category_totals[category]}"
            )
        database.close()

        if passed != answerable:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

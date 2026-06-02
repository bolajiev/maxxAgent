"""
RAG example: load documents, split into chunks, embed, and query via Retriever.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from maxxa_agent.rag.loader import Document, TextSplitter
from maxxa_agent.rag.retriever import LocalHashEmbedder, Retriever


def main() -> None:
    docs = [
        Document(
            text="MaxxAgentFramework uses a ReAct-style loop: THOUGHT -> ACTION -> OBSERVATION -> FINAL_ANSWER.",
            source="doc:react",
        ),
        Document(
            text=(
                "RAG (retrieval augmented generation) retrieves relevant chunks "
                "from a knowledge base before answering."
            ),
            source="doc:rag",
        ),
        Document(
            text="A sandboxed executor should use subprocess isolation, timeouts, and bounded output capture.",
            source="doc:sandbox",
        ),
    ]

    splitter = TextSplitter(chunk_size=120, chunk_overlap=20)
    chunks = []
    for d in docs:
        chunks.extend(splitter.split(d))

    retriever = Retriever(embedder=LocalHashEmbedder(dim=256))
    retriever.add_chunks(chunks)

    query = "How does ReAct work?"
    hits = retriever.query(query, top_k=3)
    print("Query:", query)
    for h in hits:
        print(f"- score={h['score']:.3f} source={h['source']} chunk_id={h['chunk_id']}")
        print("  ", h["text"])


if __name__ == "__main__":
    main()


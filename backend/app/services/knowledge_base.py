"""
Knowledge Base Service - Pinecone RAG for Medical Aesthetics
Loads knowledge from text files and provides context-aware responses.
"""

import os
import glob
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Lazy imports to handle missing packages gracefully
OpenAI = None
Pinecone = None

try:
    from openai import OpenAI
except ImportError:
    pass

try:
    # Pinecone SDK v8+
    from pinecone import Pinecone
except ImportError:
    try:
        # Fallback for older versions
        import pinecone as Pinecone
    except ImportError:
        pass

load_dotenv()

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "luxe-medspa-kb")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Path to knowledge base files
KB_DIR = Path(__file__).parent.parent.parent / "data" / "knowledge_base"


def load_knowledge_base_from_files() -> List[Dict]:
    """
    Load knowledge base content from text files in data/knowledge_base/.
    Splits files into chunks for better retrieval.
    """
    knowledge_items = []

    if not KB_DIR.exists():
        print(f"Knowledge base directory not found: {KB_DIR}")
        return []

    # Get all text files
    txt_files = sorted(glob.glob(str(KB_DIR / "*.txt")))

    for filepath in txt_files:
        filename = Path(filepath).stem
        category = filename.split("_", 1)[1] if "_" in filename else filename

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Split content into sections based on ## headers
        sections = []
        current_section = {"title": "", "content": ""}

        for line in content.split("\n"):
            if line.startswith("## "):
                # Save previous section
                if current_section["content"].strip():
                    sections.append(current_section)
                # Start new section
                current_section = {"title": line[3:].strip(), "content": ""}
            elif line.startswith("# "):
                # Main title - use as default section title
                if not current_section["title"]:
                    current_section["title"] = line[2:].strip()
            else:
                current_section["content"] += line + "\n"

        # Don't forget the last section
        if current_section["content"].strip():
            sections.append(current_section)

        # Create knowledge items for each section
        for i, section in enumerate(sections):
            if len(section["content"].strip()) > 50:  # Skip very short sections
                item_id = f"{filename}-{i}"
                knowledge_items.append(
                    {
                        "id": item_id,
                        "category": category,
                        "subcategory": filename,
                        "title": section["title"],
                        "content": section["content"].strip(),
                    }
                )

    print(
        f"Loaded {len(knowledge_items)} knowledge base sections from {len(txt_files)} files"
    )
    return knowledge_items


# Load knowledge base content
KNOWLEDGE_BASE_CONTENT = load_knowledge_base_from_files()


class KnowledgeBaseService:
    """
    Pinecone-based RAG for medical aesthetics knowledge.
    """

    def __init__(self):
        self.openai_client = None
        self.pinecone_client = None
        self.index = None
        self._initialized = False

        if OPENAI_API_KEY and OpenAI:
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

        if PINECONE_API_KEY and Pinecone:
            try:
                self.pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
                # Try to get existing index
                try:
                    self.index = self.pinecone_client.Index(PINECONE_INDEX_NAME)
                    self._initialized = True
                    print(f"Connected to Pinecone index: {PINECONE_INDEX_NAME}")
                except Exception:
                    print(
                        f"Index {PINECONE_INDEX_NAME} not found. Run initialize_index() to create."
                    )
            except Exception as e:
                print(f"Pinecone initialization error: {e}")

    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI."""
        if not self.openai_client:
            return []

        # Truncate text if too long
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars]

        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding

    def initialize_index(self, recreate: bool = False) -> bool:
        """
        Create Pinecone index and upload knowledge base.
        Call this once during setup.

        Args:
            recreate: If True, delete and recreate the index
        """
        if not self.pinecone_client:
            print("Pinecone not configured. Add PINECONE_API_KEY to .env")
            return False

        if not self.openai_client:
            print("OpenAI not configured. Add OPENAI_API_KEY to .env")
            return False

        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pinecone_client.list_indexes()]

            if PINECONE_INDEX_NAME in existing_indexes:
                if recreate:
                    print(f"Deleting existing index: {PINECONE_INDEX_NAME}")
                    self.pinecone_client.delete_index(PINECONE_INDEX_NAME)
                else:
                    print(
                        f"Index {PINECONE_INDEX_NAME} already exists. Use recreate=True to rebuild."
                    )
                    self.index = self.pinecone_client.Index(PINECONE_INDEX_NAME)
                    self._initialized = True
                    return True

            # Create index
            print(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")
            self.pinecone_client.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=1536,  # text-embedding-3-small dimension
                metric="cosine",
                spec={"serverless": {"cloud": "aws", "region": "us-east-1"}},
            )

            # Wait for index to be ready
            import time

            print("Waiting for index to be ready...")
            time.sleep(10)

            self.index = self.pinecone_client.Index(PINECONE_INDEX_NAME)

            # Upsert knowledge base content in batches
            vectors = []
            print(
                f"Generating embeddings for {len(KNOWLEDGE_BASE_CONTENT)} sections..."
            )

            for i, item in enumerate(KNOWLEDGE_BASE_CONTENT):
                print(
                    f"  Processing {i + 1}/{len(KNOWLEDGE_BASE_CONTENT)}: {item['title'][:50]}..."
                )
                embedding = self._get_embedding(item["content"])
                if embedding:
                    vectors.append(
                        {
                            "id": item["id"],
                            "values": embedding,
                            "metadata": {
                                "category": item["category"],
                                "subcategory": item["subcategory"],
                                "title": item["title"],
                                "content": item["content"][:1500],  # Store more content
                            },
                        }
                    )

            # Batch upsert (100 at a time)
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                self.index.upsert(vectors=batch)
                print(
                    f"  Uploaded batch {i // batch_size + 1}/{(len(vectors) + batch_size - 1) // batch_size}"
                )

            print(
                f"Successfully uploaded {len(vectors)} knowledge base entries to Pinecone!"
            )
            self._initialized = True
            return True

        except Exception as e:
            print(f"Error initializing Pinecone index: {e}")
            import traceback

            traceback.print_exc()
            return False

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Search knowledge base for relevant content.
        """
        # Try Pinecone first
        if self._initialized and self.index and self.openai_client:
            try:
                query_embedding = self._get_embedding(query)
                if query_embedding:
                    results = self.index.query(
                        vector=query_embedding, top_k=top_k, include_metadata=True
                    )

                    return [
                        {
                            "title": match.metadata.get("title", ""),
                            "content": match.metadata.get("content", ""),
                            "category": match.metadata.get("category", ""),
                            "score": match.score,
                        }
                        for match in results.matches
                    ]
            except Exception as e:
                print(f"Pinecone search error: {e}")

        # Fallback to keyword search
        return self._fallback_search(query, top_k)

    def _fallback_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Simple keyword-based fallback search.
        """
        query_lower = query.lower()
        scored_results = []

        for item in KNOWLEDGE_BASE_CONTENT:
            score = 0
            content_lower = item["content"].lower()
            title_lower = item["title"].lower()

            # Keyword matching
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 2:
                    if word in title_lower:
                        score += 3
                    if word in content_lower:
                        score += 1

            if score > 0:
                scored_results.append(
                    {
                        "title": item["title"],
                        "content": item["content"],
                        "category": item["category"],
                        "score": score,
                    }
                )

        # Sort by score and return top_k
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def get_context_for_query(self, query: str) -> str:
        """
        Get formatted context string for LLM injection.
        """
        results = self.search(query)

        if not results:
            return ""

        context_parts = ["RELEVANT KNOWLEDGE BASE INFORMATION:"]
        for i, result in enumerate(results, 1):
            context_parts.append(f"\n[{i}] {result['title']}:")
            # Take more content for context
            context_parts.append(result["content"][:800])

        return "\n".join(context_parts)


# Singleton instance
knowledge_base = KnowledgeBaseService()

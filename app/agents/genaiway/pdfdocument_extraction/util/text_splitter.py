import textwrap
from datetime import datetime


class TextSplitter:
    def split_text_into_chunks(self, pages: list[str], filename: str = "", chunk_size: int = 2000) -> list[dict[str, object]]:
        """Splits the raw text pages into smaller, indexed chunks."""
        chunks = []
        doc_id_counter = 0
        for i, page_text in enumerate(pages):
            # Split the text by a reasonable separator (e.g., double newline)
            for part in page_text.split('\n\n'):
                # Wrap each part to the desired chunk_size if it's too long
                if part.strip():
                    # textwrap.wrap handles splitting long strings without cutting words mid-sentence as aggressively
                    for chunk_text in textwrap.wrap(part, width=chunk_size, replace_whitespace=False):
                        if chunk_text.strip():
                            # chunks.append(chunk_text.strip())
                            chunks.append({
                                "id": f"doc-{doc_id_counter}",
                                "text": chunk_text.strip(),
                                "metadata": {"page": i + 1, "section": "fdfd", "filename": filename,
                                             "extracted_on": datetime.today().strftime("%m-%d-%Y")}
                            })
                            doc_id_counter += 1
        print(f"Total chunks created: {len(chunks)}")
        return chunks

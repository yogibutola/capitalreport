from pypdf import PdfReader

class PDFReader:
    def read_text_from_pdf(self, pdf_path: str) -> list[str]:
        """Extracts text from the PDF, page by page."""
        print("Extracting text from PDF...")
        reader = PdfReader(pdf_path)
        raw_text = [page.extract_text() for page in reader.pages if page.extract_text()]
        if not raw_text:
            raise ValueError("PDF extraction resulted in no text. Document might be image-based or empty.")

        return raw_text

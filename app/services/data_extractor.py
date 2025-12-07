import pandas as pd
from fastapi import UploadFile
from pypdf import PdfReader


class DataExtractor:
    def __init__(self):
        pass

    def extract_data(self, file: UploadFile) -> list[str]:
        content_type: str = file.content_type
        filename: str = file.filename

        if content_type == "application/pdf":
            reader = PdfReader(file.file)
            return [page.extract_text() for page in reader.pages]
        elif (content_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                               , "application/msword")) or filename.endswith(".docx") or filename.endswith(".doc"):
            import docx
            file.file.seek(0)
            document = docx.Document(file.file)
            return [p.text for p in document.paragraphs if p.text.strip()]
        elif (
                content_type in (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
                "application/vnd.ms-excel"  # .xls
        )
                or filename.endswith(".xlsx") or filename.endswith(".xls")
        ):
            file.file.seek(0)
            df = pd.read_excel(file.file)
            # Convert all rows to strings (each row as a joined line)
            rows = df.astype(str).fillna("").values.tolist()
            # Join each row into a single text line
            cleaned = [" ".join(r).strip() for r in rows if any(r)]
            return cleaned  # list[str]
        elif content_type in ("application/text", "text/plain"):
            text = file.file.read().decode("utf-8")
            return text.splitlines()

        # return extracted_text

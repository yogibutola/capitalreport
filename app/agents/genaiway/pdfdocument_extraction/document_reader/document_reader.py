from app.agents.genaiway.pdfdocument_extraction.document_reader.excel_reader import ExcelReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.pdf_reader import PDFReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.word_reader import WordReader


class DocumentReader:
    def __init__(self, pdf_reader: PDFReader, word_reader: WordReader, excel_reader: ExcelReader):
        self.pdf_reader = pdf_reader
        self.word_reader = word_reader
        self.excel_reader = excel_reader

    def read_data(self, filename: str, content_type: str) -> list[str]:

        # if filenames contains multiple files, the iterate over each file and extract the text.
        extracted_text: list[str] = [""]
        if content_type == "application/pdf":
            extracted_text = self.pdf_reader.read_text_from_pdf(filename)
        elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            extracted_text = self.word_reader.read_text_from_worddoc(filename)
        elif content_type == "application/excel":
            extracted_text = self.excel_reader.read_text_from_excel(filename)
        elif content_type == "application/text":
            extracted_text = self.pdf_reader.read_text_from_pdf(filename)

        return extracted_text

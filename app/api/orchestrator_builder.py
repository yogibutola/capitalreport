# File: main.py

from typing import Optional, List
import shutil
from typing import Annotated
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, Query
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from app.agents.genaiway.pdfdocument_extraction.document_reader.document_reader import DocumentReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.excel_reader import ExcelReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.pdf_reader import PdfReader, PDFReader
from app.agents.genaiway.pdfdocument_extraction.document_reader.word_reader import WordReader
from app.agents.genaiway.pdfdocument_extraction.orchestrator import Orchestrator
from app.agents.genaiway.pdfdocument_extraction.pdf_agent import PdfAgent
from app.agents.genaiway.pdfdocument_extraction.util.embed_data import EmbedData
from app.agents.genaiway.pdfdocument_extraction.util.text_splitter import TextSplitter


class Orchestrator_Builder:
    def get_orchestrator(self) -> Orchestrator:
        """Dependency injector that provides an Orchestrator instance."""
        pdf_agent = PdfAgent()
        pdf_reader = PDFReader()
        word_reader = WordReader()
        excel_reader = ExcelReader()
        document_reader = DocumentReader(pdf_reader, word_reader, excel_reader)

        text_splitter = TextSplitter()
        embed_data = EmbedData()
        return Orchestrator(pdf_agent, document_reader, text_splitter, embed_data)

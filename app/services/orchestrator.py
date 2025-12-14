import logging

from fastapi import UploadFile
from pymongo.synchronous.collection import Collection

from app.agents.vertex.prashn_uttar_agent import PrashnUttarAgent
from app.services.data_extractor import DataExtractor
from app.services.embed_data import EmbedData
from app.services.text_splitter import TextSplitter
from app.store.mongo_db_store import MongoDBStore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class Orchestrator:
    def __init__(self, prashn_uttar_agent: PrashnUttarAgent,
                 data_extractor: DataExtractor,
                 text_splitter: TextSplitter,
                 embed_data: EmbedData,
                 mongodb_store: MongoDBStore):
        self.prashn_uttar_agent = prashn_uttar_agent
        self.data_extractor = data_extractor
        self.text_splitter = text_splitter
        self.embed_data = embed_data
        self.mongodb_store = mongodb_store
        self.logger = logging.getLogger(__name__)

    def store_the_docs(self, file: UploadFile, gcs_url: str):
        self.logger.info("Starting the process of reading, chunking, embedding and storing data.")
        file.file.seek(0)
        filename: str = file.filename
        extracted_text: list[str] = self.data_extractor.extract_data(file)
        chunks: list[dict[str, object]] = self.text_splitter.split_text_into_chunks(extracted_text, filename, gcs_url)
        text_chunks = [chunk["text"] for chunk in chunks]  # extract only text
        metadatas = [chunk["metadata"] for chunk in chunks]
        embeddings = self.embed_data.embed_texts(text_chunks)
        mongodb_store = MongoDBStore()
        self.logger.info("Storing embeddings to vector database")
        mongodb_store.store_pdf_embeddings_to_mongo_db(filename, embeddings, text_chunks, metadatas)

    def prashn_kijiye(self, query: str, document_names: str):
        try:
            if query.lower() == 'quit':
                print("Exiting RAG assistant. Goodbye!")
                return 'quitting'

            if query.lower() == 'clear':
                self.embed_data.clear_index()
                return 'clearing'

            if query.strip():
                documents: list[str] = document_names.split(',')
                documents = list({d.strip() for d in documents})
                collection: Collection = self.mongodb_store.get_collection()
                embedding_model = self.embed_data.get_embedding_model()
                answer = self.prashn_uttar_agent.prashn_kijiye(query, embedding_model, collection, documents)
                self.logger.info("Completed processing user request")
                return answer
        except Exception as e:
            self.logger.error(f"\nAn error occurred during Q&A: {e}")
            self.logger.error("Please check your API key and connection.")

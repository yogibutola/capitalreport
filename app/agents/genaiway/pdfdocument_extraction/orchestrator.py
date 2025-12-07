# from chromadb.types import Collection
from fastapi import UploadFile
from pymongo.synchronous.collection import Collection
from app.agents.genaiway.pdfdocument_extraction.document_reader.document_reader import DocumentReader
from app.agents.genaiway.pdfdocument_extraction.pdf_agent import PdfAgent
from app.agents.genaiway.pdfdocument_extraction.util.embed_data import EmbedData
from app.agents.genaiway.pdfdocument_extraction.util.text_splitter import TextSplitter
from app.services.data_extractor import DataExtractor
from app.store.chroma_db_store import ChromaDBStore
from app.store.mongo_db_store import MongoDBStore


class Orchestrator:
    def __init__(self, pdf_agent: PdfAgent, document_reader: DocumentReader, text_splitter: TextSplitter,
                 embed_data: EmbedData):
        self.pdf_agent = pdf_agent
        self.document_reader = document_reader
        self.text_splitter = text_splitter
        self.embed_data = embed_data

    def start(self, pdf_path: str, pdf_agent: PdfAgent):
        # extracted_text: list[str] = read_text_from_pdf(pdf_path)
        # chunks: list[dict] = split_text_into_chunks(extracted_text)
        # embedding_function.index_document(chunks)
        extracted_text: list[str] = self.pdf_reader.read_text_from_pdf(pdf_path)
        chunks: list[dict] = self.text_splitter.split_text_into_chunks(extracted_text)
        self.embedding_function.index_document(chunks)
        self._interact_with_user(pdf_agent, embedding_function)

    def store_the_document(self, filename: str, content_type: str):
        data_extractor = DataExtractor()
        # extracted_text = self.document_reader.read_data(filename, content_type)
        extracted_text = data_extractor.extract_data(file)
        chunks: list[str] = self.text_splitter.split_text_into_chunks(extracted_text, filename)
        embeddings = self.embed_data.embed_texts(chunks)
        self.embed_data.store_pdf_embeddings(filename, embeddings, chunks)

    def store_the_documents(self, filename: str, content_type: str):
        extracted_text = self.document_reader.read_data(filename, content_type)
        chunks: list[dict[str, object]] = self.text_splitter.split_text_into_chunks(extracted_text, filename)
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        embeddings = self.embed_data.embed_texts(texts)
        # chromadb_store: ChromaDBStore = ChromaDBStore()
        # chromadb_store.store_pdf_embeddings(filename, embeddings, texts, metadatas)
        mongodb_store: MongoDBStore = MongoDBStore()
        mongodb_store.store_pdf_embeddings_to_mongo_db(filename, embeddings, texts, metadatas)

    def store_the_documents_(self, filename: str, content_type: str):
        extracted_text = self.document_reader.read_data(filename, content_type)
        chunks: list[dict[str, object]] = self.text_splitter.split_text_into_chunks(extracted_text, filename)
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        embeddings = self.embed_data.embed_texts(texts)
        # chromadb_store: ChromaDBStore = ChromaDBStore()
        # chromadb_store.store_pdf_embeddings(filename, embeddings, texts, metadatas)
        mongodb_store: MongoDBStore = MongoDBStore()
        mongodb_store.store_pdf_embeddings_to_mongo_db(filename, embeddings, texts, metadatas)

    def store_the_docs(self, file: UploadFile, gcs_url: str):
        file.file.seek(0)
        filename: str = file.filename
        data_extractor = DataExtractor()
        extracted_text: list[str] = data_extractor.extract_data(file)
        chunks: list[dict[str, object]] = self.text_splitter.split_text_into_chunks(extracted_text, filename, gcs_url)
        text_chunks = [chunk["text"] for chunk in chunks]  # extract only text
        metadatas = [chunk["metadata"] for chunk in chunks]
        embeddings = self.embed_data.embed_texts(text_chunks)
        mongodb_store = MongoDBStore()
        mongodb_store.store_pdf_embeddings_to_mongo_db(filename, embeddings, text_chunks, metadatas)


    def ask_question(self, query: str, document_name: str):
        try:
            if query.lower() == 'quit':
                print("Exiting RAG assistant. Goodbye!")
                return 'quitting'

            if query.lower() == 'clear':
                self.embed_data.clear_index()
                return 'clearing'

            if query.strip():
                collection: Collection = self.embed_data.get_collection(document_name)
                embedding_model = self.embed_data.get_embedding_model()
                answer = self.pdf_agent.ask_question(query, embedding_model, collection)
                print(f"\n🤖 **Assistant Answer:**\n{'-' * 50}")
                print(answer)
                print(f"{'-' * 50}")
                return answer
        except Exception as e:
            print(f"\nAn error occurred during Q&A: {e}")
            print("Please check your API key and connection.")

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

                mongodb_store = MongoDBStore()
                collection: Collection = mongodb_store.get_collection()
                embedding_model = self.embed_data.get_embedding_model()
                answer = self.pdf_agent.prashn_kijiye(query, embedding_model, collection, documents)
                print(f"\n🤖 **Assistant Answer:**\n{'-' * 50}")
                print(answer)
                print(f"{'-' * 50}")
                return answer
        except Exception as e:
            print(f"\nAn error occurred during Q&A: {e}")
            print("Please check your API key and connection.")

    def user_input(self, query: str):
        document_name = "doc_name"
        # embedding_function = EmbeddData(pdf_path, document_name)
        collection = self.embed_data.get_collection(document_name)
        answer = self.pdf_agent.get_answer_for_ui_client(collection, query)
        return answer

    def _interact_with_user(self, pdf_agent: PdfAgent, embedding_function: EmbedData):
        while True:
            try:
                user_question = input("\nYour question (type 'quit' or 'clear' to exit/reset): ")
                if user_question.lower() == 'quit':
                    print("Exiting RAG assistant. Goodbye!")
                    break

                if user_question.lower() == 'clear':
                    embedding_function.clear_index()
                    continue

                if user_question.strip():
                    # Get the answer from the document
                    answer = pdf_agent.get_answer(embedding_function, user_question)

                    print(f"\n🤖 **Assistant Answer:**\n{'-' * 50}")
                    print(answer)
                    print(f"{'-' * 50}")
            except Exception as e:
                print(f"\nAn error occurred during Q&A: {e}")
                print("Please check your API key and connection.")
                break

        # query = """
        #                 Read the document and list the holdings with the following information:
        #                   Schema = list of objects with fields:
        #                     - stock_name (string)
        #                     - quantity (number)
        #                     - gain_loss (number, float, in USD — no $, no commas, 0 if not applicable))
        #                 """
        # my_investments = pdf_agent.get_answer(embedding_function, query)
        # print(my_investments)


if __name__ == "__main__":
    # Example usage
    pdf_path = "Statement8312025.pdf"  # replace with your PDF file path
    output_path = "../document_understanding/output.txt"  # optional output file
    orchestrator = Orchestrator()

    embedding_function = EmbedData(pdf_path)
    pdf_agent = PdfAgent()
    text = orchestrator.start(pdf_path, pdf_agent, embedding_function)
    print("PDF extraction completed.")

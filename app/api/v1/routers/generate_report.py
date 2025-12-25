from fastapi import status, Query, APIRouter

from app.agents.vertex.prashn_uttar_agent import PrashnUttarAgent
from app.services.data_extractor import DataExtractor
from app.services.embed_data import EmbedData
from app.services.orchestrator import Orchestrator
from app.services.text_splitter import TextSplitter
from app.store.mongo_db_store import MongoDBStore

router = APIRouter(tags=["Generate Report"])


def get_orchestrator() -> Orchestrator:
    """Dependency injector that provides an Orchestrator instance."""
    prashn_uttar_agent = PrashnUttarAgent()
    data_extractor = DataExtractor()
    text_splitter = TextSplitter()
    embed_data = EmbedData()
    mongodb_store = MongoDBStore()
    return Orchestrator(prashn_uttar_agent, data_extractor, text_splitter, embed_data, mongodb_store)



@router.api_route("/generate_report/", methods=["GET", "OPTIONS"], status_code=status.HTTP_200_OK)
def query_document(query: str = Query("Describe the document",  # Default value if no query parameter is provided
                                      title="Name to Greet",
                                      description="The name to include in the greeting response.")):
    
    orchestrator = get_orchestrator()
    response: str = orchestrator.generate_report(query)
    return {"answer": f"AEGIS: {response}"}

from pydantic import BaseModel


class Investment(BaseModel):
    stock_name: str
    quantity: float
    gain_loss: float

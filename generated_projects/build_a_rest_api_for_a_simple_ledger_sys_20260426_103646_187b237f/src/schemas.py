from pydantic import BaseModel
from typing import List

class LedgerEntryModel(BaseModel):
    id: int
    user_id: int
    category_id: int
    amount: float
    description: str

    class Config:
        orm_mode = True

class CategoryModel(BaseModel):
    id: int
    name: str
    description: str

    class Config:
        orm_mode = True
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, Float, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel
from typing import List

# Initialize FastAPI app
app = FastAPI()

# Initialize OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize database engine
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    password = Column(String)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    amount = Column(Float)
    description = Column(String)
    user = relationship("User", backref="ledger_entries")
    category = relationship("Category", backref="ledger_entries")

# Create database tables
Base.metadata.create_all(bind=engine)

# Define Pydantic models
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

# Define API endpoints
@app.post("/api/v1/ledger")
async def create_ledger_entry(ledger_entry: LedgerEntryModel):
    db = SessionLocal()
    new_ledger_entry = LedgerEntry(user_id=ledger_entry.user_id, category_id=ledger_entry.category_id, amount=ledger_entry.amount, description=ledger_entry.description)
    db.add(new_ledger_entry)
    db.commit()
    db.refresh(new_ledger_entry)
    return new_ledger_entry

@app.get("/api/v1/ledger")
async def get_all_ledger_entries():
    db = SessionLocal()
    ledger_entries = db.query(LedgerEntry).all()
    return ledger_entries

@app.get("/api/v1/ledger/{ledger_entry_id}")
async def get_ledger_entry(ledger_entry_id: int):
    db = SessionLocal()
    ledger_entry = db.query(LedgerEntry).filter(LedgerEntry.id == ledger_entry_id).first()
    if ledger_entry is None:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    return ledger_entry

@app.put("/api/v1/ledger/{ledger_entry_id}")
async def update_ledger_entry(ledger_entry_id: int, ledger_entry: LedgerEntryModel):
    db = SessionLocal()
    existing_ledger_entry = db.query(LedgerEntry).filter(LedgerEntry.id == ledger_entry_id).first()
    if existing_ledger_entry is None:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    existing_ledger_entry.user_id = ledger_entry.user_id
    existing_ledger_entry.category_id = ledger_entry.category_id
    existing_ledger_entry.amount = ledger_entry.amount
    existing_ledger_entry.description = ledger_entry.description
    db.commit()
    db.refresh(existing_ledger_entry)
    return existing_ledger_entry

@app.delete("/api/v1/ledger/{ledger_entry_id}")
async def delete_ledger_entry(ledger_entry_id: int):
    db = SessionLocal()
    ledger_entry = db.query(LedgerEntry).filter(LedgerEntry.id == ledger_entry_id).first()
    if ledger_entry is None:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    db.delete(ledger_entry)
    db.commit()
    return {"message": "Ledger entry deleted successfully"}
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from pydantic import BaseModel
from jose import jwt, JWTError
from typing import Optional
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.exceptions import HTTPException
from fastapi import status

# Define the database connection
SQLALCHEMY_DATABASE_URL = "sqlite:///./ledger.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define the models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    ledger_entries = relationship("LedgerEntry", back_populates="user")

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    description = Column(String)
    amount = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="ledger_entries")

# Create the database tables
# moved to startup

# Define the Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str

class LedgerEntryCreate(BaseModel):
    description: str
    amount: float

class LedgerEntry(BaseModel):
    id: int
    user_id: int
    description: str
    amount: float
    created_at: datetime

    class Config:
        orm_mode = True

# Define the FastAPI app
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)

# Define the OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")

# Include the routers
from src.routes.users import router as users_router
from src.routes.login import router as login_router
from src.routes.ledger_entries import router as ledger_entries_router
app.include_router(users_router)
app.include_router(login_router)
app.include_router(ledger_entries_router)

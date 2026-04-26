from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.main import SessionLocal, LedgerEntry, LedgerEntryCreate, User
from src.main import oauth2_scheme

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define the routes
@router.post("/api/v1/ledger-entries", status_code=status.HTTP_201_CREATED)
def create_ledger_entry(ledger_entry: LedgerEntryCreate, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Verify the token
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    new_ledger_entry = LedgerEntry(user_id=user.id, description=ledger_entry.description, amount=ledger_entry.amount)
    db.add(new_ledger_entry)
    db.commit()
    db.refresh(new_ledger_entry)
    return new_ledger_entry

@router.get("/api/v1/ledger-entries", status_code=status.HTTP_200_OK)
def get_ledger_entries(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Verify the token
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    ledger_entries = db.query(LedgerEntry).filter(LedgerEntry.user_id == user.id).all()
    return ledger_entries

@router.get("/api/v1/ledger-entries/{id}", status_code=status.HTTP_200_OK)
def get_ledger_entry(id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Verify the token
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    ledger_entry = db.query(LedgerEntry).filter(LedgerEntry.id == id).filter(LedgerEntry.user_id == user.id).first()
    if not ledger_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found")
    return ledger_entry

@router.put("/api/v1/ledger-entries/{id}", status_code=status.HTTP_200_OK)
def update_ledger_entry(id: int, ledger_entry: LedgerEntryCreate, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Verify the token
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    db_ledger_entry = db.query(LedgerEntry).filter(LedgerEntry.id == id).filter(LedgerEntry.user_id == user.id).first()
    if not db_ledger_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found")
    db_ledger_entry.description = ledger_entry.description
    db_ledger_entry.amount = ledger_entry.amount
    db.commit()
    db.refresh(db_ledger_entry)
    return db_ledger_entry

@router.delete("/api/v1/ledger-entries/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ledger_entry(id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    # Verify the token
    user = db.query(User).filter(User.username == token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    ledger_entry = db.query(LedgerEntry).filter(LedgerEntry.id == id).filter(LedgerEntry.user_id == user.id).first()
    if not ledger_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found")
    db.delete(ledger_entry)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT)

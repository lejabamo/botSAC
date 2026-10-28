from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import engine, get_db

# Create tables in the DB (usually done by alembic or the DBA for Oracle, but keeping for dev)
if engine:
    models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BotSAC API Enterprise")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "BotSAC Enterprise API corriendo"}

@app.get("/api/radicados", response_model=List[schemas.RadicadoResponse])
def get_radicados(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    radicados = db.query(models.Radicado).offset(skip).limit(limit).all()
    return radicados

@app.post("/api/radicados/bulk", response_model=dict)
def create_radicados_bulk(radicados: List[schemas.RadicadoCreate], db: Session = Depends(get_db)):
    # Block load optimization for Oracle
    new_radicados = []
    # Check existing to avoid integrity errors
    existing_ids = {r[0] for r in db.query(models.Radicado.id_radicado).all()}
    
    for r in radicados:
        if r.id_radicado not in existing_ids:
            new_radicados.append(models.Radicado(**r.model_dump()))
            existing_ids.add(r.id_radicado)
            
    if new_radicados:
        db.add_all(new_radicados)
        db.commit()
    
    return {"status": "ok", "inserted": len(new_radicados), "skipped": len(radicados) - len(new_radicados)}

@app.post("/api/radicados", response_model=schemas.RadicadoResponse)
def create_radicado(radicado: schemas.RadicadoCreate, db: Session = Depends(get_db)):
    db_radicado = db.query(models.Radicado).filter(models.Radicado.id_radicado == radicado.id_radicado).first()
    if db_radicado:
        raise HTTPException(status_code=400, detail="Radicado ya existe")
    
    new_radicado = models.Radicado(**radicado.model_dump())
    db.add(new_radicado)
    db.commit()
    db.refresh(new_radicado)
    return new_radicado

@app.get("/api/radicados/{id_radicado}", response_model=schemas.RadicadoResponse)
def get_radicado(id_radicado: str, db: Session = Depends(get_db)):
    db_radicado = db.query(models.Radicado).filter(models.Radicado.id_radicado == id_radicado).first()
    if not db_radicado:
        raise HTTPException(status_code=404, detail="Radicado no encontrado")
    return db_radicado

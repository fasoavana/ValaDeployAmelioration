#app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


""" 
Regroupe tout ce qui est persistance de données (base de données, cache, etc.) dans un seul module.
"""

# creer le moteur une seule fois
engine = create_engine(settings.url)


# ce n'est pas la session, objet qui sert a creer une session (un modele)
Session_local = sessionmaker(bind=engine)

def get_db():
    db = Session_local()
    try:
        yield db
    finally:
        db.close()
        
class Base(DeclarativeBase):
    pass
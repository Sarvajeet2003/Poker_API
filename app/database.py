from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Create SQLite database engine
DATABASE_URL = "sqlite:///./poker_game.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class DBGame(Base):
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    is_active = Column(Boolean, default=True)
    pot = Column(Float, default=0.0)
    current_turn_index = Column(Integer, default=0)
    current_turn_order = Column(JSON, default=list)
    current_stage = Column(String, default="pre_flop")
    current_bet = Column(Float, default=0.0)
    community_cards = Column(JSON, default=list)
    
    players = relationship("DBPlayer", back_populates="game")

class DBPlayer(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    name = Column(String, index=True)
    balance = Column(Float, default=1000.0)
    is_active = Column(Boolean, default=True)
    current_bet = Column(Float, default=0.0)
    is_all_in = Column(Boolean, default=False)
    has_acted = Column(Boolean, default=False)
    cards = Column(JSON, default=list)
    
    game = relationship("DBGame", back_populates="players")

# Create tables
Base.metadata.create_all(bind=engine)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
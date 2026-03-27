from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import os

# Determine if running in test environment
TESTING = os.environ.get("TESTING") == "True"

DATABASE_URL = "sqlite:///./test.db" if TESTING else "sqlite:///./sql_app.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String) # e.g., "teacher", "admin", "student", "guardian"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    phone = Column(String, nullable=True)
    specialization = Column(String, nullable=True)
    profile_image = Column(Text, nullable=True) # Base64 encoded image or URL
    public_id = Column(String, unique=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    role_label = Column(String, nullable=True) # A more descriptive label for the role

    sessions_started = relationship("ChatSession", foreign_keys="[ChatSession.starter_id]", back_populates="starter")
    sessions_joined = relationship("ChatSession", foreign_keys="[ChatSession.joiner_id]", back_populates="joiner")
    sent_messages = relationship("Message", foreign_keys="[Message.sender_id]", back_populates="sender")
    read_receipts = relationship("ReadReceipt", back_populates="user")
    
    # Existing relationships omitted for brevity
    # /* Lines 31-35 omitted */

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    starter_id = Column(Integer, ForeignKey("users.id"))
    joiner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_muted_by_starter = Column(Boolean, default=False)
    is_muted_by_joiner = Column(Boolean, default=False)

    starter = relationship("User", foreign_keys=[starter_id], back_populates="sessions_started")
    joiner = relationship("User", foreign_keys=[joiner_id], back_populates="sessions_joined")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    read_receipts = relationship("ReadReceipt", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)

    session = relationship("ChatSession", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")
    read_receipts = relationship("ReadReceipt", back_populates="message", cascade="all, delete-orphan")

class ReadReceipt(Base):
    __tablename__ = "read_receipts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message_id = Column(Integer, ForeignKey("messages.id"))
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    read_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="read_receipts")
    message = relationship("Message", back_populates="read_receipts")
    session = relationship("ChatSession", back_populates="read_receipts")

# Existing models omitted for brevity
# /* Lines 85-89 omitted */

# Function to create all tables
def create_all_tables():
    Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#app/models/user.py

from enum import Enum 
from app.db.database import Base
from sqlalchemy.orm import  Mapped, mapped_column
from sqlalchemy import String,Boolean, ForeignKey, Enum as SQLEnum, text, DateTime, func
from datetime import datetime


class UserRole(str, Enum):
    ADMIN = "admin"
    DEV = "dev" 
    
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole, 
            name='user_role',
            values_callable= lambda enum_cls: [e.value for e in enum_cls]), 
        nullable=False, 
        server_default=text("'dev'"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    revoked: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
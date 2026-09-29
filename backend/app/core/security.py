#app/core/security.py
import binascii

from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings
from pwdlib import PasswordHash
import jwt
import secrets
import hashlib
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from fastapi import Depends, HTTPException, status
from app.db.database import get_db


""" 
Chiffrement des variables sensibles de l'application
"""

key = settings.ENCRYPTION_KEY.encode()  # Convert the key to bytes
my_fernet = Fernet(key)

def encrypt_data(data: str) -> str:
    encrypted_data = my_fernet.encrypt(data.encode())
    return encrypted_data.decode()  # Convert bytes back to string

def decrypt_data(encrypted_data: str) -> str:
    """
    Déchiffre une donnée. 
    Si la donnée n'est pas chiffrée (ou est corrompue), la retourne telle quelle (fallback en clair).
    """
    if not encrypted_data:
        return ""
    
    try:
        # Tentative de déchiffrement normal
        decrypted_bytes = my_fernet.decrypt(encrypted_data.encode())
        return decrypted_bytes.decode()
    
    except (InvalidToken, binascii.Error, Exception):
        # FALLBACK : Si ça échoue, c'est très probablement que la valeur 
        # est déjà en texte clair (ex: une URL, un port, ou une variable non marquée comme secrète).
        # On la retourne donc sans la modifier pour éviter de faire planter le déploiement.
        return encrypted_data

""" 
    Hash de password pour authentification
"""

# instancer de 'hasher' avec une config recommandee
password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)

# ============================================
""" 
Persitance des connexions
"""
def create_access_token(user_id: int, role: str) -> str:
    # utc pour different fuseau horaire
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id), # subject
        "role": role,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY, # verifie la signature
            algorithms=[settings.JWT_ALGORITHM],
        )

        return payload

    except InvalidTokenError:
        raise ValueError("Invalid token")

# ===========================================
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), # scheme + credential
    db: Session = Depends(get_db),
) -> User:

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user 

""" 
Refresh token : pas besoin de signature car depend de la db
"""

def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )


# =================================================
""" 
Dependance pour les authorizations selon le role
"""

def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user
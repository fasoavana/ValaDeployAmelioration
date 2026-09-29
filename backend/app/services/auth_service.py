from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models.user import User, RefreshToken
from app.schemas.auth import UserRegisterSchema, LoginSchema
from app.core.security import hash_password, verify_password
from app.core.security import create_access_token,refresh_token_expiry, hash_refresh_token, create_refresh_token


def register_user(user: UserRegisterSchema, db: Session) -> User:
    existing_user = (
        db.query(User) # table correspondant aux models users
        .filter(User.email == user.email)
        .first() # retourner le premier resultat 
    )
    
    if existing_user:
        raise ValueError("Email already registered")
    
    hashed_password = hash_password(user.password)
    
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        password_hash=hashed_password,
    )
    
    try:
     db.add(new_user) # preparation pour insertion
     db.commit() #
     db.refresh(new_user) # charge les valeurs par defaut de postgres
    except Exception:
        db.rollback()
        raise # relance l'exception capture
    
    return new_user 

def login_user(user: LoginSchema, db: Session):

    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    if not existing_user:
        raise ValueError("Incorrect credentials")

    is_verify = verify_password(
        user.password,
        existing_user.password_hash
    )

    if not is_verify:
        raise ValueError("Incorrect credentials")

    if not existing_user.is_active:
        raise ValueError("Your account is inactive")
    
    access_token = create_access_token(
        user_id=existing_user.id,
        role=existing_user.role.value, # c'est un enum
    )
    raw_refresh_token = create_refresh_token()
    
    db_refresh = RefreshToken(
        user_id=existing_user.id,
        token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=refresh_token_expiry(),
    )
    
    db.add(db_refresh) # stocker le refresh token
    db.commit()


    return access_token, raw_refresh_token


def refresh_access_token(raw_token: str | None, db: Session):
    """
    Reçoit le refresh_token brut (venant du cookie).
    Vérifie qu'il est valide en DB, le révoque (rotation),
    puis génère un nouvel access_token + un nouveau refresh_token.
    """

    # étape 1 : le cookie doit exister
    if not raw_token:
        raise ValueError("No refresh token")

    # étape 2 : on hash le token reçu pour le comparer à ce qui est en DB
    # (on ne stocke jamais le token en clair, donc on compare des hash)
    token_hash = hash_refresh_token(raw_token)

    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    # étape 3 : le token doit exister, ne pas être révoqué, ne pas être expiré
    if (
        not db_token
        or db_token.revoked
        or db_token.expires_at < datetime.now(timezone.utc)
    ):
        raise ValueError("Invalid refresh token")

    # étape 4 : ROTATION -> ce token est "consommé", il ne pourra plus jamais resservir
    # (protection : si quelqu'un le vole et le rejoue plus tard, il sera déjà révoqué)
    db_token.revoked = True
    db.commit()

    # étape 5 : on récupère le user lié à ce refresh_token
    user = db.query(User).filter(User.id == db_token.user_id).first()

    if not user or not user.is_active:
        raise ValueError("Invalid refresh token")

    # étape 6 : on génère un NOUVEL access_token (le vrai but de cette fonction)
    new_access_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
    )

    # étape 7 : on génère aussi un NOUVEAU refresh_token (rotation)
    new_raw_refresh_token = create_refresh_token()

    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_raw_refresh_token),
        expires_at=refresh_token_expiry(),
    ))
    db.commit()

    # on retourne les deux nouveaux tokens à la route
    return new_access_token, new_raw_refresh_token

def logout_user(raw_token: str | None, db: Session) -> None:
    """
    Révoque le refresh_token en DB pour empêcher tout renouvellement futur.
    Ne fait rien de spécial si pas de cookie (logout silencieux).
    """

    # si pas de cookie, rien à révoquer, on ne fait pas d'erreur
    if not raw_token:
        return

    token_hash = hash_refresh_token(raw_token)

    # on marque juste revoked = True, pas besoin de le supprimer physiquement
    db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).update({"revoked": True})

    db.commit()
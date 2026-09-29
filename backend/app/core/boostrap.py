import logging
import secrets
from sqlalchemy.orm import Session

from app.db.database import Session_local
from app.models.user import User, UserRole
from app.core.security import hash_password

def bootstrap_initial_admin():
    """
    Crée un compte admin par défaut si la base de données est vide.
    Affiche le mot de passe temporaire une seule fois dans les logs.
    """
    db: Session = Session_local()
    try:
        # Vérifie si un admin existe déjà
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first()
        
        if not admin_exists:
            temp_password = secrets.token_urlsafe(16) # 16 caractères aléatoires sécurisés
            hashed = hash_password(temp_password)
            
            new_admin = User(
                full_name="Administrateur Initial",
                email="admin@valadeploy.io",
                password_hash=hashed,
                role=UserRole.ADMIN,
                is_active=True,
                must_change_password=True # Force le changement au premier login
            )
            db.add(new_admin)
            db.commit()
            
            # Affichage sécurisé dans les logs Docker (visible une seule fois au premier démarrage)
            logging.warning("=" * 70)
            logging.warning(" PREMIER DÉMARRAGE DÉTECTÉ : COMPTE ADMIN CRÉÉ")
            logging.warning(" Email    : admin@valadeploy.io")
            logging.warning(f" Password : {temp_password}")
            logging.warning("  Connectez-vous et changez ce mot de passe immédiatement !")
            logging.warning("=" * 70)
            
    except Exception as e:
        logging.error(f"Erreur lors du bootstrap de l'admin initial : {e}")
        db.rollback()
    finally:
        db.close()
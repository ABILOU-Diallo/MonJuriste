from django.core.mail import send_mail
from django.conf import settings
from .models import Notification, EmailCommunication
import logging

logger = logging.getLogger(__name__)

def create_notification(user, message):
    """
    Crée une notification en base de données pour un utilisateur spécifique.
    """
    try:
        notification = Notification.objects.create(user=user, message=message)
        logger.info(f"Notification créée pour {user.username}: {message[:30]}...")
        return notification
    except Exception as e:
        logger.error(f"Erreur lors de la création de la notification : {str(e)}")
        return None


def send_automatic_email(user, subject, content):
    """
    Simule l'envoi d'un email automatique :
    1. Enregistre la communication en base de données pour que l'utilisateur puisse la lire dans l'application.
    2. Envoie l'email via le service de messagerie Django (affiché en console pour le test).
    """
    try:
        # 1. Enregistrement en base de données
        EmailCommunication.objects.create(
            user=user,
            sujet=subject,
            contenu=content,
            destinataire=user.email or f"{user.username}@monjuriste.local"
        )

        # 2. Envoi réel (backend console configuré dans settings.py)
        send_mail(
            subject=f"[MonJuriste] {subject}",
            message=content,
            from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@monjuriste.com',
            recipient_list=[user.email or 'test@monjuriste.local'],
            fail_silently=True
        )
        logger.info(f"Email envoyé à {user.email or user.username} : {subject}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email : {str(e)}")
        return False

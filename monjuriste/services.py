import random
import string
import logging

logger = logging.getLogger(__name__)

class PaymentServiceException(Exception):
    pass

class BaseMobileMoneyService:
    def __init__(self, provider_name):
        self.provider_name = provider_name

    def generate_transaction_id(self):
        prefix = "OM" if self.provider_name == "Orange Money" else "MTN"
        random_digits = ''.join(random.choices(string.digits, k=8))
        random_chars = ''.join(random.choices(string.ascii_uppercase, k=4))
        return f"TXN-{prefix}-{random_digits}{random_chars}"

    def initiate_payment(self, phone_number, amount, reference):
        """
        Simule l'initialisation du paiement Mobile Money.
        Retourne un dictionnaire contenant le statut initial, l'ID de transaction et une URL de redirection (simulée).
        """
        logger.info(f"Initiating {self.provider_name} payment of {amount} FCFA for phone {phone_number} (Ref: {reference})")
        
        # Validation basique du numéro de téléphone
        if not phone_number or len(phone_number) < 9:
            raise PaymentServiceException(f"Numéro de téléphone invalide pour le paiement {self.provider_name}.")
            
        # Générer un ID de transaction factice
        transaction_id = self.generate_transaction_id()
        
        # Simulation d'un appel API. Dans un environnement de production, nous ferions une requête HTTP POST
        # vers l'API Orange Money (OM Web Payment / Orange Developer) ou MTN MoMo API.
        
        # On retourne un dictionnaire de résultat simulé
        return {
            'status': 'PENDING',
            'transaction_id': transaction_id,
            'provider': self.provider_name,
            'amount': amount,
            'phone_number': phone_number,
            'redirect_url': f"/client/paiement/process/{transaction_id}/" # Notre page de simulation locale
        }

    def verify_payment(self, transaction_id):
        """
        Vérifie le statut d'une transaction.
        Simule une vérification en retournant de manière déterministe un statut (ex. réussi si ID correct).
        """
        logger.info(f"Verifying {self.provider_name} transaction {transaction_id}")
        
        # Pour notre prototype, on considère que la transaction est réussie à 90%
        # ou on laisse l'utilisateur choisir l'état sur la page de traitement simulé.
        success = random.random() < 0.95
        return {
            'transaction_id': transaction_id,
            'status': 'SUCCESS' if success else 'FAILED',
            'message': 'Transaction traitée avec succès' if success else 'Provision insuffisante ou expiration de session.'
        }


class OrangeMoneyService(BaseMobileMoneyService):
    def __init__(self):
        super().__init__("Orange Money")

    def initiate_om_web_payment(self, phone_number, amount, reference):
        """
        Simulation spécifique pour Orange Money (Web Payment API)
        """
        # Spécifique OM : Nécessite des tokens d'autorisation Orange Developer
        return self.initiate_payment(phone_number, amount, reference)


class MTNMoneyService(BaseMobileMoneyService):
    def __init__(self):
        super().__init__("MTN Mobile Money")

    def initiate_momo_payment(self, phone_number, amount, reference):
        """
        Simulation spécifique pour MTN MoMo API (Collection Product)
        """
        # Spécifique MTN : Nécessite une clé API souscription et l'enregistrement de l'UUID
        return self.initiate_payment(phone_number, amount, reference)

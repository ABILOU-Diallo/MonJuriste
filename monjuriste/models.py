from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Avg
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('CLIENT', 'Client'),
        ('AVOCAT', 'Avocat'),
        ('ADMIN', 'Administrateur'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT')
    telephone = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def is_client(self):
        return self.role == 'CLIENT' or hasattr(self, 'client_profile')

    def is_avocat(self):
        return self.role == 'AVOCAT' or hasattr(self, 'avocat_profile')

    def is_admin(self):
        return self.role == 'ADMIN' or self.is_superuser


class Specialite(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Spécialité"
        verbose_name_plural = "Spécialités"

    def __str__(self):
        return self.nom


class ClientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    adresse = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Profil Client"
        verbose_name_plural = "Profils Clients"

    def __str__(self):
        return f"Client: {self.user.get_full_name() or self.user.username}"


class AvocatProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='avocat_profile')
    specialites = models.ManyToManyField(Specialite, related_name='avocats', blank=True)
    tarif_horaire = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    description = models.TextField(blank=True)
    cabinet = models.CharField(max_length=200, blank=True, verbose_name="Cabinet / Étude")
    ville = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    annees_experience = models.PositiveIntegerField(default=0, verbose_name="Années d'expérience")
    is_approved = models.BooleanField(default=False, verbose_name="Approuvé par l'admin")

    class Meta:
        verbose_name = "Profil Avocat"
        verbose_name_plural = "Profils Avocats"

    def __str__(self):
        status = "Approuvé" if self.is_approved else "En attente d'approbation"
        return f"Avocat: {self.user.get_full_name() or self.user.username} ({status})"

    @property
    def note_moyenne(self):
        avg_rating = self.notes.aggregate(Avg('note'))['note__avg']
        return round(avg_rating, 1) if avg_rating else 0.0

    @property
    def total_avis(self):
        return self.notes.count()


class CreneauHoraire(models.Model):
    JOURS_SEMAINE = (
        (0, 'Lundi'),
        (1, 'Mardi'),
        (2, 'Mercredi'),
        (3, 'Jeudi'),
        (4, 'Vendredi'),
        (5, 'Samedi'),
        (6, 'Dimanche'),
    )
    avocat = models.ForeignKey(AvocatProfile, on_delete=models.CASCADE, related_name='creneaux')
    jour_semaine = models.IntegerField(choices=JOURS_SEMAINE)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    class Meta:
        verbose_name = "Créneau Horaire"
        verbose_name_plural = "Créneaux Horaires"
        ordering = ['jour_semaine', 'heure_debut']

    def __str__(self):
        return f"{self.get_jour_semaine_display()} de {self.heure_debut.strftime('%H:%M')} à {self.heure_fin.strftime('%H:%M')}"


class Conge(models.Model):
    avocat = models.ForeignKey(AvocatProfile, on_delete=models.CASCADE, related_name='conges')
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Congé / Absence"
        verbose_name_plural = "Congés / Absences"
        ordering = ['date_debut']

    def __str__(self):
        return f"Congé de {self.avocat.user.last_name} du {self.date_debut} au {self.date_fin}"


class DemandeConsultation(models.Model):
    STATUT_CHOICES = (
        ('EN_ATTENTE', 'En attente de paiement'),
        ('PAYEE', 'Payée (En attente d\'acceptation)'),
        ('ACCEPTEE', 'Acceptée (Dossier créé)'),
        ('REJETEE', 'Rejetée'),
        ('TERMINEE', 'Terminée'),
    )
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='demandes')
    avocat = models.ForeignKey(AvocatProfile, on_delete=models.CASCADE, related_name='demandes')
    sujet = models.CharField(max_length=200)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de Consultation"
        verbose_name_plural = "Demandes de Consultations"
        ordering = ['-created_at']

    def __str__(self):
        return f"Demande #{self.id} - {self.sujet} - Client: {self.client.user.last_name}"


class RendezVous(models.Model):
    STATUT_CHOICES = (
        ('EN_ATTENTE', 'En attente'),
        ('ACCEPTE', 'Accepté'),
        ('REJETE', 'Rejeté'),
        ('ANNULE', 'Annulé'),
        ('TERMINE', 'Terminé'),
    )
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='rendezvous')
    avocat = models.ForeignKey(AvocatProfile, on_delete=models.CASCADE, related_name='rendezvous')
    demande = models.ForeignKey(DemandeConsultation, on_delete=models.SET_NULL, null=True, blank=True, related_name='rendezvous')
    date_heure = models.DateTimeField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    motif = models.TextField(blank=True, help_text="Détails additionnels pour la rencontre")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rendez-vous"
        verbose_name_plural = "Rendez-vous"
        ordering = ['date_heure']

    def __str__(self):
        return f"RDV #{self.id} le {self.date_heure.strftime('%d/%m/%Y à %H:%M')} avec l'avocat {self.avocat.user.last_name}"


class Dossier(models.Model):
    STATUT_CHOICES = (
        ('EN_ATTENTE', 'En attente'),
        ('ACCEPTE', 'En cours'),
        ('REJETE', 'Rejeté'),
        ('TERMINE', 'Terminé'),
    )
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='dossiers')
    avocat = models.ForeignKey(AvocatProfile, on_delete=models.CASCADE, related_name='dossiers')
    demande = models.OneToOneField(DemandeConsultation, on_delete=models.SET_NULL, null=True, blank=True, related_name='dossier')
    titre = models.CharField(max_length=200)
    description = models.TextField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier"
        verbose_name_plural = "Dossiers"
        ordering = ['-created_at']

    def __str__(self):
        return f"Dossier: {self.titre} (Client: {self.client.user.username})"


class DocumentDossier(models.Model):
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='documents')
    fichier = models.FileField(upload_to='dossiers/')
    titre = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Document du Dossier"
        verbose_name_plural = "Documents du Dossier"
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.titre} - Importé le {self.uploaded_at.strftime('%d/%m/%Y')}"


class Paiement(models.Model):
    MOYEN_CHOICES = (
        ('ORANGE_MONEY', 'Orange Money'),
        ('MTN_MONEY', 'MTN Mobile Money'),
    )
    STATUT_CHOICES = (
        ('EN_ATTENTE', 'En attente'),
        ('REUSSI', 'Réussi'),
        ('ECHOUE', 'Échoué'),
    )
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='paiements')
    demande = models.ForeignKey(DemandeConsultation, on_delete=models.CASCADE, related_name='paiements')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    moyen_paiement = models.CharField(max_length=20, choices=MOYEN_CHOICES)
    transaction_id = models.CharField(max_length=100, unique=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-created_at']

    def __str__(self):
        return f"Paiement #{self.id} ({self.montant} FCFA) - {self.get_statut_display()}"


class Note(models.Model):
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='notes')
    avocat = models.ForeignKey(AvocatProfile, on_delete=models.CASCADE, related_name='notes')
    note = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    commentaire = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Avis / Note"
        verbose_name_plural = "Avis / Notes"
        unique_together = ('client', 'avocat')
        ordering = ['-created_at']

    def __str__(self):
        return f"Note {self.note}/5 par {self.client.user.username} pour l'avocat {self.avocat.user.username}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    lu = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification pour {self.user.username} - {'Lu' if self.lu else 'Non lu'}"


class EmailCommunication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='communications')
    sujet = models.CharField(max_length=255)
    contenu = models.TextField()
    destinataire = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Communication Email"
        verbose_name_plural = "Communications Emails"
        ordering = ['-sent_at']

    def __str__(self):
        return f"Email: '{self.sujet}' à {self.destinataire}"


# SIGNALS for automatic profile creation
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'CLIENT':
            ClientProfile.objects.create(user=instance)
        elif instance.role == 'AVOCAT':
            AvocatProfile.objects.create(user=instance)
        elif instance.role == 'ADMIN' or instance.is_superuser:
            # Let's create an admin profile if we want, or just let them manage things.
            pass

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if instance.role == 'CLIENT':
        if not hasattr(instance, 'client_profile'):
            ClientProfile.objects.create(user=instance)
        else:
            instance.client_profile.save()
    elif instance.role == 'AVOCAT':
        if not hasattr(instance, 'avocat_profile'):
            AvocatProfile.objects.create(user=instance)
        else:
            instance.avocat_profile.save()


# ==========================================
# MESSAGING MODELS
# ==========================================

class Conversation(models.Model):
    """Modèle pour les conversations entre client et avocat"""
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='conversations')
    avocat = models.ForeignKey(AvocatProfile, on_delete=models.CASCADE, related_name='conversations')
    dossier = models.ForeignKey(Dossier, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        unique_together = ('client', 'avocat')
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Conversation entre {self.client.user.get_full_name()} et {self.avocat.user.get_full_name()}"
    
    def get_latest_message(self):
        """Retourne le dernier message de la conversation"""
        return self.messages.first()


class ConversationCall(models.Model):
    """Modèle pour les demandes d'appel audio/vidéo"""
    TYPE_CHOICES = (
        ('AUDIO', 'Audio'),
        ('VIDEO', 'Vidéo'),
    )
    STATUS_CHOICES = (
        ('REQUESTED', 'Demandé'),
        ('ONGOING', 'En cours'),
        ('ENDED', 'Terminé'),
        ('MISSED', 'Manqué'),
    )

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='calls')
    initiator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calls_initiated')
    call_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='REQUESTED')
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    accepted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Appel"
        verbose_name_plural = "Appels"
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.get_call_type_display()} - {self.conversation} ({self.get_status_display()})"

    def is_active(self):
        return self.status in ['REQUESTED', 'ONGOING']

    def mark_ongoing(self):
        self.status = 'ONGOING'
        self.accepted = True
        self.save()

    def mark_ended(self):
        self.status = 'ENDED'
        self.ended_at = timezone.now()
        self.save()


class Message(models.Model):
    """Modèle pour les messages individuels"""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_sent')
    contenu = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    lu = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message de {self.sender.get_full_name()} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"
    
    def get_file_type(self):
        """Retourne le type du fichier attaché s'il existe"""
        if hasattr(self, 'file'):
            ext = self.file.fichier.name.split('.')[-1].lower()
            if ext in ['mp3', 'wav', 'ogg', 'm4a']:
                return 'audio'
            elif ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                return 'video'
            elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                return 'image'
            else:
                return 'file'
        return None


class MessageFile(models.Model):
    """Modèle pour les fichiers attachés aux messages"""
    FILE_TYPE_CHOICES = (
        ('image', 'Image'),
        ('video', 'Vidéo'),
        ('audio', 'Fichier audio'),
        ('document', 'Document'),
        ('autre', 'Autre'),
    )
    
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='file')
    fichier = models.FileField(upload_to='messages/%Y/%m/%d/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='autre')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Fichier de Message"
        verbose_name_plural = "Fichiers de Messages"
    
    def __str__(self):
        return f"Fichier de message - {self.fichier.name}"
    
    def get_file_size_mb(self):
        """Retourne la taille du fichier en MB"""
        if self.fichier:
            return round(self.fichier.size / (1024 * 1024), 2)
        return 0

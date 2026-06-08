from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, ClientProfile, AvocatProfile, DemandeConsultation, RendezVous, Note, DocumentDossier, Dossier, CreneauHoraire, Conge, Specialite, Message, MessageFile

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True, label="Prénom")
    last_name = forms.CharField(max_length=150, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Adresse Email")
    telephone = forms.CharField(max_length=20, required=True, label="Téléphone (WhatsApp ou Mobile Money)")
    adresse = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label="Adresse physique")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'telephone')

    def save(self, commit=True):
        user = super().save(commit=False)
        # L'inscription directe via le formulaire public crée automatiquement un Client
        user.role = 'CLIENT'
        user.telephone = self.cleaned_data['telephone']
        if commit:
            user.save()
            # Le signal post_save va créer le ClientProfile, nous devons ensuite y enregistrer l'adresse
            profile = user.client_profile
            profile.adresse = self.cleaned_data['adresse']
            profile.save()
        return user


class LawyerRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True, label="Prénom")
    last_name = forms.CharField(max_length=150, required=True, label="Nom")
    email = forms.EmailField(required=True, label="Adresse Email")
    telephone = forms.CharField(max_length=20, required=True, label="Téléphone professionnel")
    tarif_horaire = forms.DecimalField(max_digits=10, decimal_places=2, initial=0.0, label="Tarif Horaire (FCFA)")
    cabinet = forms.CharField(max_length=200, required=True, label="Cabinet / Étude")
    ville = forms.CharField(max_length=100, required=True, label="Ville")
    annees_experience = forms.IntegerField(min_value=0, initial=0, label="Années d'expérience")
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=True, label="Description professionnelle")
    specialites = forms.ModelMultipleChoiceField(
        queryset=Specialite.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Spécialités juridiques"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'telephone')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'AVOCAT'
        user.telephone = self.cleaned_data['telephone']
        if commit:
            user.save()
            profile = user.avocat_profile
            profile.tarif_horaire = self.cleaned_data['tarif_horaire']
            profile.cabinet = self.cleaned_data['cabinet']
            profile.ville = self.cleaned_data['ville']
            profile.annees_experience = self.cleaned_data['annees_experience']
            profile.description = self.cleaned_data['description']
            profile.is_approved = False # En attente de validation admin
            profile.specialites.set(self.cleaned_data['specialites'])
            profile.save()
        return user


class ClientProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="Prénom")
    last_name = forms.CharField(max_length=150, label="Nom")
    email = forms.EmailField(label="Adresse Email")
    telephone = forms.CharField(max_length=20, label="Téléphone")
    photo = forms.ImageField(required=False, label="Photo de profil")

    class Meta:
        model = ClientProfile
        fields = ('adresse',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['telephone'].initial = self.instance.user.telephone
            self.fields['photo'].initial = self.instance.user.photo

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.telephone = self.cleaned_data['telephone']
        user.photo = self.cleaned_data['photo']
        if commit:
            user.save()
            profile.save()
        return profile


class AvocatProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="Prénom")
    last_name = forms.CharField(max_length=150, label="Nom")
    email = forms.EmailField(label="Adresse Email")
    telephone = forms.CharField(max_length=20, label="Téléphone")
    photo = forms.ImageField(required=False, label="Photo de profil")

    class Meta:
        model = AvocatProfile
        fields = ('tarif_horaire', 'cabinet', 'ville', 'annees_experience', 'description', 'specialites')
        widgets = {
            'tarif_horaire': forms.NumberInput(attrs={'class': 'form-control'}),
            'cabinet': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Cabinet Ewondo'}),
            'ville': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Yaoundé'}),
            'annees_experience': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'specialites': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['telephone'].initial = self.instance.user.telephone
            self.fields['photo'].initial = self.instance.user.photo

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.telephone = self.cleaned_data['telephone']
        user.photo = self.cleaned_data['photo']
        if commit:
            user.save()
            profile.save()
            self.save_m2m() # Nécessaire pour les spécialités
        return profile


class DemandeConsultationForm(forms.ModelForm):
    class Meta:
        model = DemandeConsultation
        fields = ('sujet', 'description')
        widgets = {
            'sujet': forms.TextInput(attrs={'placeholder': 'Ex: Contestation de licenciement abusif, Litige foncier'}),
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Décrivez précisément les détails de votre problème juridique.'}),
        }


class RendezVousForm(forms.ModelForm):
    class Meta:
        model = RendezVous
        fields = ('date_heure', 'motif')
        widgets = {
            'date_heure': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'motif': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Objectif de la rencontre'}),
        }


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ('note', 'commentaire')
        widgets = {
            'note': forms.Select(attrs={'class': 'form-select'}),
            'commentaire': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Partagez votre retour d\'expérience sur cet avocat...'}),
        }


class DocumentDossierForm(forms.ModelForm):
    class Meta:
        model = DocumentDossier
        fields = ('titre', 'fichier')
        widgets = {
            'titre': forms.TextInput(attrs={'placeholder': 'Ex: Contrat de bail, Lettre de mise en demeure'}),
        }


class DossierForm(forms.ModelForm):
    class Meta:
        model = Dossier
        fields = ('avocat', 'titre', 'description')
        widgets = {
            'titre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Litige foncier Bonapriso'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Décrivez votre affaire et vos objectifs...'}),
            'avocat': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, avocats_eligibles=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['avocat'].queryset = avocats_eligibles or AvocatProfile.objects.none()
        self.fields['avocat'].label = "Avocat concerné"
        self.fields['titre'].label = "Intitulé / Titre de l'affaire"
        self.fields['description'].label = "Description de l'affaire"


class CreneauHoraireForm(forms.ModelForm):
    class Meta:
        model = CreneauHoraire
        fields = ('jour_semaine', 'heure_debut', 'heure_fin')
        widgets = {
            'jour_semaine': forms.Select(attrs={'class': 'form-select'}),
            'heure_debut': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'heure_fin': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }


class CongeForm(forms.ModelForm):
    class Meta:
        model = Conge
        fields = ('date_debut', 'date_fin', 'motif')
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'motif': forms.TextInput(attrs={'placeholder': 'Ex: Congés annuels, Déplacement professionnel'}),
        }


class AdminNotificationForm(forms.Form):
    destinataire = forms.ChoiceField(choices=[
        ('ALL', 'Tous les utilisateurs'),
        ('CLIENTS', 'Tous les clients'),
        ('AVOCATS', 'Tous les avocats'),
    ], widget=forms.Select(attrs={'class': 'form-select'}), label="Groupe cible")
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Saisissez le message de notification...'}), label="Message")


class UserRoleForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('role', 'is_active')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }


# ==========================================
# MESSAGING FORMS
# ==========================================

class MessageForm(forms.ModelForm):
    fichier = forms.FileField(required=False, label="Ajouter un fichier (image, vidéo, audio)")
    
    class Meta:
        model = Message
        fields = ('contenu',)
        widgets = {
            'contenu': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Écrivez votre message...',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contenu'].label = "Message"


class MessageFileForm(forms.ModelForm):
    class Meta:
        model = MessageFile
        fields = ('fichier', 'file_type')
        widgets = {
            'fichier': forms.FileInput(attrs={'accept': 'image/*,video/*,audio/*,.pdf,.doc,.docx'}),
            'file_type': forms.Select(attrs={'class': 'form-select'}),
        }

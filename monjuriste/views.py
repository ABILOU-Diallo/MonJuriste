from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from django.http import HttpResponseForbidden, Http404
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.core.cache import cache

from .models import (
    User, Specialite, ClientProfile, AvocatProfile, DemandeConsultation,
    RendezVous, Dossier, DocumentDossier, Paiement, Note, Notification,
    EmailCommunication, CreneauHoraire, Conge, Conversation, ConversationCall, Message, MessageFile
)
from .forms import (
    CustomUserCreationForm, LawyerRegistrationForm, ClientProfileForm,
    AvocatProfileForm, DemandeConsultationForm, RendezVousForm, NoteForm,
    DocumentDossierForm, CreneauHoraireForm, CongeForm, AdminNotificationForm,
    UserRoleForm, MessageForm, MessageFileForm
)
from .decorators import role_required, RoleRequiredMixin
from .services import OrangeMoneyService, MTNMoneyService
from .utils import create_notification, send_automatic_email

# ==========================================
# 1. VISITEUR VIEWS (NON AUTHENTIFIÉ)
# ==========================================

def visitor_index(request):
    """
    Page d'accueil de la plateforme avec présentation, liste des spécialités,
    et statistiques générales.
    """
    specialites = Specialite.objects.annotate(num_avocats=Count('avocats')).order_by('-num_avocats')[:6]
    avocats_premium = AvocatProfile.objects.filter(is_approved=True).order_by('-user__date_joined')[:3]
    
    # Statistiques publiques
    stats = {
        'total_avocats': AvocatProfile.objects.filter(is_approved=True).count(),
        'total_clients': ClientProfile.objects.count(),
        'total_dossiers': Dossier.objects.count(),
    }
    
    return render(request, 'visitor/index.html', {
        'specialites': specialites,
        'avocats_premium': avocats_premium,
        'stats': stats,
    })


def register(request):
    """
    Inscription d'un nouvel utilisateur (devient automatiquement Client).
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Connexion automatique après inscription
            login(request, user)
            
            # Envoi d'un email de bienvenue
            send_automatic_email(
                user,
                "Bienvenue sur MonJuriste !",
                f"Bonjour {user.first_name},\n\nVotre compte client a été créé avec succès sur MonJuriste. Vous pouvez désormais consulter les profils des avocats et planifier vos consultations.\n\nCordialement,\nL'équipe MonJuriste"
            )
            create_notification(user, "Bienvenue sur MonJuriste ! Votre profil client est complété.")
            
            messages.success(request, "Inscription réussie ! Bienvenue sur la plateforme.")
            return redirect('client_dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'visitor/register.html', {'form': form})


def lawyer_register(request):
    """
    Inscription d'un nouvel avocat (en attente de validation admin).
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = LawyerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Notification aux admins
            admins = User.objects.filter(role='ADMIN')
            for admin in admins:
                create_notification(admin, f"Nouvel avocat en attente de validation : {user.get_full_name()}")

            # Email à l'avocat
            send_automatic_email(
                user,
                "Inscription Avocat reçue - MonJuriste",
                f"Bonjour Maître {user.last_name},\n\nVotre demande d'inscription en tant qu'avocat sur MonJuriste a été reçue. Notre équipe administrative procède à sa validation. Vous recevrez un email dès que votre compte sera actif.\n\nCordialement,\nL'équipe MonJuriste"
            )

            messages.info(request, "Inscription enregistrée ! Votre profil est en attente de validation par un administrateur.")
            return redirect('login')
    else:
        form = LawyerRegistrationForm()
    return render(request, 'visitor/lawyer_register.html', {'form': form})


@login_required
def dashboard_redirect(request):
    """
    Redirige dynamiquement l'utilisateur vers son tableau de bord spécifique selon son rôle.
    """
    if request.user.role == 'CLIENT':
        return redirect('client_dashboard')
    elif request.user.role == 'AVOCAT':
        # Vérifier si l'avocat est approuvé
        if hasattr(request.user, 'avocat_profile') and request.user.avocat_profile.is_approved:
            return redirect('avocat_dashboard')
        else:
            # S'il n'est pas approuvé, on déconnecte et on renvoie une erreur
            messages.warning(request, "Votre compte avocat est en attente d'approbation.")
            logout(request)
            return redirect('login')
    elif request.user.role == 'ADMIN' or request.user.is_superuser:
        return redirect('admin_dashboard')
    else:
        return redirect('visitor_index')


# ==========================================
# 2. CLIENT VIEWS (AUTHENTIFIÉ)
# ==========================================

@login_required
@role_required('CLIENT')
def client_dashboard(request):
    """
    Tableau de bord principal du Client.
    """
    client_profile = request.user.client_profile
    demandes_recentes = DemandeConsultation.objects.filter(client=client_profile)[:5]
    rdv_a_venir = RendezVous.objects.filter(client=client_profile, date_heure__gte=timezone.now()).order_by('date_heure')[:5]
    dossiers_actifs = Dossier.objects.filter(client=client_profile).exclude(statut='TERMINE')[:5]
    unread_notifs_count = Notification.objects.filter(user=request.user, lu=False).count()
    
    context = {
        'demandes': demandes_recentes,
        'rdv': rdv_a_venir,
        'dossiers': dossiers_actifs,
        'unread_notifs_count': unread_notifs_count,
    }
    return render(request, 'client/dashboard.html', context)


@login_required
@role_required('CLIENT')
def avocat_list(request):
    """
    Liste des avocats approuvés avec filtres par spécialité et recherche textuelle.
    """
    query = request.GET.get('q', '')
    specialite_id = request.GET.get('specialite', '')
    
    avocats = AvocatProfile.objects.filter(is_approved=True)
    
    if query:
        avocats = avocats.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(description__icontains=query)
        )
        
    if specialite_id:
        avocats = avocats.filter(specialites__id=specialite_id)
        
    avocats = avocats.distinct()
    specialites = Specialite.objects.annotate(num_avocats=Count('avocats'))
    
    return render(request, 'client/avocat_list.html', {
        'avocats': avocats,
        'specialites': specialites,
        'query': query,
        'selected_specialite': int(specialite_id) if specialite_id else None
    })


@login_required
@role_required('CLIENT')
def avocat_detail(request, pk):
    """
    Fiche détaillée d'un avocat, avec son planning de créneaux disponibles et ses avis.
    """
    avocat = get_object_or_404(AvocatProfile, pk=pk, is_approved=True)
    creneaux = avocat.creneaux.all()
    conges = avocat.conges.filter(date_fin__gte=timezone.now().date())
    avis = avocat.notes.all()
    
    # Vérifier si l'utilisateur a déjà noté cet avocat
    deja_note = False
    if hasattr(request.user, 'client_profile'):
        deja_note = Note.objects.filter(client=request.user.client_profile, avocat=avocat).exists()
    
    # Formulaire de note
    note_form = NoteForm()

    return render(request, 'client/avocat_detail.html', {
        'avocat': avocat,
        'creneaux': creneaux,
        'conges': conges,
        'avis': avis,
        'deja_note': deja_note,
        'note_form': note_form
    })


@login_required
@role_required('CLIENT')
def demande_creer(request, avocat_id):
    """
    Création d'une demande de consultation pour un avocat spécifique.
    """
    avocat = get_object_or_404(AvocatProfile, pk=avocat_id, is_approved=True)
    client_profile = request.user.client_profile
    
    if request.method == 'POST':
        form = DemandeConsultationForm(request.POST)
        if form.is_valid():
            demande = form.save(commit=False)
            demande.client = client_profile
            demande.avocat = avocat
            demande.statut = 'EN_ATTENTE'
            demande.save()
            
            messages.success(request, "Votre demande de consultation a été créée. Veuillez procéder au paiement pour la valider.")
            return redirect('paiement_form', demande_id=demande.id)
    else:
        form = DemandeConsultationForm()
        
    return render(request, 'client/demande_form.html', {'form': form, 'avocat': avocat})


@login_required
@role_required('CLIENT')
def paiement_form(request, demande_id):
    """
    Formulaire pour initier le paiement d'une consultation (Orange Money / MTN Money).
    """
    demande = get_object_or_404(DemandeConsultation, id=demande_id, client=request.user.client_profile)
    
    if demande.statut != 'EN_ATTENTE':
        messages.warning(request, "Cette demande a déjà fait l'objet d'un paiement ou d'un traitement.")
        return redirect('client_dashboard')
        
    tarif = demande.avocat.tarif_horaire
    
    if request.method == 'POST':
        moyen = request.POST.get('moyen_paiement')
        telephone = request.POST.get('telephone')
        
        if not moyen or not telephone:
            messages.error(request, "Veuillez remplir tous les champs du paiement.")
        else:
            # Choix du service
            if moyen == 'ORANGE_MONEY':
                service = OrangeMoneyService()
            else:
                service = MTNMoneyService()
                
            try:
                # Initialisation de la transaction simulée
                res = service.initiate_payment(telephone, tarif, f"DEM-{demande.id}")
                
                # Enregistrement de l'objet Paiement en attente
                paiement = Paiement.objects.create(
                    client=request.user.client_profile,
                    demande=demande,
                    montant=tarif,
                    moyen_paiement=moyen,
                    transaction_id=res['transaction_id'],
                    statut='EN_ATTENTE'
                )
                
                # Redirection vers la page de simulation de paiement
                return redirect(res['redirect_url'])
                
            except Exception as e:
                messages.error(request, f"Erreur lors de l'initialisation du paiement : {str(e)}")
                
    return render(request, 'client/paiement_form.html', {'demande': demande, 'tarif': tarif})


@login_required
@role_required('CLIENT')
def paiement_process(request, transaction_id):
    """
    Vue de simulation interactive de la passerelle de paiement Mobile Money.
    Permet au client de simuler une validation OTP (réussite) ou une annulation (échec).
    """
    paiement = get_object_or_404(Paiement, transaction_id=transaction_id, client=request.user.client_profile)
    demande = paiement.demande
    
    if paiement.statut != 'EN_ATTENTE':
        messages.warning(request, "Ce paiement a déjà été traité.")
        return redirect('client_dashboard')
        
    if request.method == 'POST':
        sim_action = request.POST.get('action') # 'SUCCESS' ou 'FAILED'
        
        if sim_action == 'SUCCESS':
            # Mise à jour du Paiement
            paiement.statut = 'REUSSI'
            paiement.save()
            
            # Mise à jour de la Demande
            demande.statut = 'PAYEE'
            demande.save()
            
            # Notification et email pour le Client
            create_notification(request.user, f"Votre paiement de {paiement.montant} FCFA pour la demande #{demande.id} a été validé.")
            send_automatic_email(
                request.user,
                "Confirmation de paiement - MonJuriste",
                f"Bonjour,\n\nNous confirmons la réception de votre paiement de {paiement.montant} FCFA (Réf: {transaction_id}) pour votre consultation avec Maître {demande.avocat.user.last_name}.\n\nL'avocat va désormais vous proposer un créneau de rendez-vous.\n\nCordialement,\nL'équipe MonJuriste"
            )
            
            # Notification et email pour l'Avocat
            create_notification(demande.avocat.user, f"Nouveau paiement reçu ({paiement.montant} FCFA) pour la demande #{demande.id}.")
            send_automatic_email(
                demande.avocat.user,
                "Nouveau paiement reçu - MonJuriste",
                f"Bonjour Maître,\n\nLe client {demande.client.user.get_full_name()} a réglé vos honoraires de {paiement.montant} FCFA pour la demande de consultation #{demande.id} ({demande.sujet}).\n\nVeuillez vous connecter pour valider la demande et planifier le rendez-vous.\n\nCordialement,\nL'équipe MonJuriste"
            )
            
            messages.success(request, "Simulation: Paiement validé avec succès !")
            return redirect('client_dashboard')
        else:
            # Cas d'échec
            paiement.statut = 'ECHOUE'
            paiement.save()
            
            create_notification(request.user, f"Échec du paiement Mobile Money (Réf: {transaction_id}). Veuillez réessayer.")
            messages.error(request, "Simulation: Le paiement a été annulé ou a échoué.")
            return redirect('paiement_form', demande_id=demande.id)
            
    return render(request, 'client/paiement_process.html', {
        'paiement': paiement,
        'demande': demande
    })


@login_required
@role_required('CLIENT')
def dossier_list_client(request):
    """
    Suivi des dossiers en cours par le client.
    """
    dossiers = Dossier.objects.filter(client=request.user.client_profile)
    return render(request, 'client/dossiers.html', {'dossiers': dossiers})


@login_required
@role_required('CLIENT')
def rendezvous_list_client(request):
    """
    Visualisation et prise de rendez-vous pour le client.
    """
    client_profile = request.user.client_profile
    rdvs = RendezVous.objects.filter(client=client_profile)
    
    # Formulaire de demande de rendez-vous pour proposer une date
    if request.method == 'POST':
        form = RendezVousForm(request.POST)
        demande_id = request.POST.get('demande_id')
        demande = get_object_or_404(DemandeConsultation, id=demande_id, client=client_profile, statut='PAYEE')
        
        if form.is_valid():
            rdv = form.save(commit=False)
            rdv.client = client_profile
            rdv.avocat = demande.avocat
            rdv.demande = demande
            rdv.statut = 'EN_ATTENTE'
            rdv.save()
            
            # Modifier statut demande
            demande.statut = 'ACCEPTEE'
            demande.save()
            
            # Notifications
            create_notification(demande.avocat.user, f"Rendez-vous proposé par le client {request.user.get_full_name()} pour le {rdv.date_heure}.")
            messages.success(request, "Proposition de rendez-vous envoyée à l'avocat.")
            return redirect('rendezvous_list_client')
    else:
        form = RendezVousForm()
        
    # Demandes payées n'ayant pas encore de rendez-vous programmé
    demandes_a_planifier = DemandeConsultation.objects.filter(client=client_profile, statut='PAYEE')
    
    return render(request, 'client/rendezvous.html', {
        'rdv_list': rdvs,
        'form': form,
        'demandes_a_planifier': demandes_a_planifier
    })


@login_required
@role_required('CLIENT')
def rendezvous_annuler_client(request, pk):
    """
    Annulation d'un rendez-vous par le client.
    """
    rdv = get_object_or_404(RendezVous, pk=pk, client=request.user.client_profile)
    if rdv.statut in ['EN_ATTENTE', 'ACCEPTE']:
        rdv.statut = 'ANNULE'
        rdv.save()
        
        # Notification avocat
        create_notification(rdv.avocat.user, f"Le rendez-vous du {rdv.date_heure} a été annulé par le client.")
        messages.success(request, "Rendez-vous annulé.")
    else:
        messages.error(request, "Impossible d'annuler ce rendez-vous dans son état actuel.")
    return redirect('rendezvous_list_client')


@login_required
@role_required('CLIENT')
def avocat_noter(request, avocat_id):
    """
    Notation et commentaire sur un avocat.
    """
    avocat = get_object_or_404(AvocatProfile, id=avocat_id, is_approved=True)
    client_profile = request.user.client_profile
    
    # Vérifier s'il a déjà noté
    existing_note = Note.objects.filter(client=client_profile, avocat=avocat).first()
    
    if request.method == 'POST':
        form = NoteForm(request.POST, instance=existing_note)
        if form.is_valid():
            note = form.save(commit=False)
            note.client = client_profile
            note.avocat = avocat
            note.save()
            
            # Notification à l'avocat
            create_notification(avocat.user, f"Vous avez reçu une nouvelle note de {note.note}/5 par un client.")
            
            messages.success(request, "Votre avis a été enregistré.")
            return redirect('avocat_detail', pk=avocat_id)
            
    return redirect('avocat_detail', pk=avocat_id)


@login_required
def notifications_list(request):
    """
    Gestion des notifications utilisateur (accessible par tous les rôles).
    """
    notifs = Notification.objects.filter(user=request.user)
    
    # Actions groupées
    action = request.GET.get('action')
    if action == 'read_all':
        notifs.update(lu=True)
        messages.success(request, "Toutes les notifications ont été marquées comme lues.")
        return redirect('notifications_list')
    elif action == 'clear_all':
        notifs.delete()
        messages.success(request, "Toutes les notifications ont été supprimées.")
        return redirect('notifications_list')
        
    return render(request, 'client/notifications.html', {'notifications': notifs})


@login_required
def mark_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.lu = True
    notif.save()
    return redirect('notifications_list')


@login_required
def delete_notification(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.delete()
    return redirect('notifications_list')


@login_required
def emails_list(request):
    """
    Affiche la liste des communications mails reçues/historisées.
    """
    emails = EmailCommunication.objects.filter(user=request.user)
    return render(request, 'client/emails.html', {'emails': emails})


@login_required
def profil_edit(request):
    """
    Édition du compte pour modifier le profil, le mot de passe ou désactiver le compte.
    Filtre par type de profil.
    """
    if request.user.role == 'CLIENT':
        profile = request.user.client_profile
        form_class = ClientProfileForm
        template = 'client/profil.html'
    elif request.user.role == 'AVOCAT':
        profile = request.user.avocat_profile
        form_class = AvocatProfileForm
        template = 'avocat/profil.html'
    else:
        # Administrateur
        profile = None
        form_class = None
        template = 'client/profil.html'
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 1. Mise à jour des informations du profil
        if action == 'update_profile' and form_class:
            form = form_class(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, "Profil mis à jour avec succès.")
                return redirect('profil_edit')
                
        # 2. Changement de mot de passe
        elif action == 'change_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user) # Évite la déconnexion
                messages.success(request, "Votre mot de passe a été modifié.")
                return redirect('profil_edit')
            else:
                messages.error(request, "Erreur lors de la modification du mot de passe.")
                
        # 3. Désactivation de compte
        elif action == 'deactivate_account':
            user = request.user
            user.is_active = False
            user.save()
            logout(request)
            messages.info(request, "Votre compte a été désactivé.")
            return redirect('visitor_index')
    else:
        form = form_class(instance=profile) if form_class else None
        password_form = PasswordChangeForm(request.user)
        
    return render(request, template, {
        'form': form,
        'password_form': password_form
    })


# ==========================================
# 3. AVOCAT VIEWS (AUTHENTIFIÉ)
# ==========================================

@login_required
@role_required('AVOCAT')
def avocat_dashboard(request):
    """
    Tableau de bord de l'avocat.
    """
    avocat_profile = request.user.avocat_profile
    rdv_du_jour = RendezVous.objects.filter(
        avocat=avocat_profile,
        date_heure__date=timezone.now().date(),
        statut='ACCEPTE'
    )
    rdv_a_venir = RendezVous.objects.filter(
        avocat=avocat_profile,
        date_heure__gte=timezone.now(),
    ).exclude(statut__in=['REJETE', 'ANNULE']).order_by('date_heure')[:5]
    
    dossiers_actifs = Dossier.objects.filter(avocat=avocat_profile, statut='ACCEPTE')
    
    # Demandes concernées (en attente de paiement ou payées)
    demandes_a_valider = DemandeConsultation.objects.filter(avocat=avocat_profile, statut__in=['EN_ATTENTE', 'PAYEE'])
    
    # Revenus cumulés
    total_revenus = Paiement.objects.filter(
        demande__avocat=avocat_profile,
        statut='REUSSI'
    ).aggregate(Sum('montant'))['montant__sum'] or 0.0

    return render(request, 'avocat/dashboard.html', {
        'rdv_du_jour': rdv_du_jour,
        'rdv_a_venir': rdv_a_venir,
        'dossiers': dossiers_actifs,
        'demandes_a_valider': demandes_a_valider,
        'total_revenus': total_revenus,
    })


@login_required
@role_required('AVOCAT')
def avocat_planning(request):
    """
    Gestion des plages de travail hebdomadaires et des congés.
    """
    avocat_profile = request.user.avocat_profile
    creneaux = CreneauHoraire.objects.filter(avocat=avocat_profile)
    conges = Conge.objects.filter(avocat=avocat_profile)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Ajouter un créneau
        if action == 'add_creneau':
            form_creneau = CreneauHoraireForm(request.POST)
            if form_creneau.is_valid():
                creneau = form_creneau.save(commit=False)
                creneau.avocat = avocat_profile
                creneau.save()
                messages.success(request, "Créneau de disponibilité ajouté.")
                return redirect('avocat_planning')
                
        # Ajouter un congé
        elif action == 'add_conge':
            form_conge = CongeForm(request.POST)
            if form_conge.is_valid():
                conge = form_conge.save(commit=False)
                conge.avocat = avocat_profile
                conge.save()
                messages.success(request, "Période d'absence ajoutée.")
                return redirect('avocat_planning')
    else:
        form_creneau = CreneauHoraireForm()
        form_conge = CongeForm()
        
    return render(request, 'avocat/planning.html', {
        'creneaux': creneaux,
        'conges': conges,
        'form_creneau': form_creneau,
        'form_conge': form_conge
    })


@login_required
@role_required('AVOCAT')
def delete_creneau(request, pk):
    creneau = get_object_or_404(CreneauHoraire, pk=pk, avocat=request.user.avocat_profile)
    creneau.delete()
    messages.info(request, "Créneau supprimé.")
    return redirect('avocat_planning')


@login_required
@role_required('AVOCAT')
def delete_conge(request, pk):
    conge = get_object_or_404(Conge, pk=pk, avocat=request.user.avocat_profile)
    conge.delete()
    messages.info(request, "Absence supprimée.")
    return redirect('avocat_planning')


@login_required
@role_required('AVOCAT')
def avocat_rendezvous(request):
    """
    Gestion des rendez-vous par l'avocat : Acceptation, Rejet, Clôture.
    """
    avocat_profile = request.user.avocat_profile
    rdvs = RendezVous.objects.filter(avocat=avocat_profile).order_by('-date_heure')
    
    if request.method == 'POST':
        rdv_id = request.POST.get('rdv_id')
        statut = request.POST.get('statut')
        rdv = get_object_or_404(RendezVous, id=rdv_id, avocat=avocat_profile)
        
        if statut in ['ACCEPTE', 'REJETE', 'TERMINE']:
            rdv.statut = statut
            rdv.save()
            
            # Notifications client
            create_notification(rdv.client.user, f"Votre rendez-vous du {rdv.date_heure} a été marqué comme : {rdv.get_statut_display()}.")
            send_automatic_email(
                rdv.client.user,
                f"Statut rendez-vous mis à jour - MonJuriste",
                f"Bonjour,\n\nL'avocat Maître {rdv.avocat.user.last_name} a mis à jour l'état de votre rendez-vous du {rdv.date_heure}.\n\nStatut actuel : {rdv.get_statut_display()}\n\nCordialement,\nL'équipe MonJuriste"
            )
            
            # Si le rendez-vous est accepté, on crée automatiquement un Dossier s'il n'en existe pas déjà un pour cette demande
            if statut == 'ACCEPTE' and rdv.demande and not Dossier.objects.filter(demande=rdv.demande).exists():
                Dossier.objects.create(
                    client=rdv.client,
                    avocat=avocat_profile,
                    demande=rdv.demande,
                    titre=rdv.demande.sujet,
                    description=rdv.demande.description,
                    statut='ACCEPTE' # En cours
                )
                create_notification(rdv.client.user, f"Un dossier de suivi a été automatiquement ouvert pour : {rdv.demande.sujet}.")

            messages.success(request, f"Rendez-vous mis à jour ({rdv.get_statut_display()}).")
            return redirect('avocat_rendezvous')
            
    return render(request, 'avocat/rendezvous.html', {'rdv_list': rdvs})


@login_required
@role_required('AVOCAT')
def avocat_dossiers(request):
    """
    Gestion des dossiers clients de l'avocat.
    """
    avocat_profile = request.user.avocat_profile
    dossiers = Dossier.objects.filter(avocat=avocat_profile)
    
    if request.method == 'POST':
        # Création directe d'un dossier
        client_id = request.POST.get('client_id')
        client = get_object_or_404(ClientProfile, id=client_id)
        titre = request.POST.get('titre')
        description = request.POST.get('description')
        
        if titre and description:
            Dossier.objects.create(
                client=client,
                avocat=avocat_profile,
                titre=titre,
                description=description,
                statut='ACCEPTE'
            )
            create_notification(client.user, f"Maître {request.user.last_name} a ouvert un nouveau dossier : {titre}.")
            messages.success(request, "Dossier client créé avec succès.")
            return redirect('avocat_dossiers')
            
    clients = ClientProfile.objects.all()
    return render(request, 'avocat/dossiers.html', {'dossiers': dossiers, 'clients': clients})


@login_required
@role_required('AVOCAT')
def avocat_dossier_detail(request, pk):
    """
    Détail d'un dossier de suivi avec possibilité d'ajouter des fichiers / pièces jointes.
    """
    avocat_profile = request.user.avocat_profile
    dossier = get_object_or_404(Dossier, pk=pk, avocat=avocat_profile)
    documents = dossier.documents.all()
    
    # Formulaire de dépôt de document
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'upload_doc':
            form = DocumentDossierForm(request.POST, request.FILES)
            if form.is_valid():
                doc = form.save(commit=False)
                doc.dossier = dossier
                doc.uploaded_by = request.user
                doc.save()
                
                # Notification de dépôt au client
                create_notification(dossier.client.user, f"Un nouveau document '{doc.titre}' a été ajouté à votre dossier par l'avocat.")
                messages.success(request, "Document ajouté au dossier.")
                return redirect('avocat_dossier_detail', pk=dossier.id)
                
        elif action == 'update_status':
            nouveau_statut = request.POST.get('statut')
            if nouveau_statut in ['EN_ATTENTE', 'ACCEPTE', 'REJETE', 'TERMINE']:
                dossier.statut = nouveau_statut
                dossier.save()
                create_notification(dossier.client.user, f"Le statut de votre dossier '{dossier.titre}' a été modifié : {dossier.get_statut_display()}.")
                messages.success(request, "Statut du dossier mis à jour.")
                return redirect('avocat_dossier_detail', pk=dossier.id)
    else:
        form = DocumentDossierForm()
        
    return render(request, 'avocat/dossier_detail.html', {
        'dossier': dossier,
        'documents': documents,
        'form': form
    })


@login_required
@role_required('AVOCAT')
def avocat_notes(request):
    """
    Consultation des notes et avis laissés par les clients.
    """
    avocat_profile = request.user.avocat_profile
    notes = Note.objects.filter(avocat=avocat_profile)
    return render(request, 'avocat/avis.html', {
        'notes': notes,
        'note_moyenne': avocat_profile.note_moyenne,
        'total_avis': avocat_profile.total_avis
    })


@login_required
@role_required('AVOCAT')
def avocat_paiements(request):
    """
    Historique des paiements reçus par l'avocat.
    """
    avocat_profile = request.user.avocat_profile
    paiements = Paiement.objects.filter(demande__avocat=avocat_profile, statut='REUSSI')
    total_revenus = paiements.aggregate(Sum('montant'))['montant__sum'] or 0.0
    return render(request, 'avocat/paiements.html', {
        'paiements': paiements,
        'total_revenus': total_revenus
    })


# ==========================================
# 4. ADMINISTRATEUR VIEWS (SUPERUSER/ADMIN)
# ==========================================

@login_required
@role_required('ADMIN')
def admin_dashboard(request):
    """
    Tableau de bord de suivi statistique pour les administrateurs.
    """
    # Statistiques clés
    stats = {
        'total_users': User.objects.count(),
        'total_clients': ClientProfile.objects.count(),
        'total_avocats': AvocatProfile.objects.count(),
        'avocats_non_approuves': AvocatProfile.objects.filter(is_approved=False).count(),
        'total_rdv': RendezVous.objects.count(),
        'total_paiements': Paiement.objects.filter(statut='REUSSI').count(),
        'chiffre_affaires': Paiement.objects.filter(statut='REUSSI').aggregate(Sum('montant'))['montant__sum'] or 0.0,
    }
    
    # Listes pour approbation et suivi
    avocats_en_attente = AvocatProfile.objects.filter(is_approved=False)
    paiements_recents = Paiement.objects.all().order_by('-created_at')[:5]
    
    return render(request, 'admin_custom/dashboard.html', {
        'stats': stats,
        'avocats_en_attente': avocats_en_attente,
        'paiements_recents': paiements_recents,
    })


@login_required
@role_required('ADMIN')
def admin_approve_lawyer(request, avocat_id):
    """
    Approbation d'un profil avocat.
    """
    avocat = get_object_or_404(AvocatProfile, id=avocat_id)
    avocat.is_approved = True
    avocat.save()
    
    # Notification et Email à l'avocat approuvé
    create_notification(avocat.user, "Votre compte avocat a été validé par un administrateur. Vous êtes désormais visible sur la plateforme.")
    send_automatic_email(
        avocat.user,
        "Votre compte MonJuriste est activé !",
        f"Bonjour Maître {avocat.user.last_name},\n\nNous avons le plaisir de vous informer que votre compte professionnel d'avocat sur MonJuriste a été approuvé.\n\nVous pouvez dès à présent configurer vos créneaux horaires et recevoir des demandes de consultation.\n\nCordialement,\nL'équipe administrative MonJuriste"
    )
    
    messages.success(request, f"L'avocat {avocat.user.get_full_name()} a été approuvé.")
    return redirect('admin_dashboard')


@login_required
@role_required('ADMIN')
def admin_utilisateurs(request):
    """
    Gestion globale des comptes utilisateurs (activation, modification, etc.).
    """
    utilisateurs = User.objects.all().order_by('-date_joined')
    return render(request, 'admin_custom/utilisateurs.html', {'utilisateurs': utilisateurs})


@login_required
@role_required('ADMIN')
def admin_modifier_utilisateur(request, user_id):
    """
    Modification rapide du rôle ou de l'état d'un utilisateur par l'administrateur.
    """
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UserRoleForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Utilisateur {user.username} mis à jour.")
            return redirect('admin_utilisateurs')
    else:
        form = UserRoleForm(instance=user)
        
    return render(request, 'admin_custom/utilisateurs_form.html', {'form': form, 'target_user': user})


@login_required
@role_required('ADMIN')
def admin_supprimer_utilisateur(request, user_id):
    """
    Suppression définitive d'un compte utilisateur par l'administrateur.
    """
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.error(request, "Impossible de supprimer un superutilisateur.")
    else:
        username = user.username
        user.delete()
        messages.success(request, f"L'utilisateur {username} a été supprimé avec succès.")
    return redirect('admin_utilisateurs')


@login_required
@role_required('ADMIN')
def admin_notifier(request):
    """
    Permet à l'admin d'envoyer des notifications ciblées ou globales à des groupes d'utilisateurs.
    """
    if request.method == 'POST':
        form = AdminNotificationForm(request.POST)
        if form.is_valid():
            cible = form.cleaned_data['destinataire']
            message = form.cleaned_data['message']
            
            # Filtre des utilisateurs destinataires
            if cible == 'ALL':
                users = User.objects.all()
            elif cible == 'CLIENTS':
                users = User.objects.filter(role='CLIENT')
            else: # AVOCATS
                users = User.objects.filter(role='AVOCAT')
                
            for user in users:
                create_notification(user, f"[Annonce Admin] {message}")
                
            messages.success(request, f"Notification envoyée à {users.count()} utilisateurs.")
            return redirect('admin_dashboard')
    else:
        form = AdminNotificationForm()
        
    return render(request, 'admin_custom/notifier.html', {'form': form})


# ==========================================
# MESSAGING VIEWS
# ==========================================

@login_required
def conversation_list(request):
    """
    Liste toutes les conversations de l'utilisateur courant.
    """
    user = request.user
    
    if user.role == 'CLIENT':
        conversations = Conversation.objects.filter(client__user=user).prefetch_related('avocat__user', 'messages')
    elif user.role == 'AVOCAT':
        conversations = Conversation.objects.filter(avocat__user=user).prefetch_related('client__user', 'messages')
    else:
        conversations = Conversation.objects.none()
    
    return render(request, 'messages/conversation_list.html', {'conversations': conversations})


@login_required
def conversation_detail(request, conversation_id):
    """
    Affiche une conversation spécifique et permet d'envoyer des messages.
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    user = request.user
    
    # Vérifier les permissions
    is_client = hasattr(user, 'client_profile') and conversation.client.user == user
    is_avocat = hasattr(user, 'avocat_profile') and conversation.avocat.user == user
    
    if not (is_client or is_avocat):
        raise PermissionDenied("Vous n'avez pas accès à cette conversation.")
    
    messages_list = conversation.messages.all()
    
    if request.method == 'POST':
        form = MessageForm(request.POST)
        fichier_form = MessageFileForm(request.POST, request.FILES) if 'fichier' in request.FILES else MessageFileForm()
        
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = user
            message.save()
            
            # Ajouter un fichier si fourni
            if request.FILES.get('fichier'):
                fichier = request.FILES['fichier']
                # Déterminer le type de fichier
                ext = fichier.name.split('.')[-1].lower()
                if ext in ['mp3', 'wav', 'ogg', 'm4a']:
                    file_type = 'audio'
                elif ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                    file_type = 'video'
                elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    file_type = 'image'
                else:
                    file_type = 'document'
                
                MessageFile.objects.create(
                    message=message,
                    fichier=fichier,
                    file_type=file_type
                )
            
            # Notifier l'autre utilisateur
            if is_client:
                destinataire = conversation.avocat.user
                create_notification(destinataire, f"Nouveau message de {user.get_full_name()}")
            else:
                destinataire = conversation.client.user
                create_notification(destinataire, f"Nouveau message de {user.get_full_name()}")
            
            return redirect('conversation_detail', conversation_id=conversation.id)
    else:
        form = MessageForm()
        fichier_form = MessageFileForm()
    
    # Marquer les messages comme lus
    messages_list.exclude(sender=user).update(lu=True)
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
        'form': form,
        'fichier_form': fichier_form,
        'is_client': is_client,
        'is_avocat': is_avocat,
    }
    return render(request, 'messages/conversation_detail.html', context)


@login_required
def start_call(request, conversation_id, call_type):
    """
    Démarre un appel audio ou vidéo pour une conversation.
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    user = request.user

    is_client = hasattr(user, 'client_profile') and conversation.client.user == user
    is_avocat = hasattr(user, 'avocat_profile') and conversation.avocat.user == user
    if not (is_client or is_avocat):
        raise PermissionDenied("Vous n'avez pas accès à cette conversation.")

    if call_type not in ['audio', 'video']:
        raise Http404("Type d'appel non supporté.")

    call = ConversationCall.objects.create(
        conversation=conversation,
        initiator=user,
        call_type=call_type.upper(),
        status='REQUESTED'
    )

    other_user = conversation.avocat.user if is_client else conversation.client.user
    create_notification(other_user, f"{user.get_full_name()} vous invite à un appel {call_type}.")

    return redirect('call_room', call_id=call.id)


@login_required
def call_room(request, call_id):
    """
    Page de l'appel audio / vidéo.
    """
    call = get_object_or_404(ConversationCall, id=call_id)
    user = request.user

    is_client = hasattr(user, 'client_profile') and call.conversation.client.user == user
    is_avocat = hasattr(user, 'avocat_profile') and call.conversation.avocat.user == user
    if not (is_client or is_avocat):
        raise PermissionDenied("Vous n'avez pas accès à cet appel.")

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept' and call.status == 'REQUESTED':
            call.accepted = True
            call.status = 'ONGOING'
            call.save()
            other_user = call.conversation.avocat.user if is_client else call.conversation.client.user
            create_notification(other_user, f"{user.get_full_name()} a accepté votre appel {call.call_type.lower()}.")
        elif action == 'end' and call.status in ['REQUESTED', 'ONGOING']:
            call.status = 'ENDED'
            call.ended_at = timezone.now()
            call.save()
            return redirect('conversation_detail', conversation_id=call.conversation.id)

    return render(request, 'messages/call_room.html', {
        'call': call,
        'is_client': is_client,
        'is_avocat': is_avocat,
        'user': user,
    })


@login_required
def presence_heartbeat(request):
    """
    Endpoint léger pour enregistrer la présence en mémoire cache.
    Appelé régulièrement depuis le navigateur pour indiquer que l'utilisateur est en ligne.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    key = f'presence:{request.user.id}'
    # stocke le timestamp, expire automatiquement après 60s
    cache.set(key, timezone.now().timestamp(), timeout=60)
    return JsonResponse({'status': 'ok'})


@login_required
def incoming_calls_api(request):
    """
    Retourne les appels entrants non traités pour l'utilisateur connecté.
    """
    user = request.user
    # Les appels demandés où l'utilisateur est le destinataire
    calls = ConversationCall.objects.filter(status='REQUESTED').exclude(initiator=user)
    incoming = []
    for c in calls:
        convo = c.conversation
        # vérifier que l'utilisateur est participant de la conversation
        if convo.client.user == user or convo.avocat.user == user:
            initiator_online = False
            initiator_last = cache.get(f'presence:{c.initiator.id}')
            if initiator_last and (timezone.now().timestamp() - float(initiator_last) < 30):
                initiator_online = True

            incoming.append({
                'id': c.id,
                'conversation_id': convo.id,
                'initiator_id': c.initiator.id,
                'initiator_name': c.initiator.get_full_name() or c.initiator.username,
                'call_type': c.call_type,
                'started_at': c.started_at.isoformat(),
                'initiator_online': initiator_online,
            })

    return JsonResponse({'incoming': incoming})


@login_required
def start_conversation(request, avocat_id):
    """
    Démarre une nouvelle conversation entre un client et un avocat.
    """
    user = request.user
    
    # Vérifier que l'utilisateur est un client
    if not hasattr(user, 'client_profile'):
        messages.error(request, "Seuls les clients peuvent démarrer une conversation.")
        return redirect('avocat_list')
    
    avocat = get_object_or_404(AvocatProfile, id=avocat_id)
    client = user.client_profile
    
    # Créer ou récupérer la conversation
    conversation, created = Conversation.objects.get_or_create(
        client=client,
        avocat=avocat
    )
    
    if created:
        create_notification(avocat.user, f"Nouveau message de {user.get_full_name()}")
    
    return redirect('conversation_detail', conversation_id=conversation.id)

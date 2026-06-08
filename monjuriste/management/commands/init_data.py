from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from monjuriste.models import Specialite, AvocatProfile, ClientProfile, CreneauHoraire
import datetime

User = get_user_model()

class Command(BaseCommand):
    help = "Initialise la base de données avec des spécialités juridiques, un administrateur et des profils de test."

    def handle(self, *args, **options):
        self.stdout.write("Initialisation des données de test...")

        # 1. Création des spécialités juridiques
        specs_data = [
            ("Droit de la Famille", "Divorce, garde d'enfants, successions, mariages et PACS."),
            ("Droit du Travail", "Licenciements, contrats de travail, litiges avec l'employeur, harcèlement."),
            ("Droit Immobilier", "Baux d'habitation et commerciaux, litiges de copropriété, ventes immobilières."),
            ("Droit des Affaires", "Création de sociétés, fusions-acquisitions, contrats commerciaux, propriété intellectuelle."),
            ("Droit Pénal", "Défense pénale, garde à vue, tribunaux correctionnels, assistance aux victimes."),
        ]
        
        specialites = {}
        for nom, desc in specs_data:
            spec, created = Specialite.objects.get_or_create(nom=nom, defaults={'description': desc})
            specialites[nom] = spec
            if created:
                self.stdout.write(f"Spécialité créée : {nom}")

        # 2. Création de l'Administrateur
        if not User.objects.filter(username="admin").exists():
            admin_user = User.objects.create_superuser(
                username="admin",
                email="admin@monjuriste.cm",
                password="adminpassword",
                first_name="Admin",
                last_name="System",
                role="ADMIN"
            )
            self.stdout.write("Superutilisateur 'admin' (password: adminpassword) créé.")
        else:
            admin_user = User.objects.get(username="admin")

        # 3. Création du Client de test
        if not User.objects.filter(username="client_test").exists():
            client_user = User.objects.create_user(
                username="client_test",
                email="client@example.com",
                password="clientpassword",
                first_name="Jean",
                last_name="Kouam",
                role="CLIENT",
                telephone="677889900"
            )
            profile = client_user.client_profile
            profile.adresse = "Rond-point Deido, Douala"
            profile.save()
            self.stdout.write("Utilisateur client 'client_test' (password: clientpassword) créé.")

        # 4. Création de l'Avocat de test 1 (Approuvé)
        if not User.objects.filter(username="avocat_dupont").exists():
            avo_user = User.objects.create_user(
                username="avocat_dupont",
                email="dupont@monjuriste.cm",
                password="lawyerpassword",
                first_name="Charles",
                last_name="Dupont",
                role="AVOCAT",
                telephone="699112233"
            )
            profile = avo_user.avocat_profile
            profile.tarif_horaire = 25000.00
            profile.cabinet = "Cabinet Dupont"
            profile.ville = "Douala"
            profile.annees_experience = 12
            profile.description = (
                "Titulaire d'un Doctorat en droit privé, Maître Charles Dupont exerce depuis plus de 10 ans "
                "dans la résolution des litiges contractuels, des procédures de licenciement et du droit social. "
                "Il vous accompagne avec écoute et rigueur devant les instances juridictionnelles camerounaises."
            )
            profile.is_approved = True
            profile.specialites.add(specialites["Droit du Travail"], specialites["Droit des Affaires"])
            profile.save()
            
            # Ajouter des créneaux
            CreneauHoraire.objects.create(avocat=profile, jour_semaine=0, heure_debut=datetime.time(9, 0), heure_fin=datetime.time(12, 0)) # Lundi matin
            CreneauHoraire.objects.create(avocat=profile, jour_semaine=2, heure_debut=datetime.time(14, 0), heure_fin=datetime.time(17, 0)) # Mercredi aprem
            CreneauHoraire.objects.create(avocat=profile, jour_semaine=4, heure_debut=datetime.time(9, 0), heure_fin=datetime.time(16, 0)) # Vendredi journée
            
            self.stdout.write("Avocat approuvé 'avocat_dupont' (password: lawyerpassword) créé.")

        # 5. Création de l'Avocat de test 2 (Non approuvé - à valider par l'admin)
        if not User.objects.filter(username="avocat_momo").exists():
            avo_user2 = User.objects.create_user(
                username="avocat_momo",
                email="momo@monjuriste.cm",
                password="lawyerpassword",
                first_name="Alice",
                last_name="Momo",
                role="AVOCAT",
                telephone="655667788"
            )
            profile2 = avo_user2.avocat_profile
            profile2.tarif_horaire = 15000.00
            profile2.cabinet = "Cabinet Momo & Associés"
            profile2.ville = "Yaoundé"
            profile2.annees_experience = 6
            profile2.description = (
                "Spécialiste du droit de la famille et des affaires matrimoniales. Maître Alice Momo propose "
                "ses services pour les conciliations, divorces, successions et gardes d'enfants à Yaoundé."
            )
            profile2.is_approved = False  # Nécessite approbation administrative
            profile2.specialites.add(specialites["Droit de la Famille"])
            profile2.save()
            
            # Ajouter un créneau
            CreneauHoraire.objects.create(avocat=profile2, jour_semaine=1, heure_debut=datetime.time(10, 0), heure_fin=datetime.time(15, 0)) # Mardi
            
            self.stdout.write("Avocat en attente 'avocat_momo' (password: lawyerpassword) créé.")

        self.stdout.write(self.style.SUCCESS("Initialisation terminée avec succès !"))

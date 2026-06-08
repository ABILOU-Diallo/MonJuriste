from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Specialite, ClientProfile, AvocatProfile, CreneauHoraire,
    Conge, DemandeConsultation, RendezVous, Dossier, DocumentDossier,
    Paiement, Note, Notification, EmailCommunication
)

# Custom UserAdmin to show role in admin list
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations de Rôle', {'fields': ('role', 'telephone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations de Rôle', {'fields': ('role', 'telephone')}),
    )

class AvocatProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'cabinet', 'ville', 'annees_experience', 'tarif_horaire', 'is_approved', 'note_moyenne', 'total_avis')
    list_filter = ('is_approved', 'ville', 'specialites')
    search_fields = ('user__last_name', 'user__first_name', 'description')
    actions = ['approve_lawyers']

    def approve_lawyers(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, "Les avocats sélectionnés ont été approuvés.")
    approve_lawyers.short_description = "Approuver les avocats sélectionnés"

class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'adresse')
    search_fields = ('user__last_name', 'user__first_name', 'adresse')

class PaiementAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'client', 'demande', 'montant', 'moyen_paiement', 'statut', 'created_at')
    list_filter = ('statut', 'moyen_paiement', 'created_at')
    search_fields = ('transaction_id', 'client__user__last_name', 'demande__sujet')

class RendezVousAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'avocat', 'date_heure', 'statut')
    list_filter = ('statut', 'date_heure')
    search_fields = ('client__user__last_name', 'avocat__user__last_name', 'motif')

class DossierAdmin(admin.ModelAdmin):
    list_display = ('titre', 'client', 'avocat', 'statut', 'created_at')
    list_filter = ('statut', 'created_at')
    search_fields = ('titre', 'client__user__last_name', 'avocat__user__last_name')

admin.site.register(User, CustomUserAdmin)
admin.site.register(Specialite)
admin.site.register(ClientProfile, ClientProfileAdmin)
admin.site.register(AvocatProfile, AvocatProfileAdmin)
admin.site.register(CreneauHoraire)
admin.site.register(Conge)
admin.site.register(DemandeConsultation)
admin.site.register(RendezVous, RendezVousAdmin)
admin.site.register(Dossier, DossierAdmin)
admin.site.register(DocumentDossier)
admin.site.register(Paiement, PaiementAdmin)
admin.site.register(Note)
admin.site.register(Notification)
admin.site.register(EmailCommunication)

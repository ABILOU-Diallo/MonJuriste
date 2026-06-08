from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # 1. VISITEUR & GENERAL
    path('', views.visitor_index, name='visitor_index'),
    path('register/', views.register, name='register'),
    path('lawyer-register/', views.lawyer_register, name='lawyer_register'),
    path('login/', auth_views.LoginView.as_view(template_name='visitor/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='visitor_index'), name='logout'),
    path('dashboard/redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/<int:pk>/delete/', views.delete_notification, name='delete_notification'),
    path('emails/', views.emails_list, name='emails_list'),
    path('profil/', views.profil_edit, name='profil_edit'),

    # 2. CLIENT
    path('client/dashboard/', views.client_dashboard, name='client_dashboard'),
    path('client/avocats/', views.avocat_list, name='avocat_list'),
    path('client/avocats/<int:pk>/', views.avocat_detail, name='avocat_detail'),
    path('client/avocats/<int:avocat_id>/noter/', views.avocat_noter, name='avocat_noter'),
    path('client/demande/creer/<int:avocat_id>/', views.demande_creer, name='demande_creer'),
    path('client/paiement/<int:demande_id>/', views.paiement_form, name='paiement_form'),
    path('client/paiement/process/<str:transaction_id>/', views.paiement_process, name='paiement_process'),
    path('client/dossiers/', views.dossier_list_client, name='dossier_list_client'),
    path('client/dossiers/<int:pk>/', views.dossier_detail_client, name='dossier_detail_client'),
    path('client/rendezvous/', views.rendezvous_list_client, name='rendezvous_list_client'),
    path('client/rendezvous/<int:pk>/annuler/', views.rendezvous_annuler_client, name='rendezvous_annuler_client'),

    # 3. AVOCAT
    path('avocat/dashboard/', views.avocat_dashboard, name='avocat_dashboard'),
    path('avocat/planning/', views.avocat_planning, name='avocat_planning'),
    path('avocat/planning/creneau/<int:pk>/delete/', views.delete_creneau, name='delete_creneau'),
    path('avocat/planning/conge/<int:pk>/delete/', views.delete_conge, name='delete_conge'),
    path('avocat/rendezvous/', views.avocat_rendezvous, name='avocat_rendezvous'),
    path('avocat/dossiers/', views.avocat_dossiers, name='avocat_dossiers'),
    path('avocat/dossiers/<int:pk>/', views.avocat_dossier_detail, name='avocat_dossier_detail'),
    path('avocat/avis/', views.avocat_notes, name='avocat_notes'),
    path('avocat/paiements/', views.avocat_paiements, name='avocat_paiements'),

    # 5. MESSAGING
    path('messages/', views.conversation_list, name='conversation_list'),
    path('messages/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('messages/<int:conversation_id>/start-call/<str:call_type>/', views.start_call, name='start_call'),
    path('messages/call/<int:call_id>/', views.call_room, name='call_room'),
    path('api/presence/heartbeat/', views.presence_heartbeat, name='presence_heartbeat'),
    path('api/calls/incoming/', views.incoming_calls_api, name='incoming_calls_api'),
    path('messages/start/<int:avocat_id>/', views.start_conversation, name='start_conversation'),

    # 6. CUSTOM ADMIN
    path('admin-custom/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-custom/avocat/<int:avocat_id>/approve/', views.admin_approve_lawyer, name='admin_approve_lawyer'),
    path('admin-custom/utilisateurs/', views.admin_utilisateurs, name='admin_utilisateurs'),
    path('admin-custom/utilisateurs/<int:user_id>/modifier/', views.admin_modifier_utilisateur, name='admin_modifier_utilisateur'),
    path('admin-custom/utilisateurs/<int:user_id>/supprimer/', views.admin_supprimer_utilisateur, name='admin_delete_user'),
    path('admin-custom/notifier/', views.admin_notifier, name='admin_notifier'),
]

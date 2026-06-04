from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin

def role_required(allowed_roles):
    """
    Décorateur pour restreindre l'accès à une vue en fonction des rôles de l'utilisateur.
    allowed_roles peut être une chaîne de caractères simple (ex: 'AVOCAT')
    ou une liste/tuple (ex: ['AVOCAT', 'ADMIN']).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Les superutilisateurs ont accès à tout
            if request.user.is_superuser:
                from .models import ClientProfile, AvocatProfile
                if 'CLIENT' in allowed_roles and not hasattr(request.user, 'client_profile'):
                    ClientProfile.objects.get_or_create(user=request.user)
                if 'AVOCAT' in allowed_roles and not hasattr(request.user, 'avocat_profile'):
                    profile, created = AvocatProfile.objects.get_or_create(user=request.user)
                    if created or not profile.is_approved:
                        profile.is_approved = True
                        profile.save()
                return view_func(request, *args, **kwargs)
                
            # Vérification du rôle
            if request.user.role in allowed_roles:
                # Si c'est un avocat, vérifier qu'il est approuvé par l'admin
                if request.user.role == 'AVOCAT':
                    if hasattr(request.user, 'avocat_profile') and request.user.avocat_profile.is_approved:
                        return view_func(request, *args, **kwargs)
                    else:
                        raise PermissionDenied("Votre compte avocat est en cours de validation par un administrateur.")
                return view_func(request, *args, **kwargs)
                
            raise PermissionDenied("Vous n'avez pas l'autorisation d'accéder à cette page.")
        return _wrapped_view
    return decorator


class RoleRequiredMixin(LoginRequiredMixin):
    """
    Mixin pour les Class-Based Views Django qui vérifie le rôle de l'utilisateur connecté.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        # Vérifier d'abord si l'utilisateur est connecté
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Les superutilisateurs passent outre les vérifications
        if request.user.is_superuser:
            from .models import ClientProfile, AvocatProfile
            roles = self.allowed_roles
            if isinstance(roles, str):
                roles = [roles]
            if 'CLIENT' in roles and not hasattr(request.user, 'client_profile'):
                ClientProfile.objects.get_or_create(user=request.user)
            if 'AVOCAT' in roles and not hasattr(request.user, 'avocat_profile'):
                profile, created = AvocatProfile.objects.get_or_create(user=request.user)
                if created or not profile.is_approved:
                    profile.is_approved = True
                    profile.save()
            return super().dispatch(request, *args, **kwargs)

        roles = self.allowed_roles
        if isinstance(roles, str):
            roles = [roles]

        # Vérifier si l'utilisateur possède l'un des rôles requis
        if request.user.role in roles:
            # Si c'est un avocat, vérifier s'il est approuvé
            if request.user.role == 'AVOCAT':
                if hasattr(request.user, 'avocat_profile') and request.user.avocat_profile.is_approved:
                    return super().dispatch(request, *args, **kwargs)
                else:
                    raise PermissionDenied("Votre compte avocat est en cours de validation par un administrateur.")
            return super().dispatch(request, *args, **kwargs)

        raise PermissionDenied("Vous n'avez pas l'autorisation d'accéder à cette page.")

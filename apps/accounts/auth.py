# type: ignore
from django.utils import timezone
from ninja.security import HttpBearer
from apps.accounts.models import AccessToken


class AccessTokenAuth(HttpBearer):
    def authenticate(self, request, token):
        access_token = (
            AccessToken.objects.select_related("user", "user__company", "user__branch")
            .filter(token=token, status=0)
            .first()
        )
        if access_token is None or access_token.is_expired or access_token.user is None:
            return None

        access_token.last_used_at = timezone.now()
        access_token.save(update_fields=["last_used_at", "updated_at"])

        request.user = access_token.user
        return {
            "token_id": access_token.id,
            "token": access_token.token,
            "user_id": access_token.user_id,
            "company_id": access_token.user.company_id,
            "branch_id": access_token.user.branch_id,
        }


auth_bearer = AccessTokenAuth()

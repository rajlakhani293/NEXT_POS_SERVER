# type: ignore
from datetime import timedelta

from django.utils import timezone
from ninja.security import HttpBearer
from apps.accounts.models import AccessToken


class AccessTokenAuth(HttpBearer):
    TOKEN_TOUCH_INTERVAL = timedelta(minutes=5)

    def authenticate(self, request, token):
        access_token = (
            AccessToken.objects.select_related(
                "user",
                "user__company",
                "user__branch",
                "user__role",
            )
            .filter(
                token=token,
                status=0,
                user__status=0,
                user__company__status=0,
                user__branch__status=0,
            )
            .first()
        )
        if access_token is None or access_token.is_expired or access_token.user is None:
            return None

        now = timezone.now()
        if (
            access_token.last_used_at is None
            or access_token.last_used_at <= now - self.TOKEN_TOUCH_INTERVAL
        ):
            AccessToken.objects.filter(id=access_token.id).update(last_used_at=now)

        request.user = access_token.user
        return {
            "token_id": access_token.id,
            "token": access_token.token,
            "user_id": access_token.user_id,
            "company_id": access_token.user.company_id,
            "branch_id": access_token.user.branch_id,
        }


auth_bearer = AccessTokenAuth()

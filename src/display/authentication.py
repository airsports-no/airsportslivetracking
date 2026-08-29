"""
Custom DRF authentication for Firebase ID tokens, replacing the third-party drf_firebase_auth
package (see .review-notes/codebase_review.md and the approved migration plan for the full
rationale: drf_firebase_auth==1.0.0 - abandoned, last released years ago - hard-pins
firebase-admin<5, which blocks upgrading past protobuf<4 and therefore blocks adding any modern
package (e.g. ortools) that needs protobuf>=4).

This replicates the exact behavior of
drf_firebase_auth.authentication.FirebaseAuthentication.authenticate_credentials, verified
against the installed package's source and this app's specific settings overrides
(FIREBASE_AUTH_EMAIL_VERIFICATION=True; everything else here matches the package's own
defaults: FIREBASE_AUTH_HEADER_PREFIX="JWT", FIREBASE_CHECK_JWT_REVOKED=True,
FIREBASE_CREATE_LOCAL_USER=True, FIREBASE_ATTEMPT_CREATE_WITH_DISPLAY_NAME=True, username
mapped from the Firebase uid) - with one deliberate omission: the original also mirrored
Firebase UID/provider data into two local FirebaseUser/FirebaseUserProvider tables that nothing
in this app's own code ever reads; that bookkeeping is dropped here.

Known pre-existing gap, preserved as-is rather than silently fixed: auto-creating a MyUser here
does not also create a matching Person row, so a brand-new Firebase user's first request that
touches request.user.person (contest creation, team management, etc.) will hit
Person.DoesNotExist. This matched the old package's behavior too - not introduced by this
rewrite.
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from firebase_admin import auth as firebase_auth
from rest_framework import authentication, exceptions

from display.auth_backends import FirebaseMigrationBackend

logger = logging.getLogger(__name__)

User = get_user_model()


class FirebaseTokenAuthentication(authentication.TokenAuthentication):
    """
    Token-based authentication using a Firebase ID token, sent as
    ``Authorization: JWT <token>``.
    """

    keyword = "JWT"

    def authenticate_credentials(self, token):
        try:
            decoded_token = self._decode_token(token)
            firebase_user = self._authenticate_token(decoded_token)
            local_user = self._get_or_create_local_user(firebase_user)
            return (local_user, decoded_token)
        except Exception as e:
            raise exceptions.AuthenticationFailed(e)

    def _decode_token(self, token: str) -> dict:
        FirebaseMigrationBackend()._initialize_firebase()
        try:
            return firebase_auth.verify_id_token(token, check_revoked=True)
        except Exception as e:
            logger.warning(f"Firebase token verification failed: {e}")
            raise

    def _authenticate_token(self, decoded_token: dict):
        uid = decoded_token.get("uid")
        firebase_user = firebase_auth.get_user(uid)
        if not firebase_user.email_verified:
            raise exceptions.AuthenticationFailed(
                "Email address of this user has not been verified."
            )
        return firebase_user

    def _get_firebase_user_email(self, firebase_user) -> str:
        return firebase_user.email if firebase_user.email else firebase_user.provider_data[0].email

    def _get_or_create_local_user(self, firebase_user):
        email = self._get_firebase_user_email(firebase_user)
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                raise exceptions.AuthenticationFailed("User account is not currently active.")
            user.last_login = timezone.now()
            user.save()
            return user
        except User.DoesNotExist:
            pass

        user = User.objects.create_user(username=firebase_user.uid, email=email)
        user.last_login = timezone.now()
        if firebase_user.display_name is not None:
            display_name = firebase_user.display_name.split(" ")
            if len(display_name) == 2:
                user.first_name = display_name[0]
                user.last_name = display_name[1]
        user.save()
        return user

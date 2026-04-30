import logging
import firebase_admin
from firebase_admin import auth, credentials
from django.contrib.auth.backends import ModelBackend
from django.conf import settings

import requests

logger = logging.getLogger(__name__)

class FirebaseMigrationBackend(ModelBackend):
    """
    Custom authentication backend that authenticates against the local Django 
    database and then silently syncs the password to Firebase.
    """

    def _get_firebase_api_key(self):
        # This is the public Web API Key for your Firebase project, now pulled from settings
        return getattr(settings, "FIREBASE_WEB_API_KEY", "")

    def _verify_firebase_password(self, email, password):
        api_key = self._get_firebase_api_key()
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                return True
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    logger.warning(f"[Auth-Migration] Firebase REST API login failed for {email}: {error_msg} (Status: {response.status_code})")
                except Exception:
                    logger.warning(f"[Auth-Migration] Firebase REST API login failed for {email} with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"[Auth-Migration] Error verifying password with Firebase REST API: {e}")
            return False

    def _initialize_firebase(self):
        try:
            firebase_admin.get_app()
        except ValueError:
            # Firebase not initialized, try to initialize it using settings
            firebase_conf = getattr(settings, "DRF_FIREBASE_AUTH", {})
            cert_path = firebase_conf.get("FIREBASE_SERVICE_ACCOUNT_KEY")
            
            if cert_path:
                import os
                # Try absolute path (Docker) first, then relative path (Local)
                paths_to_try = [cert_path, cert_path.lstrip("/"), "secret/airsports-firebase-admin.json"]
                
                cred = None
                for path in paths_to_try:
                    if os.path.exists(path):
                        try:
                            cred = credentials.Certificate(path)
                            logger.info(f"Firebase Admin initialized using key at: {path}")
                            break
                        except Exception as e:
                            logger.error(f"Failed to load Firebase key from {path}: {e}")

                if cred:
                    try:
                        firebase_admin.initialize_app(cred)
                        logger.info("Firebase Admin initialized successfully in FirebaseMigrationBackend")
                    except Exception as e:
                        logger.error(f"Failed to initialize Firebase Admin app: {e}")
                else:
                    logger.error(f"Could not find Firebase Service Account key in any of: {paths_to_try}")
            else:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY not found in settings")

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return super().authenticate(request, username=username, password=password, **kwargs)

        # 1. Attempt to authenticate against Firebase first (PRIMARY AUTH)
        firebase_success = self._verify_firebase_password(username, password)
        
        if firebase_success:
            logger.info(f"[Auth-Migration] User {username} authenticated successfully via FIREBASE.")
            try:
                from display.models import MyUser
                # Use iexact to be case-insensitive and robust
                user = MyUser.objects.filter(email__iexact=username).first()
                
                if not user:
                    # AUTO-PROVISION: If they are in Firebase but not Django, create them.
                    logger.info(f"[Auth-Migration] User {username} not found in Django. Auto-provisioning profile.")
                    user = MyUser.objects.create_user(
                        email=username.lower(),
                        username=username.lower(),  # Pass email as username to satisfy the manager
                        password=None  # Firebase is the source of truth
                    )
                    user.set_unusable_password()
                    user.save()

                if self.user_can_authenticate(user):
                    # Ensure local password is unusable to enforce Firebase
                    if user.has_usable_password():
                        user.set_unusable_password()
                        user.save(update_fields=["password"])
                        logger.info(f"[Auth-Migration] User {username} local password purged (Firebase migrated).")
                    return user
                else:
                    logger.warning(f"[Auth-Migration] User {username} authenticated via Firebase but is inactive in Django.")
                    return None
            except Exception as e:
                logger.error(f"[Auth-Migration] Error during Firebase-success user mapping for {username}: {e}")
                return None

        # 2. If Firebase fails, try local Django auth (LEGACY MIGRATION PATH)
        # Use iexact lookup for legacy auth as well
        from display.models import MyUser
        user = MyUser.objects.filter(email__iexact=username).first()
        if user and user.check_password(password):
            logger.info(f"[Auth-Migration] User {user.email} authenticated successfully via Legacy Django database.")
            
            self._initialize_firebase()
            try:
                try:
                    firebase_user = auth.get_user_by_email(user.email)
                    auth.update_user(
                        firebase_user.uid,
                        password=password
                    )
                    logger.info(f"[Auth-Migration] User {user.email} migrated: Firebase password updated.")
                except auth.UserNotFoundError:
                    auth.create_user(
                        email=user.email,
                        password=password,
                        display_name=f"{user.first_name} {user.last_name}".strip() or None
                    )
                    logger.info(f"[Auth-Migration] User {user.email} migrated: Created new Firebase account.")
                
                # MIGRATION COMPLETE: Remove local password
                user.set_unusable_password()
                user.save(update_fields=["password"])
                logger.info(f"[Auth-Migration] User {user.email} local password PURGED. Future logins will use Firebase.")
                return user
                
            except Exception as e:
                logger.error(f"[Auth-Migration] FAILED to migrate user {user.email} to Firebase: {e}")
                return user # Still return user since Django auth worked
        
        return None

1. Codebase Compatibility
   * Python Version: The project already requires Python >=3.12 (in pyproject.toml), which is the target version for Django 6.0. No issues here.
   * Timezone Handling: Django 5.0 deprecated django.utils.timezone.utc in favor of Python's standard datetime.timezone.utc. The codebase is already using datetime.timezone.utc in over 300 locations, so it is well-positioned for the removal of the Django-specific alias in
     6.0.
   * Removed Meta options: index_together is removed in favor of indexes. I searched the codebase and found no usages of index_together, so this is safe.
   * GIS Admin: GeoModelAdmin and OSMGeoAdmin are deprecated in favor of GISModelAdmin. No usages were found in the codebase.
   * JSONField: The project correctly uses django.db.models.JSONField rather than the removed PostgreSQL-specific field.

  2. Identified Deprecations & Immediate Risks
   * `smart_text` Monkey-patch: In src/live_tracking_map/settings.py (Line 27), there is a monkey-patch: django.utils.encoding.smart_text = smart_str. smart_text was removed in Django 4.0. The fact that this patch exists suggests some older third-party dependencies might
     still be looking for it. You should remove this and update the offending dependencies.
   * `USE_L10N` Setting: In settings.py, USE_L10N = True is used. This setting was deprecated in Django 4.0 and will likely be completely removed or ignored in 6.0.
   * Logout via GET: Django 5.x/6.0 strictly requires POST for LogoutView. Ensure your frontend (React or Django templates) does not trigger logouts via simple <a> tags or GET requests.

  3. Dependency Risks (requirements.txt)
   * `drf-yasg==1.21.11`: High Risk. This library is known to lag behind Django's major releases and often relies on internal Django APIs that change. It is highly recommended to migrate to drf-spectacular before the Django 6.0 upgrade. REMOVED
   * `djangorestframework==3.14.0`: Needs an upgrade to 3.15+ for Django 5.x support, and likely 3.16+ or 3.17 for Django 6.0 compatibility.
   * `django-bootstrap-dynamic-formsets==0.5.0`: This package is quite old (last major update ~2017) and is likely to use removed Django functions (like ugettext or url()). REMOVED
   * `drf-nested-routers==0.93.5`: Will likely need an update to a version that explicitly supports Django 6.0.
   * `django-js-reverse==0.10.2`: Used for URL reversing in JS. Ensure you update to the version that supports Django 6.0 routing.

  Summary of Recommendations
   1. Remove the `smart_text` monkey-patch in settings.py and fix any library that breaks because of it.
   2. Remove `USE_L10N = True` from settings.py.
   3. Plan a migration from `drf-yasg` to `drf-spectacular`, as this is the most likely dependency to block the upgrade. MIGRATED
   4. Update DRF to at least 3.15.x immediately to prepare for the transition.


   To upgrade Django Rest Framework (DRF) to the latest version (v3.15+), the following steps and considerations are required based on your current codebase:

  1. Dependency Updates (requirements.txt)
   * `djangorestframework`: Update to 3.15.2 (or latest). This version is required for official Django 5.0/5.1 support and prepares for Django 6.0.
   * `drf-nested-routers`: Update from 0.93.5 to 0.94.1. Newer versions of DRF and Django have changes in URL routing and path resolution that 0.94.1 handles more robustly.
   * `drf-spectacular`: (Already updated to 0.28.0) - Ensure this is kept current as it is the most active schema generator for newer DRF versions.

  2. Code Compatibility Checks
   * Removal of `rest_framework.compat`: DRF 3.15 removes several internal compatibility shims. I searched the codebase and confirmed you are not using these, so no action is needed here.
   * `UniqueConstraint` vs `unique_together`: DRF 3.15 now automatically generates validators for Django's new UniqueConstraint. Your Contestant model uses the older unique_together style, which remains fully supported and will not break.
   * `DecimalField` Changes: If you were using DecimalField, DRF 3.15 changed how NaN, Infinity, and -Infinity are handled. However, your codebase primarily uses FloatField for coordinates and speeds, so this is not a concern.

  3. Potential Risks
   * `drf-firebase-auth==1.0.0`: This package is relatively old (last updated ~2021). While it likely still works with DRF 3.15, it might use deprecated Django string-encoding functions (like smart_text). Since you have a monkey-patch for smart_text in settings.py, this
     package is the prime suspect.
       * Recommendation: After upgrading DRF, attempt to remove the django.utils.encoding.smart_text = smart_str line from settings.py. If drf-firebase-auth breaks, consider migrating to drf-firebase-token-auth or a similar maintained library.

  4. Recommended Action Plan
   1. Update requirements.txt:
   1     djangorestframework==3.15.2
   2     drf-nested-routers==0.94.1
   2. Remove the monkey-patch in src/live_tracking_map/settings.py:
   1     # Remove this line
   2     django.utils.encoding.smart_text = smart_str
   3. Run the test suite (pytest) to ensure that the authentication flow and nested routing (which are the most "at risk" areas) still function correctly.

  Would you like me to proceed with updating these dependencies and removing the monkey-patch now?


Migrating from drf-firebase-auth (the library currently in your requirements.txt) to drf-firebase-token-auth (or a similar modern alternative like gdmty-drf-firebase-auth) has several implications for your codebase:

  1. Breaking Code Changes (views.py)
  In your src/display/views.py, you have a manual authentication flow in firebase_token_login:

   1 firebase_authenticator = FirebaseAuthentication()
   2 user, decoded_token = firebase_authenticator.authenticate_credentials(token)
  The authenticate_credentials method is specific to the Gary DeSylva implementation of drf-firebase-auth. Most modern Firebase DRF libraries use different internal method names or expect to be called via the standard authenticate(request) flow. You would likely need to
  refactor this view to either use the new library's verification logic or call firebase_admin.auth.verify_id_token directly.

  2. Authorization Header Prefix
   * `drf-firebase-auth` defaults to JWT (e.g., Authorization: JWT <token>).
   * `drf-firebase-token-auth` typically defaults to Bearer (e.g., Authorization: Bearer <token>).
   * Implication: If your mobile or client apps are currently sending JWT, they will fail to authenticate unless you explicitly set FIREBASE_AUTH_HEADER_PREFIX: 'JWT' in your new settings.

  3. User Model & Creation Logic
  Your project uses a custom user model display.MyUser and a linked Person model.
   * Modern libraries often have "auto-create user" features enabled by default.
   * Implication: You must ensure the new library doesn't bypass your Person creation logic. You may need to disable automatic user creation in the library and handle the "get or create" logic yourself to maintain the integrity of the MyUser <-> Person relationship.

  4. Settings Dictionary
  While both libraries use DRF_FIREBASE_AUTH in settings.py, the configuration keys may differ slightly. You would need to map your current settings:

   1 DRF_FIREBASE_AUTH = {
   2     "FIREBASE_SERVICE_ACCOUNT_KEY": "...",
   3     "FIREBASE_AUTH_EMAIL_VERIFICATION": True,
   4 }
  to the new library's expected format (e.g., some libraries expect the service account path as a top-level setting or under a different key).

  5. Benefits (Why migrate?)
   * Django 6.0 Compatibility: The current drf-firebase-auth (v1.0.0) is unmaintained and is the likely reason you need the smart_text = smart_str monkey-patch in settings.py. A modern library will use force_str and be compatible with Django 5.x/6.0 without hacks.
   * Token Revocation: Newer libraries often have better support for checking if a Firebase token has been revoked.

  Recommendation: Instead of a direct "library-for-library" swap, consider whether you can use firebase-admin directly in a simple custom DRF BaseAuthentication class. This would remove the dependency on unmaintained third-party "glue" libraries and give you full control
  over how users and persons are linked.
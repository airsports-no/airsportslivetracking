from django.contrib.staticfiles.storage import ManifestFilesMixin, StaticFilesStorage

try:
    from storages.backends.gcloud import GoogleCloudStorage
except Exception:
    # Fallback for environments where django-storages or google-auth fails to initialize
    class GoogleCloudStorage(object):
        def __init__(self, *args, **kwargs):
            raise RuntimeError("GoogleCloudStorage failed to initialize. Check credentials.")

class ManifestGoogleCloudStorage(ManifestFilesMixin, GoogleCloudStorage):
    """
    Custom storage backend that stores files in Google Cloud Storage
    and handles hashed filenames for cache busting.
    """
    manifest_strict = False

class ManifestLocalStaticFilesStorage(ManifestFilesMixin, StaticFilesStorage):
    """
    Local storage with manifest hashing but non-strict about missing entries.
    Useful during build time.
    """
    manifest_strict = False

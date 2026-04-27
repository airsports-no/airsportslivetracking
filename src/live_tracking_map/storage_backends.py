from django.contrib.staticfiles.storage import ManifestFilesMixin
from storages.backends.gcloud import GoogleCloudStorage

class ManifestGoogleCloudStorage(ManifestFilesMixin, GoogleCloudStorage):
    """
    Custom storage backend that stores files in Google Cloud Storage
    and handles hashed filenames for cache busting.
    """
    pass

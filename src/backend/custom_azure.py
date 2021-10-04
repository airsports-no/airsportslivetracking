from storages.backends.azure_storage import AzureStorage

from live_tracking_map import settings


class AzureMediaStorage(AzureStorage):
    account_name = settings.STORAGE_ACCOUNT_KEY
    account_key = settings.STORAGE_ACCOUNT_SECRET
    azure_container = settings.MEDIA_LOCATION
    expiration_secs = None
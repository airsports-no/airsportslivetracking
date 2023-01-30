AZURE_BACKUP_SUBSCRIPTION_NAME="Airsports subscription"
AZURE_RESOURCE_GROUP="airsports_group"
TARGET_AZURE_RESOURCE_GROUP="airsports2group"
AZURE_BACKUP_SUBSCRIPTION_ID=$(az account list --query="[?name=='$AZURE_BACKUP_SUBSCRIPTION_NAME'].id | [0]" -o tsv)

az account set -s $AZURE_BACKUP_SUBSCRIPTION_ID

AZURE_BACKUP_RESOURCE_GROUP=Velero_Backups
az group create -n $AZURE_BACKUP_RESOURCE_GROUP --location WestUS

AZURE_STORAGE_ACCOUNT_ID="velero$(uuidgen | cut -d '-' -f5 | tr '[A-Z]' '[a-z]')"
az storage account create \
   --name $AZURE_STORAGE_ACCOUNT_ID \
   --resource-group $AZURE_BACKUP_RESOURCE_GROUP \
   --sku Standard_GRS \
   --encryption-services blob \
   --https-only true \
   --kind BlobStorage \
   --access-tier Hot

BLOB_CONTAINER=velero
az storage container create -n $BLOB_CONTAINER --public-access off --account-name $AZURE_STORAGE_ACCOUNT_ID

AZURE_SUBSCRIPTION_ID=`az account list --query '[?isDefault].id' -o tsv`
AZURE_TENANT_ID=`az account list --query '[?isDefault].tenantId' -o tsv`

AZURE_CLIENT_SECRET=`az ad sp create-for-rbac --name "velero" --role "Contributor" --scopes "/subscriptions/$AZURE_SUBSCRIPTION_ID" --query 'password' -o tsv \
--scopes  "/subscriptions/$AZURE_SUBSCRIPTION_ID"`

# $AZURE_CLIENT_SECRET = "kjb.uTML.6KPBF-xL.-xQm-h5BolYF4YsJ"

AZURE_CLIENT_ID=`az ad sp list --display-name "velero" --query '[0].appId' -o tsv`

cat << EOF  > ./credentials-velero
AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID}
AZURE_TENANT_ID=${AZURE_TENANT_ID}
AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET}
AZURE_RESOURCE_GROUP=${AZURE_RESOURCE_GROUP}
AZURE_CLOUD_NAME=AzurePublicCloud
EOF


velero install \
   --provider azure \
   --plugins velero/velero-plugin-for-microsoft-azure:v1.3.0 \
   --bucket $BLOB_CONTAINER \
   --secret-file ./credentials-velero \
   --backup-location-config resourceGroup=$AZURE_BACKUP_RESOURCE_GROUP,storageAccount=$AZURE_STORAGE_ACCOUNT_ID \
   --use-restic

kubectl -n velero get pods
kubectl logs deployment/velero -n velero

velero backup create airsports-initial-backup --default-volumes-to-restic
velero backup describe airsports-initial-backup

# Restore
cat << EOF  > ./credentials-velero
AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID}
AZURE_TENANT_ID=${AZURE_TENANT_ID}
AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET}
AZURE_RESOURCE_GROUP=${TARGET_AZURE_RESOURCE_GROUP}
AZURE_CLOUD_NAME=AzurePublicCloud
EOF

velero install \
   --provider azure \
   --plugins velero/velero-plugin-for-microsoft-azure:v1.3.0 \
   --bucket $BLOB_CONTAINER \
   --secret-file ./credentials-velero \
   --backup-location-config resourceGroup=$AZURE_BACKUP_RESOURCE_GROUP,storageAccount=$AZURE_STORAGE_ACCOUNT_ID \
   --use-restic


velero restore create --from-backup airsports-initial-backup3
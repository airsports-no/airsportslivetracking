# https://pumpingco.de/blog/backup-and-restore-a-kubernetes-cluster-with-state-using-velero/
#
# Prepare variables
TENANT_ID=...
SUBSCRIPTION_ID=...
SOURCE_AKS_RESOURCE_GROUP=MC_...
TARGET_AKS_RESOURCE_GROUP=MC_... # (optional, only needed if you want to migrate)
BACKUP_RESOURCE_GROUP=backups
BACKUP_STORAGE_ACCOUNT_NAME=velero$(uuidgen | cut -d '-' -f5 | tr '[A-Z]' '[a-z]')

# Create Azure Storage Account
az storage account create \
  --name $BACKUP_STORAGE_ACCOUNT_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku Standard_GRS \
  --encryption-services blob \
  --https-only true \
  --kind BlobStorage \
  --access-tier Hot

 # Create Blob Container
 az storage container create \
   --name velero \
   --public-access off \
   --account-name $BACKUP_STORAGE_ACCOUNT_NAME

# Create a Service Principal for RBAC
AZURE_CLIENT_SECRET=`az ad sp create-for-rbac \
  --name "velero" \
  --role "Contributor" \
  --query 'password' \
  -o tsv \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$BACKUP_RESOURCE_GROUP /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$SOURCE_AKS_RESOURCE_GROUP /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$TARGET_AKS_RESOURCE_GROUP`

AZURE_CLIENT_ID=`az ad sp list --display-name "velero" --query '[0].appId' -o tsv`

cat << EOF > ./credentials-velero
AZURE_SUBSCRIPTION_ID=${SUBSCRIPTION_ID}
AZURE_TENANT_ID=${TENANT_ID}
AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET}
AZURE_RESOURCE_GROUP=${SOURCE_AKS_RESOURCE_GROUP}
AZURE_CLOUD_NAME=AzurePublicCloud
EOF



velero install \
  --provider azure \
  --plugins velero/velero-plugin-for-microsoft-azure:v1.2.0 \
  --bucket velero \
  --secret-file ./credentials-velero \
  --backup-location-config resourceGroup=$BACKUP_RESOURCE_GROUP,storageAccount=$BACKUP_STORAGE_ACCOUNT_NAME \
  --snapshot-location-config apiTimeout=5m,resourceGroup=$BACKUP_RESOURCE_GROUP,incremental=true \
  --wait


velero backup create firstbackup

TARGET_AKS_RESOURCE_GROUP=airsports2_group

#Restore
cat << EOF > ./credentials-velero
AZURE_SUBSCRIPTION_ID=${SUBSCRIPTION_ID}
AZURE_TENANT_ID=${TENANT_ID}
AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET}
AZURE_RESOURCE_GROUP=${TARGET_AKS_RESOURCE_GROUP} # <- This changed
AZURE_CLOUD_NAME=AzurePublicCloud
EOF


velero install \
  --provider azure \
  --plugins velero/velero-plugin-for-microsoft-azure:v1.2.0 \
  --bucket velero \
  --secret-file ./credentials-velero \
  --backup-location-config resourceGroup=$BACKUP_RESOURCE_GROUP,storageAccount=$BACKUP_STORAGE_ACCOUNT_NAME \
  --snapshot-location-config apiTimeout=5m,resourceGroup=$BACKUP_RESOURCE_GROUP,incremental=true \
  --wait
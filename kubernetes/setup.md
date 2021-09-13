Create storage account, and under this create a file share using the Azure GUI. Fetch access keys from the storage account-> Access keys
 
> kubectl apply -f kubernetes/namespace-production.yml

> kubectl create -f kubernetes/configmaps/.

> kubectl create -f kubernetes/secrets/. 


Set up the storage class for database storage:

> kubectl apply -f .\kubernetes\storage_classes/retain_azure_disk.yml

Set up all storage

> kubectl apply -f .\kubernetes\storage/.

Get ACR credentials

> az aks get-credentials -g airsports_group -n airsportsacr

Login ACR

> az acr login --name airsportsacr
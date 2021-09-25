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

Fix AKS ACR authentication issue

> az aks update -n airsports -g airsports_group --attach-acr airsportsacr

Get access to a node

> kubectl get nodes -o wide
> kubectl debug node/aks-agentpool-42549294-vmss000000 -it --image=mcr.microsoft.com/aks/fundamental/base-ubuntu:v0.0.11
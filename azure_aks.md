## Push containers ##
Install Azure CLI:
> https://docs.microsoft.com/en-us/cli/azure/install-azure-cli-windows?tabs=azure-cli

Login: 
> az login

Set subscription:
> az account set --subscription 025b77b1-c02b-4961-a548-38caf9cbffcd

Create container registry: 
> az acr create --resource-group airsports_group --name airsportsacr --sku Basic

Log in to container registry: 
> az acr login --name airsportsacr

Fetch the name of the login server: 
> az acr list --resource-group airsports_group --query "[].{acrLoginServer:loginServer}" --output table

Gives the server address
> airsportsacr.azurecr.io

Tag containers with the login address above:
```
docker tag live_tracking_map_tracker_web airsportsacr.azurecr.io/live_tracking_tracker_web:v1
docker tag live_tracking_map_tracker_processor airsportsacr.azurecr.io/live_tracking_tracker_processor:v1
docker tag live_tracking_map_tracker_celery airsportsacr.azurecr.io/live_tracking_tracker_celery:v1
# docker tag live_tracking_map_tracker_beat airsportsacr.azurecr.io/live_tracking_tracker_beat:v1
docker tag live_tracking_map_tracker_daphne airsportsacr.azurecr.io/live_tracking_tracker_daphne:v1
docker tag live_tracking_map_ogn_consumer airsportsacr.azurecr.io/live_tracking_ogn_consumer:v1
docker tag live_tracking_map_opensky_consumer airsportsacr.azurecr.io/live_tracking_opensky_consumer:v1
```
Push all the images:
```
docker push airsportsacr.azurecr.io/live_tracking_tracker_web:v1 
docker push airsportsacr.azurecr.io/live_tracking_tracker_processor:v1
docker push airsportsacr.azurecr.io/live_tracking_tracker_celery:v1
# docker push airsportsacr.azurecr.io/live_tracking_tracker_beat:v1
docker push airsportsacr.azurecr.io/live_tracking_tracker_daphne:v1
docker push airsportsacr.azurecr.io/live_tracking_ogn_consumer:v1
docker push airsportsacr.azurecr.io/live_tracking_opensky_consumer:v1
```
List all images in the ACR:
> az acr repository list --name airsportsacr --output table

Install kubectl inside az:
> az aks install-cli

Connect to existing cluster:
> az aks get-credentials --resource-group airsports_group --name airsports

Get the current nodes:
> kubectl get nodes

Resource capacity
> kubectl resource-capacity -u -p
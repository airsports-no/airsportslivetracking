This requires a service account to be set up. This will provide a secret that can be used for the kubernetes client. This secret must be provided as an environment variable to the application.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: calculator-scheduler
---
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  namespace: default
  name: x20-jobs-sp-role
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["batch", "extensions"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: x20-jobs-sp-rolebinding
  namespace: prod
subjects:
  - kind: ServiceAccount
    # Reference to ServiceAccount kind's `metadata.name`
    name: calculator-scheduler
    # Reference to ServiceAccount kind's `metadata.namespace`
    namespace: default
roleRef:
  kind: ClusterRole
  name: x20-jobs-sp-role
  apiGroup: rbac.authorization.k8s.io
```
Deploy the service account:
```shell
kubectl create -f <path_to_file> --namespace=default
```
This creates the secret.

Current cluster server is:
```
https://airsports-dns-b66fdeca.hcp.northeurope.azmk8s.io:443
```

# Controlling the auto scaler
```shell
az aks update \
  --resource-group airsports_group \
  --name airsports \
  --cluster-autoscaler-profile max-graceful-termination-sec=7200
```
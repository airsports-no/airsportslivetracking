"""
https://medium.com/google-cloud/playing-with-python-kubernetes-api-running-tasks-in-jobs-generated-by-a-pod-in-google-kubernetes-b5048696dfa8

https://stefanopassador.medium.com/launch-kubernetes-job-on-demand-with-python-c0efc5ed4ae4
"""

import datetime
import json
import logging
import os
import time
from copy import deepcopy

import yaml
from kubernetes import client, config
from kubernetes.utils import create_from_dict, FailToCreateError

LOCAL_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImpRUVZjVjlZZGFNQWF4cWlxX1N3MklWVTNKcFRpb3BlYkluMnVDdmJacFUifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6ImNhbGN1bGF0b3Itc2NoZWR1bGVyLXRva2VuLXg3czhtIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQubmFtZSI6ImNhbGN1bGF0b3Itc2NoZWR1bGVyIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQudWlkIjoiODQ2MzEzMGYtYTdkMi00YTMxLTkxY2MtNTA0M2UwM2JkYjgzIiwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6Y2FsY3VsYXRvci1zY2hlZHVsZXIifQ.KM-ZNFk3SO0xtJIr2M5OH2rAVZYJysIBFyVcfqRxkqmXNip05R2gxXNWWcxUXe9TBdLLQWSzCZwXvlsHbECrL9JD1E9HSvFOkMrpY45Rj0NOfYOSUcgUN1XIr2VptnEuHGryRFtX1Dv6P82Kl4068yNMXuap5bmw4su2Z-e13-q-4OZTQM3hwYY6OLZ8s9TbP-mt1RW2mieZA5a2R9XAlTkorvcSPtkaBriTymwPxFaw2sSLgXJtowr4zYrMUOfZkf7396PKNi2jHp-_g7uEhxs2XPDN2AqQIt4SFI-eczVD74UkevL4Hzw-M-cSEdTBTil3LM1hR5kvRN1gxgN5aA"
AKS_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IlFUOVdrdXJ0V0lyRlFqWW9UWEJEbEZDNlNTTS01T0RIbnNhcXdfOWFPS1UifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6ImNhbGN1bGF0b3Itc2NoZWR1bGVyLXRva2VuLXRsaDV0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQubmFtZSI6ImNhbGN1bGF0b3Itc2NoZWR1bGVyIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQudWlkIjoiMTQxYzI4ZTUtYWEwZC00YjYxLWIyNDItMGU3YzhmNDA0OTJjIiwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6Y2FsY3VsYXRvci1zY2hlZHVsZXIifQ.XWG7XJXzUo0YJExgTsMZNF-lzob5UdVbwzCfObxbBTR0B5BR_J5Tf-Xrs-t-XasyR6MvBoqZpZopMhdhiEpyBTGRvckN5SeW51kqq0d0hoJjYmU_FhIPNBmBVmRv1mBarDgkn1kfGegsnieGAR-l0DKfEZp9S-ztd8y59kqyzHdyd4DEf-qcwzOOgxB2f6Kjot2XWW8E9Kl464DV6iDwWqKEirM-YJGUH-MHudVgo1femE2ufLPmOieOtVdxrqUaryKBefl8B3yG3WJOe5zWPN1Lg75Mpp4tXyzbdnt2-HxO5nfoONovlTPWosTaO1u3kMa1Lkxue2MPmdcZs-k43ez6okKPt7RBI18VY66KtBsOeCPRiWsLjd4DMdIxSHki-Sl7ACd9Wx_WYAz_HLv1OtJJWPkE2-ekHUq_AUK5WI8HURMvCjT-KWfijc5_397n5Dj23Y36q_bTMqAUTKiROsdJMAjeTtRBAiD7t99sfZ1_PVKO2lA6EY4oROdaEXzekaGE7CrKYVtLMGxtTVxMLrhmxV41iImUCqttALyTilX4IEDHwJREi2-sXysiTqFg67siTLU4xjp0SjZp6-h3r-lhFxZxB8xDK2sA9GTuiRL2nCPMX53ctLB6pXF9SxiLQwdwL3tLONQqtovuIBCrqSryN1aFXpN5oVxrQej2PFA"

LOCALHOST = "http://localhost:8080"
AKS_HOST = "https://airsports-dns-b66fdeca.hcp.northeurope.azmk8s.io:443"

logger=logging.getLogger(__name__)

class AlreadyExists(Exception):
    pass


class JobCreator:
    def __init__(self):
        self.client = self.create_client()

    def create_client(self):
        config.load_incluster_config()
        configuration = client.Configuration()
        return client.BatchV1Api(client.ApiClient(configuration))
        # return client.ApiClient()
        # configuration = client.Configuration()
        # configuration.api_key["authorization"] = os.getenv("K8S_TOKEN", AKS_TOKEN)
        # configuration.api_key_prefix["authorization"] = "Bearer"
        # # Requires minikube to run with proxy: kubectl proxy --port=8080
        # configuration.host = os.environ.get("K8S_API", AKS_HOST)
        # configuration.ssl_ca_cert = (
        #     "/aks_certificate/ca.crt"  # Hardcoded volume in deployment
        #     # "ca.aks.crt"  # Hardcoded volume in deployment
        # )
        # configuration.client_side_validation = True
        # return client.ApiClient(configuration)

    def get_job_name(self, pk):
        with open("display/kubernetes_calculator/job.yml", "r") as i:
            configuration = yaml.safe_load(i)
        container = configuration["spec"]["template"]["spec"]["containers"][0]
        return f"{container['name']}-{pk}"

    def spawn_calculator_job(self, pk):
        command = ["python3", "calculator_job.py", str(pk)]
        # with open("job.yml", "r") as i:
        with open("display/kubernetes_calculator/job.yml", "r") as i:
            configuration = yaml.safe_load(i)
        print(f"configuration: {configuration}")
        configuration["metadata"]["name"] += f"-{pk}"

        container = configuration["spec"]["template"]["spec"]["containers"][0]
        container["command"] = command
        container["name"] += f"-{pk}"
        yml = yaml.dump(configuration)
        print(yml)
        try:
            api_response = create_from_dict(self.client, configuration, verbose=True)
        except FailToCreateError as e:
            for reason in e.api_exceptions:
                logger.debug(f"Failure reason: {reason.body}")
                body = json.loads(reason.body)
                if body["reason"] == "AlreadyExists":
                    raise AlreadyExists
            raise e
        # api_response = self.client.create_namespaced_job("default", configuration)
        return api_response

    def get_job_completed(self, pk):
        batch_v1 = client.BatchV1Api(self.client)
        api_response = batch_v1.read_namespaced_job_status(
            name=self.get_job_name(pk), namespace="default"
        )
        return (
                api_response.status.succeeded is not None
                or api_response.status.failed is not None
        )

    def delete_calculator(self, pk):
        batch_v1 = client.BatchV1Api(self.client)
        api_response = batch_v1.delete_namespaced_job(
            name=self.get_job_name(pk),
            namespace="default",
            body=client.V1DeleteOptions(
                propagation_policy="Foreground", grace_period_seconds=5
            ),
        )
        start = datetime.datetime.now()
        while start + datetime.timedelta(minutes=1) < datetime.datetime.now():
            if self.get_job_completed(pk):
                break
            time.sleep(5)
        return api_response


if __name__ == "__main__":
    creator = JobCreator()
    creator.spawn_calculator_job(2452)

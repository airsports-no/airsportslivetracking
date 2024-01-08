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

from live_tracking_map import settings

logger = logging.getLogger(__name__)


class AlreadyExists(Exception):
    pass


class JobCreator:
    def __init__(self):
        self.client = self.create_client()

    def create_client(self):
        config.load_incluster_config()
        return client.ApiClient()
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
        container["image"] += f":{settings.BUILD_ID}"
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
        api_response = batch_v1.read_namespaced_job_status(name=self.get_job_name(pk), namespace="default")
        return api_response.status.succeeded is not None or api_response.status.failed is not None

    def delete_calculator(self, pk):
        batch_v1 = client.BatchV1Api(self.client)
        api_response = batch_v1.delete_namespaced_job(
            name=self.get_job_name(pk),
            namespace="default",
            body=client.V1DeleteOptions(propagation_policy="Foreground", grace_period_seconds=5),
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

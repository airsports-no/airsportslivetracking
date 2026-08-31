from __future__ import annotations

import os
import signal
from pathlib import Path

import requests
from django.conf import settings
from kubernetes import client, config
from kubernetes.stream import stream

from display.models.user_uploaded_map import UserUploadedMap


def get_mbtiles_publish_root() -> Path:
    return Path(getattr(settings, "MBTILES_PUBLISH_ROOT", "/tilesets"))


def get_mbtiles_user_subdir() -> str:
    return getattr(settings, "MBTILES_USER_SUBDIR", "user-uploaded")


def get_published_absolute_path(user_map: UserUploadedMap) -> Path:
    relative_path = user_map.published_relative_path or user_map.default_published_relative_path
    return get_mbtiles_publish_root() / relative_path


def get_local_reload_trigger_path() -> Path:
    return get_mbtiles_publish_root() / ".reload-trigger"


def unpublish_user_uploaded_map(user_map: UserUploadedMap, relative_path: str | None = None) -> None:
    if relative_path:
        target = get_mbtiles_publish_root() / relative_path
    elif user_map.published_relative_path:
        target = get_mbtiles_publish_root() / user_map.published_relative_path
    else:
        target = get_published_absolute_path(user_map)
    try:
        target.unlink()
    except FileNotFoundError:
        pass


def request_mbtiles_reload() -> None:
    reload_method = getattr(settings, "MBTILES_RELOAD_METHOD", "noop")
    if reload_method == "noop":
        return None
    if reload_method == "local":
        os.kill(1, signal.SIGHUP)
        return None
    if reload_method != "kubernetes":
        raise RuntimeError(f"Unknown MBTiles reload method: {reload_method}")

    namespace = getattr(settings, "MBTILES_RELOAD_NAMESPACE", "default")
    label_selector = getattr(settings, "MBTILES_RELOAD_POD_LABEL_SELECTOR", "service=mbtiles")

    config.load_incluster_config()
    core_v1_api = client.CoreV1Api()
    pods = core_v1_api.list_namespaced_pod(namespace=namespace, label_selector=label_selector).items
    if not pods:
        raise RuntimeError(f"Could not find mbtiles pod with selector '{label_selector}' in namespace '{namespace}'")

    # Signal every matching pod, not just one: with more than one mbtiles replica, only
    # reloading pods[0] would leave the others silently serving stale tilesets until their
    # own restart. One pod's exec failing shouldn't stop the others from being signaled, so
    # errors are collected and raised together at the end rather than aborting the loop.
    errors = []
    for pod in pods:
        pod_name = pod.metadata.name
        try:
            stream(
                core_v1_api.connect_get_namespaced_pod_exec,
                name=pod_name,
                namespace=namespace,
                command=["/bin/sh", "-c", "kill -HUP 1"],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )
        except Exception as ex:  # noqa: BLE001 - collected below, not swallowed
            errors.append(f"{pod_name}: {ex}")

    if errors:
        raise RuntimeError(f"Failed to reload {len(errors)}/{len(pods)} mbtiles pod(s): {'; '.join(errors)}")
    return None

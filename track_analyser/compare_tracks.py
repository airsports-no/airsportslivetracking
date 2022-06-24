from typing import List

from cartopy.io.img_tiles import OSM

from track_analyser.gps_track import GPSTrack
import numpy as np
import matplotlib.pyplot as plt

from track_analyser.track_comparator import get_track_differences, get_track_differences_time
import scipy.stats as st

def compare_mean_with_confidences(
    truths: List[GPSTrack], tracks: List[GPSTrack], desired_confidence: float, folder: str
):
    compared_to_truth={}
    for truth_index, truth in enumerate(truths):
        for index, track in enumerate(tracks):
            if truth == track:
                continue
            differences = get_track_differences_time(track, truth)
            try:
                compared_to_truth[track.name].append(differences)
            except KeyError:
                compared_to_truth[track.name]=[differences]
    total_confidence =np.zeros((2, len(tracks)))
    total_mean=[]
    for index, track in enumerate(tracks):
        differences=compared_to_truth[track.name]
        total_differences=np.concatenate(differences)
        confidence=st.t.interval(alpha=desired_confidence, df=len(total_differences)-1, loc=np.mean(total_differences), scale=st.sem(total_differences))
        print(confidence)
        mean=np.mean(total_differences, axis=0)
        total_mean.append(mean)
        total_confidence[:, index]=confidence
    fig, ax = plt.subplots()
    plt.title(f"Mean time distance for confidence interval {int(100 * desired_confidence)}%")
    r1 = np.arange(len(tracks))
    plt.ylabel("Time distance (s)")
    plt.bar(
        r1,
        total_mean,
        yerr=total_confidence,
        width=0.5,
        color="blue",
        edgecolor="black",
        capsize=7,
        label="poacee",
    )
    plt.xticks(np.arange(len(tracks)), [item.name for item in tracks], rotation=60)
    plt.savefig(
        f"{folder}/mean_confidence_bar_{int(100 * desired_confidence)}.png",
        dpi=100,
        bbox_inches="tight",
    )
    plt.close()

def compare_maximum_confidences(
    truths: List[GPSTrack], tracks: List[GPSTrack], confidence: float, folder: str
):
    maximum_confidences = np.zeros((len(truths), len(tracks)))
    for truth_index, truth in enumerate(truths):
        for index, track in enumerate(tracks):
            if truth == track:
                continue
            differences = get_track_differences(track, truth)
            maximum_confidences[truth_index, index] = np.amax(
                np.percentile(
                    differences,
                    [100 * (1 - confidence) / 2, 100 * (1 - (1 - confidence) / 2)],
                )
            )
    fig, ax = plt.subplots()
    plt.title(f"Maximum offset for confidence interval {int(100 * confidence)}%")
    r1 = np.arange(len(tracks))
    plt.ylabel("Position offset (m)")
    plt.bar(
        r1,
        np.mean(maximum_confidences, axis=0),
        width=0.5,
        color="blue",
        edgecolor="black",
        capsize=7,
        label="poacee",
    )
    plt.xticks(np.arange(len(tracks)), [item.name for item in tracks], rotation=60)
    plt.savefig(
        f"{folder}/maximum_confidence_{int(100 * confidence)}.png",
        dpi=100,
        bbox_inches="tight",
    )
    plt.close()


def plot_confidence_compared_with_single_logger(
    truth: GPSTrack, comparisons: List[GPSTrack], confidence: float
):
    try:
        comparisons.remove(truth)
    except ValueError:
        pass
    means = np.zeros((len(comparisons)))
    confidences = np.zeros((2, len(comparisons)))
    for index, comparison in enumerate(comparisons):
        differences = get_track_differences(comparison, truth)
        means[index] = np.mean(differences)
        confidences[:, index] = np.percentile(
            differences, [100 * (1 - confidence) / 2, 100 * (1 - (1 - confidence) / 2)]
        )
    fig, ax = plt.subplots()
    plt.title(f"Confidence interval compared to {truth}: {int(100 * confidence)}%")
    r1 = np.arange(len(comparisons))
    plt.ylabel("Position offset (m)")
    plt.bar(
        r1,
        means,
        width=0.5,
        color="blue",
        edgecolor="black",
        yerr=confidences,
        capsize=7,
        label="poacee",
    )
    plt.xticks(
        np.arange(len(comparisons)), [item.name for item in comparisons], rotation=60
    )
    plt.savefig(
        f"confidence_{truth}_{int(100 * confidence)}.png", dpi=100, bbox_inches="tight"
    )
    plt.close()


def plot_scores():
    fig, ax = plt.subplots()
    plt.title("Scores")
    ax.scatter(range(len(scores)), [item[1] for item in scores])
    plt.xticks(np.arange(len(scores)), [item[0] for item in scores], rotation=60)
    plt.savefig(f"scores.png", dpi=100, bbox_inches="tight")
    plt.close()


def plot_difference_compared_to_single(
    truth: GPSTrack, tracks: List[GPSTrack], folder: str
):
    print(f"Truth start: {truth.start_time}")
    fig, ax = plt.subplots()
    for index1 in range(len(tracks)):
        print(f"{tracks[index1]} start: {tracks[index1].start_time} finish: {tracks[index1].finish_time}")
        if tracks[index1] == truth:
            continue
        differences = get_track_differences(tracks[index1], truth)
        plt.plot(differences, label=f"{tracks[index1]}")
    plt.title(f"Compare tracks to {truth}")
    ax.legend()
    plt.savefig(f"{folder}/track_difference_vs_{truth}.png", dpi=100)
    plt.close()


def compare_everything(tracks: List[GPSTrack], filename: str, folder: str):
    start_time = max([track.start_time for track in tracks])
    finish_time = min([track.finish_time for track in tracks])
    means = np.zeros((len(tracks), len(tracks)))
    stddevs = np.zeros((len(tracks), len(tracks)))
    maximum = np.zeros((len(tracks), len(tracks)))
    fig, ax = plt.subplots()
    for index1 in range(len(tracks)):
        for index2 in range(index1 + 1, len(tracks)):
            differences = get_track_differences(
                tracks[index1], tracks[index2], start_time, finish_time
            )
            print(
                f"{tracks[index1]} vs {tracks[index2]}: Min {np.min(differences)}, Mean {np.mean(differences)}, Max {np.max(differences)}, stddev {np.std(differences)}"
            )
            means[index1, index2] = np.mean(differences)
            means[index2, index1] = np.mean(differences)
            stddevs[index1, index2] = np.std(differences)
            stddevs[index2, index1] = np.std(differences)
            maximum[index1, index2] = np.max(differences)
            maximum[index2, index1] = np.max(differences)
            plt.plot(differences, label=f"{tracks[index1]} - {tracks[index2]}")
    plt.title("Compare tracks")
    ax.legend()
    plt.savefig(f"{folder}/{filename}.png", dpi=100)
    plt.close()
    fig, ax = plt.subplots()
    plt.title("Mean errors")
    y, x = np.meshgrid(
        np.linspace(0, len(tracks) - 1, len(tracks)),
        np.linspace(0, len(tracks) - 1, len(tracks)),
    )
    c = ax.pcolormesh(x, y, means)
    cb = fig.colorbar(c, ax=ax)
    cb.set_label("Metres")
    plt.xticks(np.arange(len(tracks)), [str(track) for track in tracks], rotation=60)
    plt.yticks(np.arange(len(tracks)), [str(track) for track in tracks])
    plt.savefig(f"{folder}/{filename}_means.png", dpi=100, bbox_inches="tight")
    plt.close()

    fig, ax = plt.subplots()
    plt.title("Stddev errors")
    y, x = np.meshgrid(
        np.linspace(0, len(tracks) - 1, len(tracks)),
        np.linspace(0, len(tracks) - 1, len(tracks)),
    )
    c = ax.pcolormesh(x, y, stddevs)
    cb = fig.colorbar(c, ax=ax)
    cb.set_label("Metres")
    plt.xticks(np.arange(len(tracks)), [str(track) for track in tracks], rotation=60)
    plt.yticks(np.arange(len(tracks)), [str(track) for track in tracks])
    plt.savefig(f"{folder}/{filename}_stddevs.png", dpi=100, bbox_inches="tight")
    plt.close()

    fig, ax = plt.subplots()
    plt.title("Maximum errors")
    y, x = np.meshgrid(
        np.linspace(0, len(tracks) - 1, len(tracks)),
        np.linspace(0, len(tracks) - 1, len(tracks)),
    )
    c = ax.pcolormesh(x, y, maximum)
    cb = fig.colorbar(c, ax=ax)
    cb.set_label("Metres")
    plt.xticks(np.arange(len(tracks)), [str(track) for track in tracks], rotation=60)
    plt.yticks(np.arange(len(tracks)), [str(track) for track in tracks])
    plt.savefig(f"{folder}/{filename}_maximum.png", dpi=100, bbox_inches="tight")
    plt.close()


colours = ["blue", "green", "red", "yellow"]


def plot_tracks(tracks: List[GPSTrack], filename: str):
    fig, ax = plt.subplots()
    imagery = OSM()
    ax = plt.axes(projection=imagery.crs)
    for index, track in enumerate(tracks):
        track.plot_track_existing_figure(ax, colours[index], track.name)
    ax.add_image(imagery, 11)
    ax.legend()
    plt.savefig(filename, format="png", dpi=600, transparent=True)

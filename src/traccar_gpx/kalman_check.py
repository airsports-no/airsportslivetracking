import datetime
import itertools
import time

from cartopy.io.img_tiles import OSM
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
import pykalman
from dateutil import parser
from typing import List

from pykalman import KalmanFilter

from traccar_gpx.get_gpx import get_data

TIME_STEP = datetime.timedelta(seconds=0.1)


class Position:
    def __init__(self, latitude, longitude, altitude, timestamp: datetime.datetime):
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.timestamp = timestamp


def load_data(start_time, finish_time, device_id):
    return [
        Position(
            item["latitude"],
            item["longitude"],
            item["altitude"],
            parser.parse(item["deviceTime"]),
        )
        for item in get_data(start_time, finish_time, device_id)
    ]


def to_array(positions: List[Position]) -> np.ndarray:
    return np.array([(item.latitude, item.longitude) for item in positions])


def create_observation(position: Position) -> np.ndarray:
    return np.array([position.latitude, position.longitude])


def build_masked(positions: List[Position]):
    masked = []
    values = []
    last_time = positions[0].timestamp
    for position in positions:
        while last_time + TIME_STEP < position.timestamp:
            masked.append((True, True))
            values.append(create_observation(position))
            last_time += TIME_STEP
        masked.append((False, False))
        values.append(create_observation(position))
        last_time += TIME_STEP
    return np.ma.MaskedArray(values, mask=masked)


def smooth_simple(combined_positions):
    # How much confidence do we have in our data ([15/(10^5))
    obs_var = 1
    observation_covariance = np.diag([obs_var, obs_var]) ** 2

    # How much confidence do we have in our predictions
    confidence = 0.55  # 0.55
    transition_covariance = np.diag([confidence, confidence]) ** 2

    # Create the transition matrix
    transition = [[1, 0], [0, 1]]
    measurement = build_masked(combined_positions)

    kf = KalmanFilter(
        initial_state_mean=measurement[0],
        observation_covariance=observation_covariance,
        transition_covariance=transition_covariance,
        transition_matrices=transition,
    )

    kalman_smoothed, state_cov = kf.smooth(measurement)
    return kalman_smoothed


def smooth_with_covariance(combined_positions):
    confidence = 0.55 ** 2  # 0.55

    transition_covariance = np.array(
        [[1, 0, confidence, 0], [0, 1, 0, confidence], [0, 0, 1, 0], [0, 0, 0, 1]]
    )
    transition_matrix = np.array(
        [[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 1]]
    )

    P = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1000, 0], [0, 0, 0, 1000]])

    Q = np.array(
        [
            [0.001, 0, 0.001, 0],
            [0, 0.001, 0, 0.001],
            [0.001, 0, 0, 0],
            [0, 0.001, 0, 0.001],
        ]
    )
    F = np.array(
        [[1, 0, confidence, 0], [0, 1, 0, confidence], [0, 0, 1, 0], [0, 0, 0, 1]]
    )
    B = np.array([(confidence ** 2) / 2, (confidence ** 2) / 2, confidence, confidence])
    H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])

    # How much confidence do we have in our predictions

    # Create the transition matrix
    measurement = build_masked(combined_positions)
    initial_state = np.array([measurement[0, 0], measurement[0, 1], 0, 0])

    kf = KalmanFilter(
        initial_state_mean=initial_state,
        observation_matrices=H,
        # observation_covariance=P,
        # transition_offsets=B,
        transition_covariance=Q,
        transition_matrices=F,
    )

    kalman_smoothed, state_cov = kf.smooth(measurement)
    return kalman_smoothed[:, 0:2]


def smooth_ikalman(combined_positions):
    noise = 1
    pos = 0.000001
    observation_model = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
    observation_noise = np.array(
        ([[pos, 0, 0, 0], [0, pos, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    )
    observation_noise_covariance = np.array([[pos * noise, 0], [0, pos * noise]])

    estimate_covariance = np.eye(4) * 1000 ** 4
    measurements = build_masked(combined_positions)
    initial_state = np.array([measurements[0, 0], measurements[0, 1], 0, 0])

    kf = KalmanFilter(
        initial_state_mean=initial_state,
        observation_matrices=observation_model,

        observation_covariance=observation_noise_covariance,
        # transition_offsets=B,
        transition_covariance=estimate_covariance,
        transition_matrices=observation_noise,
    )

    kalman_smoothed, state_cov = kf.smooth(measurements)
    return kalman_smoothed[:, 0:2]


def smooth(combined_positions, single_positions):
    position = combined_positions[0]
    transition_matrix = np.array(
        [[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 1]]
    )

    observation_matrix = np.array([[1, 0, 0, 0], [0, 0, 1, 0]])
    previous_state_mean = np.array([position.latitude, 0, position.longitude, 0])
    kf = pykalman.KalmanFilter(
        transition_matrices=transition_matrix,
        observation_matrices=observation_matrix,
        initial_state_mean=previous_state_mean,
    )
    single_measurements = build_masked(single_positions)
    measurements = build_masked(combined_positions)
    kf1 = kf.em(measurements, n_iter=5)
    time_before = time.time()
    n_real_time = measurements.shape[0] - 2000

    kf2 = KalmanFilter(
        transition_matrices=transition_matrix,
        observation_matrices=observation_matrix,
        initial_state_mean=previous_state_mean,
        observation_covariance=10 * kf1.observation_covariance,
        em_vars=["transition_covariance", "initial_state_covariance"],
    )

    kf2 = kf2.em(measurements[:-n_real_time, :], n_iter=5)
    # (smoothed_state_means, smoothed_state_covariances) = kf2.smooth(measurements)
    # return smoothed_state_means[:, 0:4:2]

    (filtered_state_means, filtered_state_covariances) = kf2.filter(
        measurements[:-n_real_time, :]
    )

    print("Time to build and train kf2: %s seconds" % (time.time() - time_before))

    x_now = filtered_state_means[1, :]
    P_now = filtered_state_covariances[1, :]
    x_new = np.zeros((n_real_time, filtered_state_means.shape[1]))
    i = 0

    for measurement in measurements[-n_real_time:, :]:
        time_before = time.time()
        (x_now, P_now) = kf2.filter_update(
            filtered_state_mean=x_now,
            filtered_state_covariance=P_now,
            observation=measurement,
        )
        # print("Time to update kf2: %s seconds" % (time.time() - time_before))
        x_new[i, :] = x_now
        i = i + 1

    return x_new[:, 0:4:2]
    # (smoothed_state_means, smoothed_state_covariances) = kf2.smooth(measurements)
    kf3 = KalmanFilter(
        transition_matrices=transition_matrix,
        observation_matrices=observation_matrix,
        initial_state_mean=previous_state_mean,
        observation_covariance=10 * kf2.observation_covariance,
        em_vars=["transition_covariance", "initial_state_covariance"],
    )

    kf3 = kf3.em(measurements, n_iter=5)
    (smoothed_state_means, smoothed_state_covariances) = kf3.smooth(measurements)
    return smoothed_state_means[:, 0:4:2]
    means, covariances = kf.smooth(build_masked(combined_positions))
    return np.array([(item[0], item[2]) for item in means])
    # smooth_means, smooth_covariance=kf.smooth(to_array(combined_positions))
    # previous_state_mean, previous_state_covariance = kf.filter(
    #     create_observation(position)
    # )
    smoothed = [
        Position(
            previous_state_mean[0],
            previous_state_mean[2],
            position.altitude,
            position.timestamp,
        )
    ]
    last_time = position.timestamp
    for position in combined_positions[1:]:
        while last_time + TIME_STEP < position.timestamp:
            previous_state_mean, previous_state_covariance = kf.filter_update(
                previous_state_mean,
                previous_state_covariance,
                observation_matrix=observation_matrix,
            )
            last_time += TIME_STEP
        previous_state_mean, previous_state_covariance = kf.filter_update(
            previous_state_mean,
            previous_state_covariance,
            observation=create_observation(position),
            observation_matrix=observation_matrix,
        )
        smoothed.append(
            Position(
                previous_state_mean[0],
                previous_state_mean[1],
                position.altitude,
                position.timestamp,
            )
        )
    return smoothed


# devices = {"Ottar": 10966, "Stein": 12428}
# start_time = datetime.datetime(2022, 4, 15)  # , tzinfo=datetime.timezone.utc)
# finish_time = datetime.datetime(2022, 4, 16)  # , tzinfo=datetime.timezone.utc)
devices = {"Ottar": 10966}
start_time = datetime.datetime(2022, 4, 14)  # , tzinfo=datetime.timezone.utc)
finish_time = datetime.datetime(2022, 4, 15)  # , tzinfo=datetime.timezone.utc)
tracks = {
    key: load_data(start_time, finish_time, value) for key, value in devices.items()
}

combined = sorted(
    itertools.chain.from_iterable(tracks.values()), key=lambda k: k.timestamp
)
# smoothed = smooth(combined, tracks["Ottar"])
# smoothed = smooth_simple(combined)
# smoothed = smooth_with_covariance(combined)
smoothed = smooth_ikalman(combined)
plt.figure(figsize=(3, 3))
imagery = OSM()
ax = plt.axes(projection=imagery.crs)
line_thickness = 0.05
for name, track in tracks.items():
    ys, xs = to_array(track).T
    plt.plot(xs, ys, transform=ccrs.PlateCarree(), linewidth=line_thickness, label=name)
ys, xs = to_array(combined).T
plt.plot(
    xs, ys, transform=ccrs.PlateCarree(), linewidth=line_thickness, label="combined"
)
ys, xs = smoothed.T
plt.plot(
    xs, ys, transform=ccrs.PlateCarree(), linewidth=line_thickness, label="smoothed"
)
ax.legend()
ax.add_image(imagery, 10)
plt.savefig(f"kalman_track.png", format="png", dpi=4000, transparent=True)

import numpy as np

RESEARCH_ONLY_FEATURES = frozenset({"blink_burst_rate", "stride_impact_force_g"})
NOT_MEASURED = {"tremor_amplitude_mm": "needs 20 Hz sampling; tracker runs at 2 Hz"}


def gait_features(foot_y, dt, angles):
    accel = np.diff(np.diff(foot_y)) / max(dt ** 2, 1e-4) / 9.80665
    return {
        "step_width_ratio": float(np.mean(angles) / 3.0),
        "stride_impact_force_g": float(np.max(np.abs(accel))),
        "knee_flexion_std_deg": float(np.std(angles)),
        "sit_to_stand_speed_m_s": float("nan"),
        "tremor_amplitude_mm": float("nan"),
    }


def face_features(blinks):
    return {"blink_burst_rate": len(blinks) / 2.2}


DEFAULTS = {"sit_to_stand_speed_m_s": 0.0}

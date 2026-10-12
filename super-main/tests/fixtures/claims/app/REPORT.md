# New features

The platform measures the following signals:

- step_width_ratio: ratio of step width to step length.
- stride_impact_force_g: impact force of each stride.
- knee_flexion_variance_deg: variance of knee flexion during swing.
- sit_to_stand_speed_m_s: speed of sitting down.
- tremor_amplitude_mm: micro-tremor of the hands.
- facial_specularity: sweat detection from skin shine.
- blink_burst_rate: blink bursts (research only, not used in scoring).

Implementation lives in src/metrics.py and src/vision/pupil.py.
The screening is reliable and very hard to fake.

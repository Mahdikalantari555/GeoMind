# online-learning-drift Specification

## Purpose
Provides statistical concept drift detection via the Page-Hinkley test and sliding window streaming updates for seasonal remote sensing data streams.

## Requirements

### Requirement: Page-Hinkley Drift Detector
The `geolearn.drift` module SHALL implement the Page-Hinkley statistical test to detect distribution shifts in prediction residuals over sequential observations.

#### Scenario: Detecting seasonal phenological drift
- **WHEN** classification error residuals exhibit a sustained positive drift exceeding the threshold
- **THEN** `PageHinkley.update()` returns `drift_detected=True` and resets cumulative statistics

### Requirement: Sliding Window Streaming Updates
The `geolearn.streaming` module SHALL maintain a fixed-size FIFO sliding window of recent observations, enabling continuous incremental updates without memory growth.

#### Scenario: Streaming window bounds
- **WHEN** incoming streaming observations exceed the maximum window size
- **THEN** oldest samples are evicted and online classifiers are updated with the current window batch

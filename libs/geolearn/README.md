# GeoLearn

Online adaptation and continual learning framework for remote sensing foundation model representations.

## Features

- **Online Classifiers**: Incremental SGD, Passive-Aggressive, and MiniBatch-KMeans adapters.
- **Probability Calibration & Uncertainty**: `IsotonicCalibrator` (isotonic regression with Platt scaling fallback) and normalized Shannon entropy uncertainty quantification powering principled abstention in `PredictionResult`.
- **Feedback-to-Training Pipeline**: Facade-driven incremental training (`TrainingPipeline.run()`) consuming verified candidate memories via `GeoMemory.list_candidate_memories()`.
- **Model Versioning & Snapshot Rollback**: Automatic version tracking with feedback batch tagging and instant rollbacks on feedback revocation.
- **Concept Drift Detection**: Pure NumPy `PageHinkley` test and sliding window streaming updates (`StreamingWindow`).

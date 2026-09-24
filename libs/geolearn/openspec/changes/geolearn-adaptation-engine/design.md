## Context

GeoLearn needs to mature from experimental 0.1.0 stubs to a solid continual adaptation engine. This design implements confidence calibration (#21), facade-driven feedback training with rollback (#15), and Page-Hinkley drift detection (#12).

## Goals / Non-Goals

**Goals:**
- Provide isotonic calibration and Shannon entropy calculations in pure NumPy / SciKit-Learn.
- Wire training through `GeoMemory.list_candidate_memories` and integrate version rollbacks on feedback revocation.
- Provide a lightweight Page-Hinkley drift detector without heavy third-party streaming libraries.
- Remove `phase3-roadmap.md` and document the completed architecture.

**Non-Goals:**
- PyTorch or CUDA dependencies.
- Complex distributed streaming infrastructure.

## Decisions

### Decision 1: Pure NumPy / SciKit-Learn Page-Hinkley
- **Choice**: Implement `PageHinkley` in `geolearn.drift` using running mean and cumulative deviation.
- **Rationale**: Keeps `[river]` dependency truly optional while ensuring baseline drift detection is built into core GeoLearn.

### Decision 2: Snapshot Linking in ModelVersionManager
- **Choice**: Tag model snapshots with the batch of feedback IDs trained in that step.
- **Rationale**: If any feedback ID in a batch is later revoked in GeoMemory, `ModelVersionManager.rollback()` can immediately identify and restore the pre-batch snapshot.

## Risks / Trade-offs

- [Risk] Isotonic calibration on very small sample sizes (<20) can overfit. → Mitigation: Default to Platt scaling / sigmoid smoothing when sample count is below 20.

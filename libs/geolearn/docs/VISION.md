# GeoLearn — Long-Term Architecture & Vision

## 1. Executive Summary

GeoLearn is the **adaptive machine learning and continuous calibration layer** of the GeoFoundation platform. 

While foundation models (e.g. OLMoEarth, Prithvi, Clay) provide generalist representations of planetary surface reflectance, agricultural and environmental conditions vary drastically across regional microclimates, soil compositions, and seasonal regimes. GeoLearn bridges the gap between static global foundation embeddings and hyper-local agronomic truth.

GeoLearn does not train foundation models from scratch. Instead, it turns sparse expert feedback, field observations, and localized verifications into continuously improving, lightweight adapters with rigorous uncertainty quantification and explicit abstention.

---

## 2. Core Architectural Pillars

```
+─────────────────────────────────────────────────────────────────────────────+
|                                 GEOLEARN                                    |
|                                                                             |
|  [Input: Frozen Embeddings + Feedback]                                      |
|                            │                                                |
|                            ▼                                                |
|   ┌─────────────────────────────────────────────────────────────────────┐   |
|   │ 1. Cold-Start Bridge       : Nearest-Neighbor prototype memory      │   |
|   │ 2. Continual Adaptation    : Streaming online classifiers (SGD)     │   |
|   │ 3. Uncertainty & Abstention: Isotonic calibration & Shannon entropy │   |
|   │ 4. Spatiotemporal Drift    : Statistical drift tracking (Page-Hinkley│  |
|   │ 5. Model Versioning        : Rollback safety on feedback revocation │   |
|   └─────────────────────────────────────────────────────────────────────┘   |
|                            │                                                |
|                            ▼                                                |
|  [Output: Calibrated Class Probabilities + Reliable Abstention]             |
+─────────────────────────────────────────────────────────────────────────────+
```

### I. Frugal, Sovereign, Edge-Capable Compute
* **Zero GPU Requirement for Adaptation**: Learning and inference operate entirely on commodity CPU architectures using optimized NumPy, SciKit-Learn, and lightweight C-extensions.
* **Deployable Everywhere**: Models can export to self-contained JSON/NumPy formats (`EdgeLoader`) capable of executing on farm IoT gateways, tractors, and edge drones without heavy deep learning runtimes.

### II. Continuous Online Learning
* **Feedback as the Gradient**: Every verified candidate memory and researcher correction in GeoMemory translates into an immediate, incremental parameter update (`partial_fit`).
* **Non-Destructive Life-Cycle**: Weight updates are partitioned by hierarchical keys `(crop_type, region, subregion)` preventing catastrophic forgetting across crops or geographies.
* **Deterministic Rollback**: Every training cycle snapshots model state in `geolearn.db`, enabling instant rollback if expert feedback is revoked or found erroneous.

### III. Honest Uncertainty & Abstention Over Hallucination
* **Calibrated Probabilities**: Raw model scores are mapped through isotonic calibration curves, ensuring a predicted probability of 80% reflects true empirical accuracy.
* **Abstention as a First-Class Citizen**: When Shannon entropy is high or sample density in embedding space is sparse (<30 samples), GeoLearn outputs an explicit `abstain=True` with actionable reasoning, rather than generating unfounded predictions.

### IV. Temporal Awareness & Concept Drift
* **Seasonal Progression Tracking**: Crop phenology and spectral signatures shift naturally across planting, vegetative, and harvest stages.
* **Automated Drift Detection**: The Page-Hinkley cumulative statistical test monitors classification residue, detecting when changing weather or crop cycles invalidate existing weights and signaling the need for adaptation.

---

## 3. Position in the GeoFoundation Monorepo

GeoFoundation strictly enforces downward architectural dependencies:

```
[Apps & Web SPA]
       │
       ▼
[Gateway Server (geofront_api)]
       │
       ▼
[GeoAgent & Data Engine] ──(Queries predictions & registers tools)──▶ [GeoLearn]
                                                                          │
                                              (Consumes verified memories)│
                                                                          ▼
                                                                     [GeoMemory]
```

* **What GeoLearn Never Does**:
  1. It never performs spatial raster math or energy balance calculations (owned by `data_engine`).
  2. It never stores raw documents, vector indexes, or spatial assets (owned by `geomemory`).
  3. It never runs autonomous multi-step planning or conversation loops (owned by `geoagent`).
  4. It never executes raw SQL against foreign databases (`geomemory.db` or `agent.db`).

---

## 4. Long-Term Evolution Roadmap

1. **Federated & Multi-Tenant Adaptation**: Secure model aggregation allowing regional cooperatives to pool anonymized weight updates without sharing raw farm imagery.
2. **Multi-Task Biophysical Estimators**: Extending beyond categorical stress classification to continuous regression tasks (soil moisture %, yield forecast kg/ha, canopy nitrogen content).
3. **Active Learning Synthesis**: Proactively querying researchers for labels on high-entropy pixels where model certainty is lowest.

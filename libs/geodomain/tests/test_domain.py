"""Unit tests for geodomain library."""

import pytest
from pydantic import BaseModel, ValidationError

from geodomain.identity import EntityRef, GeoURI
from geodomain.labels import (
    LabelDefinition,
    LabelRegistry,
    LabelSet,
)
from geodomain.observation import (
    Observation,
    ObservationKind,
)
from geodomain.temporal import (
    TemporalKind,
    UtcTimestamp,
    utc_now_iso,
    validate_utc_iso8601,
)


class SampleModel(BaseModel):
    uri: GeoURI
    timestamp: UtcTimestamp


def test_entity_ref_roundtrip() -> None:
    ref = EntityRef(type="farm", id="farm_123")
    assert ref.to_uri() == "geo:farm/farm_123"
    assert str(ref) == "geo:farm/farm_123"

    parsed = EntityRef.from_uri("geo:farm/farm_123")
    assert parsed.type == "farm"
    assert parsed.id == "farm_123"
    assert parsed == ref


def test_entity_ref_geouri_types() -> None:
    # GeoURI accepts EntityRef
    ref = EntityRef(type="parcel", id="p_42")
    model = SampleModel(uri=ref, timestamp="2026-05-10T12:00:00Z")  # type: ignore[arg-type]
    assert model.uri == "geo:parcel/p_42"

    # GeoURI non-string/non-EntityRef raises TypeError / ValidationError
    with pytest.raises((ValidationError, TypeError)):
        SampleModel(uri=12345, timestamp="2026-05-10T12:00:00Z")  # type: ignore[arg-type]



def test_entity_ref_invalid_uri() -> None:
    with pytest.raises(ValueError, match="must start with 'geo:'"):
        EntityRef.from_uri("http://example.com")

    with pytest.raises(ValueError, match="Invalid GeoURI format"):
        EntityRef.from_uri("geo:invalid")


def test_geo_uri_pydantic_field() -> None:
    model = SampleModel(
        uri="geo:field/fld_999",  # type: ignore[arg-type]
        timestamp="2026-05-10T12:00:00Z",  # type: ignore[arg-type]
    )
    assert model.uri == "geo:field/fld_999"
    assert model.timestamp == "2026-05-10T12:00:00+00:00"

    with pytest.raises(ValidationError):
        SampleModel(uri="invalid_uri", timestamp="2026-05-10T12:00:00Z")  # type: ignore[arg-type]


def test_temporal_kinds_and_validation() -> None:
    assert TemporalKind.ACQUIRED_AT.value == "acquired_at"
    assert TemporalKind.OBSERVED_AT.value == "observed_at"
    assert TemporalKind.PUBLISHED_AT.value == "published_at"
    assert TemporalKind.INGESTED_AT.value == "ingested_at"
    assert TemporalKind.CREATED_AT.value == "created_at"

    valid = validate_utc_iso8601("2026-06-01T08:30:00Z")
    assert valid == "2026-06-01T08:30:00+00:00"

    # Datetime inputs
    from datetime import datetime, timezone

    dt_naive = datetime(2026, 6, 1, 8, 30)
    assert validate_utc_iso8601(dt_naive) == "2026-06-01T08:30:00+00:00"

    dt_aware = datetime(2026, 6, 1, 8, 30, tzinfo=timezone.utc)
    assert validate_utc_iso8601(dt_aware) == "2026-06-01T08:30:00+00:00"

    now_ts = utc_now_iso()
    assert "+00:00" in now_ts or now_ts.endswith("Z")

    # Invalid cases
    with pytest.raises(ValueError, match="Expected timestamp string"):
        validate_utc_iso8601(12345)

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_utc_iso8601("   ")

    with pytest.raises(ValueError, match="Invalid ISO-8601 timestamp"):
        validate_utc_iso8601("invalid-date")

    with pytest.raises(ValueError, match="Timestamp must include timezone"):
        validate_utc_iso8601("2026-06-01T08:30:00")


def test_observation_model() -> None:
    obs = Observation(
        subject_id="scene_001",
        subject_type="raster_scene",
        metric=ObservationKind.NDVI,
        value=0.72,
        observed_at="2026-07-01T10:00:00Z",
        valid_from="2026-07-01T00:00:00Z",
        valid_to="2026-07-01T23:59:59Z",
        confidence=0.95,
    )
    assert obs.metric == "ndvi"
    assert obs.value == 0.72
    assert obs.entity_ref.to_uri() == "geo:raster_scene/scene_001"
    assert obs.observation_ref.uri == f"geo:observation/{obs.id}"
    assert obs.valid_from is not None
    assert obs.valid_to is not None

    # Invalid bounds on confidence
    with pytest.raises(ValidationError):
        Observation(subject_id="s1", metric="ndvi", value=0.5, confidence=1.5)

    with pytest.raises(ValidationError):
        Observation(subject_id="s1", metric="ndvi", value=0.5, confidence=-0.1)


def test_label_taxonomy_and_registry() -> None:
    lset = LabelRegistry.get("canopy_stress")
    assert lset.name == "canopy_stress"
    assert len(lset.labels) == 4

    assert lset.name_to_id["water_stress"] == 1
    assert lset.id_to_name[1] == "water_stress"

    assert LabelRegistry.validate_label("salinity_stress") is True
    assert LabelRegistry.validate_label(99) is False

    # LabelSet.get edge cases
    assert lset.get("nonexistent") is None
    assert lset.get(999) is None
    assert lset.get(0) is not None
    assert lset.get("healthy_canopy") is not None

    # Unknown set in registry
    with pytest.raises(KeyError, match="not found in LabelRegistry"):
        LabelRegistry.get("unknown_set")

    custom_set = LabelSet(
        name="custom_stress",
        labels=[
            LabelDefinition(name="pest_damage", class_id=0, display_name="Pest Damage"),
        ],
    )
    LabelRegistry.register(custom_set)
    assert LabelRegistry.get("custom_stress").get("pest_damage") is not None


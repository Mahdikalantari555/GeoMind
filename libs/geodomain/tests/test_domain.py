"""Unit tests for geodomain library."""

import pytest
from pydantic import BaseModel, ValidationError

from geodomain.identity import EntityRef, GeoURI
from geodomain.labels import (
    CANOPY_STRESS_TAXONOMY,
    LabelDefinition,
    LabelRegistry,
    LabelSet,
)
from geodomain.observation import (
    Observation,
    ObservationKind,
    ObservationRef,
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

    valid = validate_utc_iso8601("2026-06-01T08:30:00Z")
    assert valid == "2026-06-01T08:30:00+00:00"

    with pytest.raises(ValueError):
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
    )
    assert obs.metric == "ndvi"
    assert obs.value == 0.72
    assert obs.entity_ref.to_uri() == "geo:raster_scene/scene_001"
    assert obs.observation_ref.uri == f"geo:observation/{obs.id}"


def test_label_taxonomy_and_registry() -> None:
    lset = LabelRegistry.get("canopy_stress")
    assert lset.name == "canopy_stress"
    assert len(lset.labels) == 4

    assert lset.name_to_id["water_stress"] == 1
    assert lset.id_to_name[1] == "water_stress"

    assert LabelRegistry.validate_label("salinity_stress") is True
    assert LabelRegistry.validate_label(99) is False

    custom_set = LabelSet(
        name="custom_stress",
        labels=[
            LabelDefinition(name="pest_damage", class_id=0, display_name="Pest Damage"),
        ],
    )
    LabelRegistry.register(custom_set)
    assert LabelRegistry.get("custom_stress").get("pest_damage") is not None

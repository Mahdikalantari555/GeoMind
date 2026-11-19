"""Counterexamples from the fifth QA pass (2026-11-19): METRIC ET science
modules — missing weather data must degrade to "unknown" (NaN), never to
"zero evapotranspiration"; NaN gaps must not poison QC statistics; the
physics fallback must keep the pixel-level aerodynamic resistance.

Each test is red on commit 39a21f6 and green after the fifth-pass fix.
Synthetic data only.
"""
from __future__ import annotations

import numpy as np
import pytest

from data_engine.energy_balance.latent_heat_flux import LatentHeatFlux, LatentHeatFluxConfig
from data_engine.energy_balance.sensible_heat_flux import SensibleHeatFlux, SensibleHeatFluxConfig
from data_engine.et.daily_et import DailyET, DailyETConfig
from data_engine.et.instantaneous_et import create_instantaneous_et
from data_engine.et.quality import ETQuality


class TestMissingReferenceEtIsUnknownNotZero:
    """A NaN ETr/ETo (weather fetch gap) must propagate, not become 0.0."""

    def test_etrf_with_nan_etr_is_nan(self):
        et = create_instantaneous_et()
        le = np.array([300.0, 300.0, 300.0])
        etr = np.array([0.5, np.nan, 0.4])
        out = et.calculate(le, etr_inst=etr)
        assert np.isnan(out["ETrF"][1])
        assert not np.isnan(out["ETrF"][0])

    def test_etof_with_nan_eto_is_nan(self):
        et = create_instantaneous_et()
        le = np.array([300.0, 300.0])
        eto = np.array([np.nan, 0.4])
        out = et.calculate_etof(le, eto)
        assert np.isnan(out[0])

    def test_scale_instantaneous_to_daily_nan_etr_is_nan(self):
        daily = DailyET(DailyETConfig())
        et_inst = np.array([0.2, 0.2])
        etr_inst = np.array([0.4, np.nan])
        etr_daily = np.array([5.0, 5.0])
        out = daily.scale_instantaneous_to_daily(et_inst, etr_inst, etr_daily)
        assert np.isnan(out[1])

    def test_calculate_full_nan_etr_gives_nan_daily_et(self):
        daily = DailyET(DailyETConfig())
        et_inst = np.array([0.2, 0.2, 0.2])
        etr_inst = np.array([0.4, np.nan, 0.3])
        etr_daily = np.array([5.0, 5.0, 5.0])
        out = daily.calculate_full(et_inst, etr_inst, etr_daily)
        assert np.isnan(out["ET_daily"][1])

    def test_calculate_et_from_le_nan_daily_etr_is_nan(self):
        daily = DailyET(DailyETConfig())
        le = np.array([200.0, 200.0])
        etr_daily = np.array([np.nan, 5.0])
        out = daily.calculate_et_from_le(le, etr_daily)
        assert np.isnan(out["ET_daily"][0])

    def test_et_fraction_with_nan_reference_is_nan(self):
        lh = LatentHeatFlux(LatentHeatFluxConfig())
        le = np.array([200.0, 200.0])
        eto = np.array([np.nan, 0.3])
        etr = np.array([0.35, 0.4])
        out = lh.calculate_et_fraction(le, eto=eto, etr=etr)
        assert np.isnan(out["EToF"][0])
        assert not np.isnan(out["ETrF"][0])


class TestTemperatureLambdaFallback:
    """use_temperature_lambda without a temperature array must not crash."""

    def test_no_temperature_falls_back_to_constant(self, caplog):
        et = create_instantaneous_et(use_temperature_lambda=True)
        le = np.full(3, 300.0)
        out = et.calculate_et_rate(le)
        expected = le * 3600.0 / et.latent_heat
        np.testing.assert_allclose(out, expected)
        assert any("temperature" in rec.message.lower() for rec in caplog.records)


class TestQualityNanAwareness:
    """NaN gaps must not poison neighborhood statistics or violation counts."""

    def test_gap_ring_is_not_flagged_as_outlier(self):
        checker = ETQuality()
        arr = np.full((20, 20), 4.0)
        arr[5:8, 5:8] = np.nan  # a hole of unknown ET
        out = checker.check_spatial_consistency(arr)
        flags = out["is_outlier"]
        ring = np.zeros_like(flags, dtype=bool)
        ring[4, 5:8] = True
        ring[8, 5:8] = True
        ring[5:8, 4] = True
        ring[5:8, 8] = True
        assert not (flags & ring).any()

    def test_nan_is_not_counted_as_bounds_violation(self):
        checker = ETQuality()
        arr = np.array([2.0, np.nan, 99.0])
        out = checker.check_physical_bounds(arr)
        assert out["et_violation_count"] == 1  # only the 99 mm/day pixel
        assert out["et_nan_count"] == 1


class TestPhysicsFallbackKeepsPixelwiseRah:
    """The physics fallback must divide by the pixel rah, not its scene mean."""

    def test_h_reflects_spatially_varying_rah(self):
        shf = SensibleHeatFlux(SensibleHeatFluxConfig(use_stability_correction=False))
        n = 32
        rn = np.full(n, 500.0)
        ts_kelvin = np.full(n, 310.0)
        ta_kelvin = np.full(n, 300.0)
        u = np.full(n, 2.0)
        # Roughness varies across pixels → neutral rah varies → H varies.
        z0m = np.linspace(0.01, 0.5, n)
        out = shf.calculate(rn, ts_kelvin, ta_kelvin, u, z0m, dt_a=0.5)
        h = out["H"]
        d = ts_kelvin - ta_kelvin
        rho = out["rho"]
        ratio = h / (rho * 1005.0 * d)  # ≈ 1/rah per pixel
        assert np.nanstd(ratio) > 0.01  # spatial structure preserved


class TestCalibratedPathUsesGivenDT:
    """Calibrated H stays H = dt_a * dT (dt_b is only for the linear form)."""

    def test_calibrated_h_matches_dt_a_times_d(self):
        shf = SensibleHeatFlux(SensibleHeatFluxConfig(use_stability_correction=False))
        n = 16
        ts = np.full(n, 308.0)
        ta = np.full(n, 300.0)
        rn = np.full(n, 600.0)
        u = np.full(n, 2.0)
        z0m = np.full(n, 0.1)
        out = shf.calculate(rn, ts, ta, u, z0m, dt_a=20.0)
        # H = dt_a * dT before bounds; bounds may clip only the extremes here.
        np.testing.assert_allclose(out["H"], 20.0 * (ts - ta))


@pytest.fixture(scope="module", autouse=True)
def _quiet_logging():
    import logging

    logging.getLogger("data_engine").setLevel(logging.ERROR)
    yield
    logging.getLogger("data_engine").setLevel(logging.NOTSET)

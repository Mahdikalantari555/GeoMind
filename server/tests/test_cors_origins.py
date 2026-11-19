from geofront_api.main import DEV_ORIGINS


def test_studio_dev_origin_allowed():
    assert "http://localhost:5174" in DEV_ORIGINS
    assert "http://127.0.0.1:5174" in DEV_ORIGINS

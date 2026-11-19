import pytest
from pydantic import ValidationError
from geofront_api.errors import GeoFrontError
from geofront_api.routers.data import _require_roi_polygon
from geofront_api.routers.providers import catalog
from geofront_api.schemas import SceneSearchRequest, SceneDownloadRequest, RoiCreateRequest


@pytest.mark.parametrize('cls',[SceneSearchRequest, SceneDownloadRequest])
@pytest.mark.parametrize('dates',[('2024-02-30','2024-03-01'),('2024-03-01','2024-02-01')])
def test_invalid_scene_dates(cls, dates):
    extra={'scene_id':'LC-test'} if cls is SceneDownloadRequest else {}
    with pytest.raises(ValidationError): cls(roi={},date_from=dates[0],date_to=dates[1],**extra)


@pytest.mark.parametrize('ring', [[[0,0],[1,1],[1,0],[0,1],[0,0]], [[0,0],[181,0],[0,1],[0,0]]])
def test_reject_invalid_scene_polygon(ring):
    with pytest.raises(GeoFrontError): _require_roi_polygon({'type':'Polygon','coordinates':[ring]})


def test_reject_zero_area_roi(client,open_ws):
    assert client.post('/api/v1/rois',json={'name':'line','coords':[[1,1],[2,2],[3,3]]}).status_code==422


def test_reject_blank_roi_name():
    with pytest.raises(ValidationError): RoiCreateRequest(name='   ',coords=[])


def test_invalid_custom_base_does_not_break_catalog(monkeypatch):
    monkeypatch.setenv('GEOMIND_APPROVED_PROVIDER_BASES','https://[bad')
    assert 'OpenAI' in catalog()


def test_catalog_does_not_publish_credentials_in_configured_url(monkeypatch):
    monkeypatch.setenv('GEOMEMORY_LLM_API_BASE_URL','https://example.test/v1?token=fixture')
    assert 'fixture' not in str(catalog())


def test_empty_band_component_is_not_silently_removed(client,open_ws,tmp_path):
    from pathlib import Path
    root=Path(client.get('/api/v1/workspace').json()['path'])
    (root/'placeholder.tif').touch()
    resp=client.get('/api/v1/data/tiles/0/0/0.png',params={'path':'placeholder.tif','bands':'1,,2'})
    assert resp.status_code==422

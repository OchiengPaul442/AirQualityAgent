import asyncio
import unittest
from unittest.mock import Mock, patch

import requests
from fastapi import HTTPException

from domain.models.schemas import AirQualityQueryRequest
from infrastructure.api.airqo import AirQoService
from infrastructure.api.waqi import WAQIService
from interfaces.rest_api import routes as routes_module
from shared.utils.provider_errors import ProviderServiceError, provider_unavailable_message


class _CacheStub:
    def get_api_response(self, *_args, **_kwargs):
        return None

    def set_api_response(self, *_args, **_kwargs):
        return None


class _ResponseStub:
    def __init__(self, json_data, status_code=200, text=""):
        self._json_data = json_data
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


class TestWAQIService(unittest.TestCase):
    def test_waqi_uses_v2_search_endpoint(self):
        service = WAQIService(api_token="test-token")
        service.cache_service = _CacheStub()  # type: ignore[assignment]

        service.session.get = Mock(
            return_value=_ResponseStub({"status": "ok", "data": [{"uid": 123}]}, 200)
        )

        service.search_stations("kampala")

        called_url = service.session.get.call_args[0][0]
        called_params = service.session.get.call_args[1]["params"]

        self.assertIn("/v2/search/", called_url)
        self.assertEqual(called_params["keyword"], "kampala")
        self.assertEqual(called_params["token"], "test-token")

    def test_waqi_error_is_sanitized(self):
        service = WAQIService(api_token="test-token")
        service.cache_service = _CacheStub()  # type: ignore[assignment]

        service.session.get = Mock(
            return_value=_ResponseStub({"status": "error", "data": "SECRET_PROVIDER_DETAIL"}, 200)
        )

        with self.assertRaises(ProviderServiceError) as ctx:
            service.search_stations("kampala")

        err = ctx.exception
        self.assertIn("Aeris-AQ", err.public_message)
        self.assertNotIn("SECRET_PROVIDER_DETAIL", str(err))


class TestAirQoService(unittest.TestCase):
    def test_airqo_recent_site_uses_documented_endpoint(self):
        service = AirQoService(api_token="test-token")
        service.cache_service = _CacheStub()  # type: ignore[assignment]

        service.session.get = Mock(
            return_value=_ResponseStub(
                {
                    "success": True,
                    "message": "successfully returned the measurements",
                    "meta": {"total": 1, "skip": 0, "limit": 1000, "page": 1, "pages": 1},
                    "measurements": [{"pm2_5": {"value": 12.3}}],
                },
                200,
            )
        )

        service.get_recent_measurements(site_id="site-123", fetch_all=False)

        called_url = service.session.get.call_args[0][0]
        called_params = service.session.get.call_args[1]["params"]

        self.assertIn("/devices/measurements/sites/site-123/recent", called_url)
        self.assertEqual(called_params["token"], "test-token")
        self.assertEqual(called_params["limit"], 1000)
        self.assertEqual(called_params["skip"], 0)

    def test_airqo_sites_summary_paginates_by_skip_limit(self):
        service = AirQoService(api_token="test-token")
        service.cache_service = _CacheStub()  # type: ignore[assignment]

        def _side_effect(url, headers=None, params=None, timeout=None):
            params = params or {}
            skip = int(params.get("skip", 0))
            limit = int(params.get("limit", 2))
            if skip == 0:
                return _ResponseStub(
                    {
                        "success": True,
                        "sites": [{"_id": "s1"}, {"_id": "s2"}],
                        "meta": {"total": 3, "skip": skip, "limit": limit, "page": 1, "pages": 2},
                    }
                )
            return _ResponseStub(
                {
                    "success": True,
                    "sites": [{"_id": "s3"}],
                    "meta": {"total": 3, "skip": skip, "limit": limit, "page": 2, "pages": 2},
                }
            )

        service.session.get = Mock(side_effect=_side_effect)

        resp = service.get_sites_summary(limit=2, fetch_all=True)
        self.assertTrue(resp.get("success"))
        self.assertEqual(len(resp.get("sites", [])), 3)
        self.assertEqual(resp.get("meta", {}).get("pagesFetched"), 2)


class TestNoLeakREST(unittest.TestCase):
    def test_rest_does_not_leak_provider_errors(self):
        req = AirQualityQueryRequest(
            city="Kampala",
            forecast_days=None,
            include_forecast=False,
            timezone="auto",
        )

        with patch("interfaces.rest_api.routes.WAQIService.get_city_feed", side_effect=Exception("WAQI_SECRET")):
            with patch(
                "interfaces.rest_api.routes.AirQoService.get_recent_measurements",
                side_effect=Exception("AIRQO_SECRET"),
            ):
                try:
                    asyncio.run(routes_module.query_air_quality(req, document=None))  # type: ignore[arg-type]
                    self.fail("Expected HTTPException")
                except HTTPException as exc:
                    self.assertEqual(exc.status_code, 404)
                    detail = exc.detail

        detail_dict = detail if isinstance(detail, dict) else {}
        errors = detail_dict.get("errors", {})

        self.assertIn("waqi", errors)
        self.assertIn("airqo", errors)

        self.assertEqual(errors["waqi"], provider_unavailable_message("WAQI"))
        self.assertEqual(errors["airqo"], provider_unavailable_message("AirQo"))
        self.assertNotIn("WAQI_SECRET", str(detail_dict))
        self.assertNotIn("AIRQO_SECRET", str(detail_dict))


if __name__ == "__main__":
    unittest.main()

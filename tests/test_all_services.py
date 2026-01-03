"""
Comprehensive test suite for all services
Tests: AirQo, WAQI, Search, Scraper, Document Scanner, Weather, Redis Cache
"""

import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import get_settings
from src.services.agent_service import AgentService
from src.services.airqo_service import AirQoService
from src.services.cache import get_cache
from src.services.search_service import SearchService
from src.services.waqi_service import WAQIService
from src.services.weather_service import WeatherService
from src.tools.document_scanner import DocumentScanner
from src.tools.robust_scraper import RobustScraper


class TestAirQoService(unittest.TestCase):
    """Test AirQo API integration"""

    def setUp(self):
        self.service = AirQoService()

    @patch("requests.Session.get")
    def test_get_metadata_grids(self, mock_get):
        """Test getting grid metadata"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "message": "Successful Operation",
            "grids": [
                {"_id": "123", "name": "kampala", "admin_level": "city"}
            ]
        }
        mock_get.return_value = mock_response

        result = self.service.get_metadata("grids")
        self.assertTrue(result["success"])
        self.assertIn("grids", result)

    @patch("requests.Session.get")
    def test_get_recent_measurements_by_site(self, mock_get):
        """Test getting recent measurements by site ID"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "measurements": [
                {
                    "pm2_5": {"value": 25.5},
                    "time": "2024-12-30T12:00:00Z",
                    "site_id": "test_site_123"
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.service.get_recent_measurements(site_id="test_site_123")
        self.assertTrue(result["success"])
        self.assertIn("measurements", result)

    @patch("requests.Session.get")
    def test_get_historical_measurements(self, mock_get):
        """Test getting historical measurements"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "measurements": [
                {"pm2_5": {"value": 30.2}, "time": "2024-12-29T10:00:00Z"}
            ]
        }
        mock_get.return_value = mock_response

        start = datetime.now() - timedelta(days=7)
        end = datetime.now()
        result = self.service.get_historical_measurements(
            site_id="test_site_123",
            start_time=start,
            end_time=end,
            frequency="hourly"
        )
        self.assertTrue(result["success"])

    @patch("requests.Session.get")
    def test_get_forecast(self, mock_get):
        """Test getting air quality forecast"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "forecasts": [
                {"pm2_5": 28.5, "time": "2024-12-31T00:00:00+00:00"}
            ]
        }
        mock_get.return_value = mock_response

        result = self.service.get_forecast(site_id="test_site_123", frequency="daily")
        self.assertIn("forecasts", result)


class TestWAQIService(unittest.TestCase):
    """Test WAQI API integration"""

    def setUp(self):
        self.service = WAQIService()

    @patch("requests.Session.get")
    def test_get_city_feed(self, mock_get):
        """Test getting city air quality data"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": {
                "aqi": 55,
                "city": {"name": "London"},
                "iaqi": {"pm25": {"v": 35}}
            }
        }
        mock_get.return_value = mock_response

        result = self.service.get_city_feed("london")
        self.assertEqual(result["status"], "ok")
        self.assertIn("data", result)

    @patch("requests.Session.get")
    def test_get_station_by_coords(self, mock_get):
        """Test getting nearest station by coordinates"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"aqi": 42}
        }
        mock_get.return_value = mock_response

        result = self.service.get_station_by_coords(51.5074, -0.1278)
        self.assertEqual(result["status"], "ok")

    @patch("requests.Session.get")
    def test_search_stations(self, mock_get):
        """Test searching for stations"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "data": [
                {"station": {"name": "London"}, "uid": 123}
            ]
        }
        mock_get.return_value = mock_response

        result = self.service.search_stations("london")
        self.assertEqual(result["status"], "ok")


class TestSearchService(unittest.TestCase):
    """Test DuckDuckGo search service"""

    def setUp(self):
        self.service = SearchService()

    @patch("duckduckgo_search.DDGS.text")
    def test_search(self, mock_search):
        """Test web search functionality"""
        mock_search.return_value = [
            {
                "title": "Test Result",
                "href": "https://example.com",
                "body": "Test description"
            }
        ]

        results = self.service.search("air quality", max_results=5)
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 5)


class TestRobustScraper(unittest.TestCase):
    """Test web scraper"""

    def setUp(self):
        self.scraper = RobustScraper()

    @patch("requests.Session.get")
    def test_scrape_success(self, mock_get):
        """Test successful web scraping"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"""
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Test Heading</h1>
                <p>Test paragraph</p>
                <a href="/link1">Link 1</a>
            </body>
        </html>
        """
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.scraper.scrape("https://example.com")
        self.assertIn("title", result)
        self.assertEqual(result["title"], "Test Page")
        self.assertIn("content", result)

    @patch("requests.Session.get")
    def test_scrape_retry_on_failure(self, mock_get):
        """Test retry mechanism"""
        # Mock a failed request
        mock_get.side_effect = Exception("Network error")

        result = self.scraper.scrape("https://example.com")
        self.assertIn("error", result)
        # HTTPAdapter will retry automatically
        self.assertGreaterEqual(mock_get.call_count, 1)


class TestDocumentScanner(unittest.TestCase):
    """Test document scanning functionality"""

    def setUp(self):
        self.scanner = DocumentScanner()

    def test_scan_text_file(self):
        """Test scanning a CSV file"""
        # Create a temporary test CSV file
        test_content = "name,value\nair quality,good\npm25,15"
        test_file = "test_doc.csv"
        
        with open(test_file, "w") as f:
            f.write(test_content)
        
        try:
            result = self.scanner.scan_file(test_file)
            self.assertIn("content", result)
            self.assertIn("air quality", result["content"].lower())
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_scan_nonexistent_file(self):
        """Test scanning a file that doesn't exist"""
        result = self.scanner.scan_file("nonexistent_file.txt")
        self.assertIn("error", result)


class TestWeatherService(unittest.TestCase):
    """Test weather API service"""

    def setUp(self):
        self.service = WeatherService()

    @patch("requests.get")
    def test_get_current_weather(self, mock_get):
        """Test getting weather data"""
        # Mock two calls: geocoding and weather
        mock_geocoding = MagicMock()
        mock_geocoding.status_code = 200
        mock_geocoding.json.return_value = {
            "results": [{
                "latitude": 51.5074,
                "longitude": -0.1278,
                "name": "London",
                "country": "UK"
            }]
        }
        mock_geocoding.raise_for_status = MagicMock()

        mock_weather = MagicMock()
        mock_weather.status_code = 200
        mock_weather.json.return_value = {
            "current": {
                "temperature_2m": 15.5,
                "apparent_temperature": 14.0,
                "relative_humidity_2m": 70,
                "wind_speed_10m": 12,
                "precipitation": 0.0,
                "weather_code": 2
            },
            "current_units": {
                "temperature_2m": "°C",
                "apparent_temperature": "°C",
                "relative_humidity_2m": "%",
                "wind_speed_10m": "km/h",
                "precipitation": "mm"
            }
        }
        mock_weather.raise_for_status = MagicMock()

        # Return geocoding first, then weather
        mock_get.side_effect = [mock_geocoding, mock_weather]

        result = self.service.get_current_weather("London")
        self.assertIn("location", result)
        self.assertIn("temperature", result)
        self.assertEqual(mock_get.call_count, 2)


class TestCacheService(unittest.TestCase):
    """Test Redis cache functionality"""

    def setUp(self):
        self.cache = get_cache()

    def test_cache_set_get(self):
        """Test setting and getting cache values"""
        self.cache.set("test", "key1", "value1", ttl=300)
        result = self.cache.get("test", "key1")
        
        # Should work with both Redis and in-memory fallback
        self.assertEqual(result, "value1")

    def test_cache_ttl(self):
        """Test cache expiration (if Redis is enabled)"""
        self.cache.set("test", "expire_key", "value", ttl=1)
        
        # Immediate retrieval should work
        result = self.cache.get("test", "expire_key")
        self.assertEqual(result, "value")

    def test_api_response_caching(self):
        """Test API response caching"""
        test_data = {"status": "ok", "data": [1, 2, 3]}
        endpoint = "test/endpoint"
        params = {"city": "london"}
        
        self.cache.set_api_response("test_service", endpoint, params, test_data, 300)
        cached = self.cache.get_api_response("test_service", endpoint, params)
        
        # Should work with both Redis and in-memory
        self.assertEqual(cached, test_data)


class TestAgentService(unittest.TestCase):
    """Test Agent Service functionality"""

    def setUp(self):
        self.service = AgentService()

    def test_is_appreciation_message(self):
        """Test appreciation message detection"""
        # Test positive cases
        appreciation_messages = [
            "thanks",
            "thank you",
            "Thanks a lot",
            "Thank you very much",
            "thx",
            "ty",
            "appreciate it",
            "much appreciated",
            "cheers",
            "awesome",
            "great job",
            "well done",
            "nice work",
            "helpful",
            "thanks on that",
        ]
        
        for msg in appreciation_messages:
            with self.subTest(msg=msg):
                self.assertTrue(self.service._is_appreciation_message(msg), f"Failed to detect: {msg}")

        # Test negative cases
        non_appreciation_messages = [
            "what is the air quality in kampala",
            "tell me about pollution",
            "how to improve air quality",
            "what are the AQI levels",
            "hello",
            "hi there",
            "good morning",
        ]
        
        for msg in non_appreciation_messages:
            with self.subTest(msg=msg):
                self.assertFalse(self.service._is_appreciation_message(msg), f"Incorrectly detected: {msg}")


def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("COMPREHENSIVE SERVICE TEST SUITE")
    print("=" * 70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAirQoService))
    suite.addTests(loader.loadTestsFromTestCase(TestWAQIService))
    suite.addTests(loader.loadTestsFromTestCase(TestSearchService))
    suite.addTests(loader.loadTestsFromTestCase(TestRobustScraper))
    suite.addTests(loader.loadTestsFromTestCase(TestDocumentScanner))
    suite.addTests(loader.loadTestsFromTestCase(TestWeatherService))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheService))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentService))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

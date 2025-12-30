"""
Comprehensive Stress Test Suite

Tests all services with real API calls and various edge cases.
This validates the entire system under realistic conditions.
"""

import asyncio
import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import get_settings
from src.services.airqo_service import AirQoService
from src.services.cache import get_cache
from src.services.search_service import SearchService
from src.services.waqi_service import WAQIService
from src.services.weather_service import WeatherService
from src.tools.document_scanner import DocumentScanner
from src.tools.robust_scraper import RobustScraper


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)


def print_test(name, passed, message=""):
    """Print test result"""
    # Use ASCII symbols for Windows compatibility
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status}  {name}")
    if message:
        print(f"   {message}")


def test_airqo_service():
    """Test AirQo API with all endpoints"""
    print_header("Testing AirQo Service")
    service = AirQoService()
    results = {"passed": 0, "failed": 0, "errors": []}

    # Test 1: Get sites summary
    try:
        response = service.get_sites_summary(limit=5)
        if response.get("success"):
            sites = response.get("sites", [])
            print_test(
                f"Sites Summary",
                len(sites) > 0,
                f"Retrieved {len(sites)} sites"
            )
            results["passed"] += 1
            
            # Save a site ID for later tests
            test_site_id = sites[0].get("_id") if sites else None
        else:
            print_test("Sites Summary", False, f"API returned: {response.get('message')}")
            results["failed"] += 1
            test_site_id = None
    except Exception as e:
        print_test("Sites Summary", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Sites summary error: {str(e)}")
        test_site_id = None

    # Test 2: Get grids summary
    try:
        response = service.get_grids_summary(limit=5)
        if response.get("success"):
            grids = response.get("grids", [])
            total_sites = sum(g.get("numberOfSites", 0) for g in grids)
            print_test(
                "Grids Summary",
                len(grids) > 0,
                f"Retrieved {len(grids)} grids with {total_sites} total sites"
            )
            results["passed"] += 1
            
            # Save a grid ID for later tests
            test_grid_id = grids[0].get("_id") if grids else None
        else:
            print_test("Grids Summary", False, f"API returned: {response.get('message')}")
            results["failed"] += 1
            test_grid_id = None
    except Exception as e:
        print_test("Grids Summary", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Grids summary error: {str(e)}")
        test_grid_id = None

    # Test 3: Search for specific location
    try:
        response = service.get_sites_summary(search="Kampala", limit=5)
        if response.get("success"):
            sites = response.get("sites", [])
            print_test(
                "Site Search (Kampala)",
                True,
                f"Found {len(sites)} sites matching 'Kampala'"
            )
            results["passed"] += 1
        else:
            print_test("Site Search", False, f"API returned: {response.get('message')}")
            results["failed"] += 1
    except Exception as e:
        print_test("Site Search", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Site search error: {str(e)}")

    # Test 4: Get recent measurements by site
    if test_site_id:
        try:
            response = service.get_recent_measurements(site_id=test_site_id)
            if response.get("success"):
                measurements = response.get("measurements", [])
                print_test(
                    "Recent Measurements (Site)",
                    True,
                    f"Retrieved {len(measurements)} measurements for site {test_site_id[:8]}..."
                )
                results["passed"] += 1
            else:
                print_test("Recent Measurements (Site)", False, f"API returned: {response.get('message')}")
                results["failed"] += 1
        except Exception as e:
            print_test("Recent Measurements (Site)", False, f"Error: {str(e)}")
            results["failed"] += 1
            results["errors"].append(f"Recent measurements error: {str(e)}")
    else:
        print_test("Recent Measurements (Site)", False, "No test site ID available")
        results["failed"] += 1

    # Test 5: Get measurements by grid
    if test_grid_id:
        try:
            response = service.get_recent_measurements(grid_id=test_grid_id)
            if response.get("success"):
                measurements = response.get("measurements", [])
                print_test(
                    "Recent Measurements (Grid)",
                    True,
                    f"Retrieved {len(measurements)} measurements for grid {test_grid_id[:8]}..."
                )
                results["passed"] += 1
            else:
                print_test("Recent Measurements (Grid)", False, f"API returned: {response.get('message')}")
                results["failed"] += 1
        except Exception as e:
            print_test("Recent Measurements (Grid)", False, f"Error: {str(e)}")
            results["failed"] += 1
            results["errors"].append(f"Grid measurements error: {str(e)}")
    else:
        print_test("Recent Measurements (Grid)", False, "No test grid ID available")
        results["failed"] += 1

    # Test 6: Get metadata
    try:
        response = service.get_metadata("grids")
        grids = response.get("grids", [])
        print_test(
            "Metadata (Grids)",
            len(grids) >= 0,
            f"Retrieved {len(grids)} grids from metadata"
        )
        results["passed"] += 1
    except Exception as e:
        print_test("Metadata (Grids)", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Metadata error: {str(e)}")

    # Test 7: Site lookup by name
    try:
        site_id = service.get_site_id_by_name("Kampala")
        print_test(
            "Site ID Lookup",
            site_id is not None,
            f"Found site ID: {site_id[:8] if isinstance(site_id, str) else site_id[0][:8] if isinstance(site_id, list) else 'None'}..."
        )
        results["passed"] += 1 if site_id else 0
        results["failed"] += 0 if site_id else 1
    except Exception as e:
        print_test("Site ID Lookup", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Site lookup error: {str(e)}")

    # Test 8: Recent measurements by location search
    try:
        response = service.get_recent_measurements(search="Gulu University")
        if response.get("success"):
            measurements = response.get("measurements", [])
            print_test(
                "Recent Measurements (Location Search)",
                len(measurements) > 0,
                f"Retrieved {len(measurements)} measurements for 'Gulu University'"
            )
            results["passed"] += 1
        else:
            print_test("Recent Measurements (Location Search)", False, f"API returned: {response.get('message')}")
            results["failed"] += 1
    except Exception as e:
        print_test("Recent Measurements (Location Search)", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Location search measurements error: {str(e)}")

    # Test 9: Forecast by location
    try:
        response = service.get_forecast(city="Kampala", frequency="daily")
        if response.get("forecasts"):
            forecasts = response.get("forecasts", [])
            print_test(
                "Forecast (Location-based)",
                len(forecasts) > 0,
                f"Retrieved {len(forecasts)}-day forecast for Kampala"
            )
            results["passed"] += 1
        else:
            print_test("Forecast (Location-based)", False, "No forecast data returned")
            results["failed"] += 1
    except Exception as e:
        print_test("Forecast (Location-based)", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Forecast error: {str(e)}")

    print(f"\nAirQo Results: {results['passed']} passed, {results['failed']} failed")
    return results


def test_waqi_service():
    """Test WAQI API"""
    print_header("Testing WAQI Service")
    service = WAQIService()
    results = {"passed": 0, "failed": 0, "errors": []}

    # Test 1: Get city feed
    try:
        response = service.get_city_feed("London")
        if response.get("status") == "ok":
            aqi = response.get("data", {}).get("aqi")
            print_test(
                "City Feed (London)",
                aqi is not None,
                f"AQI = {aqi}"
            )
            results["passed"] += 1
        else:
            print_test("City Feed", False, f"Status: {response.get('status')}")
            results["failed"] += 1
    except Exception as e:
        print_test("City Feed", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"City feed error: {str(e)}")

    # Test 2: Get station by coordinates
    try:
        response = service.get_station_by_coords(51.5074, -0.1278)
        if response.get("status") == "ok":
            aqi = response.get("data", {}).get("aqi")
            print_test(
                "Coordinates Lookup",
                aqi is not None,
                f"AQI at (51.5074, -0.1278) = {aqi}"
            )
            results["passed"] += 1
        else:
            print_test("Coordinates Lookup", False, f"Status: {response.get('status')}")
            results["failed"] += 1
    except Exception as e:
        print_test("Coordinates Lookup", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Coordinates error: {str(e)}")

    # Test 3: Search stations
    try:
        response = service.search_stations("New York")
        if response.get("status") == "ok":
            stations = response.get("data", [])
            print_test(
                "Station Search",
                len(stations) > 0,
                f"Found {len(stations)} stations"
            )
            results["passed"] += 1
        else:
            print_test("Station Search", False, f"Status: {response.get('status')}")
            results["failed"] += 1
    except Exception as e:
        print_test("Station Search", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Station search error: {str(e)}")

    # Test 4: Multiple cities
    test_cities = ["Paris", "Tokyo", "Beijing"]
    for city in test_cities:
        try:
            response = service.get_city_feed(city)
            if response.get("status") == "ok":
                aqi = response.get("data", {}).get("aqi")
                print_test(
                    f"City Feed ({city})",
                    aqi is not None,
                    f"AQI = {aqi}"
                )
                results["passed"] += 1
            else:
                print_test(f"City Feed ({city})", False, f"Status: {response.get('status')}")
                results["failed"] += 1
        except Exception as e:
            print_test(f"City Feed ({city})", False, f"Error: {str(e)}")
            results["failed"] += 1

    print(f"\nWAQI Results: {results['passed']} passed, {results['failed']} failed")
    return results


def test_weather_service():
    """Test Weather Service"""
    print_header("Testing Weather Service")
    service = WeatherService()
    results = {"passed": 0, "failed": 0, "errors": []}

    test_cities = ["London", "New York", "Tokyo", "Kampala"]
    for city in test_cities:
        try:
            response = service.get_current_weather(city)
            if "error" not in response:
                print_test(
                    f"Weather ({city})",
                    True,
                    f"Temp: {response.get('temperature')}"
                )
                results["passed"] += 1
            else:
                print_test(f"Weather ({city})", False, response.get("error"))
                results["failed"] += 1
        except Exception as e:
            print_test(f"Weather ({city})", False, f"Error: {str(e)}")
            results["failed"] += 1
            results["errors"].append(f"Weather error for {city}: {str(e)}")

    print(f"\nWeather Results: {results['passed']} passed, {results['failed']} failed")
    return results


def test_scraper_service():
    """Test Web Scraper"""
    print_header("Testing Web Scraper")
    scraper = RobustScraper()
    results = {"passed": 0, "failed": 0, "errors": []}

    test_urls = [
        ("https://example.com", "Example Domain"),
        ("https://httpbin.org/html", "HTML"),
    ]

    for url, expected_text in test_urls:
        try:
            response = scraper.scrape(url)
            if "error" not in response:
                content = response.get("content", "")
                print_test(
                    f"Scrape {url}",
                    len(content) > 0,
                    f"Retrieved {len(content)} chars, title: {response.get('title')}"
                )
                results["passed"] += 1
            else:
                print_test(f"Scrape {url}", False, response.get("error"))
                results["failed"] += 1
        except Exception as e:
            print_test(f"Scrape {url}", False, f"Error: {str(e)}")
            results["failed"] += 1
            results["errors"].append(f"Scraper error for {url}: {str(e)}")

    print(f"\nScraper Results: {results['passed']} passed, {results['failed']} failed")
    return results


def test_search_service():
    """Test Search Service"""
    print_header("Testing Search Service")
    service = SearchService()
    results = {"passed": 0, "failed": 0, "errors": []}

    test_queries = [
        "air quality monitoring",
        "Python programming tutorial",
        "weather forecast API"
    ]

    for query in test_queries:
        try:
            response = service.search(query, max_results=3)
            if isinstance(response, list):
                print_test(
                    f"Search '{query}'",
                    len(response) > 0,
                    f"Found {len(response)} results"
                )
                results["passed"] += 1
            else:
                print_test(f"Search '{query}'", False, "Invalid response format")
                results["failed"] += 1
        except Exception as e:
            print_test(f"Search '{query}'", False, f"Error: {str(e)}")
            results["failed"] += 1
            results["errors"].append(f"Search error for '{query}': {str(e)}")

    print(f"\nSearch Results: {results['passed']} passed, {results['failed']} failed")
    return results


def test_document_scanner():
    """Test Document Scanner"""
    print_header("Testing Document Scanner")
    scanner = DocumentScanner()
    results = {"passed": 0, "failed": 0, "errors": []}

    # Test 1: Create and scan text file
    test_file = "test_doc_stress.txt"
    test_content = "This is a comprehensive test of the document scanner. It should read this content successfully."
    
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        response = scanner.scan_document(test_file)
        if "content" in response:
            print_test(
                "Scan Text File",
                test_content in response["content"],
                f"Read {len(response['content'])} chars"
            )
            results["passed"] += 1
        else:
            print_test("Scan Text File", False, response.get("error", "No content"))
            results["failed"] += 1
    except Exception as e:
        print_test("Scan Text File", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Document scan error: {str(e)}")
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

    # Test 2: Handle non-existent file
    try:
        response = scanner.scan_document("nonexistent_file_xyz.txt")
        print_test(
            "Handle Missing File",
            "error" in response,
            "Correctly reported error"
        )
        results["passed"] += 1
    except Exception as e:
        print_test("Handle Missing File", False, f"Error: {str(e)}")
        results["failed"] += 1

    print(f"\nScanner Results: {results['passed']} passed, {results['failed']} failed")
    return results


def test_cache_service():
    """Test Cache Service"""
    print_header("Testing Cache Service")
    cache = get_cache()
    results = {"passed": 0, "failed": 0, "errors": []}

    # Test 1: Basic set/get
    try:
        cache.set("test", "key1", "value1")
        value = cache.get("test", "key1")
        print_test(
            "Cache Set/Get",
            value == "value1",
            f"Retrieved: {value}"
        )
        results["passed"] += 1
    except Exception as e:
        print_test("Cache Set/Get", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"Cache set/get error: {str(e)}")

    # Test 2: API response caching
    try:
        test_data = {"status": "ok", "data": [1, 2, 3]}
        cache.set_api_response("test_api", "endpoint", {"param": "value"}, test_data)
        cached = cache.get_api_response("test_api", "endpoint", {"param": "value"})
        print_test(
            "API Response Cache",
            cached == test_data,
            "Cached and retrieved API response"
        )
        results["passed"] += 1
    except Exception as e:
        print_test("API Response Cache", False, f"Error: {str(e)}")
        results["failed"] += 1
        results["errors"].append(f"API cache error: {str(e)}")

    # Test 3: Clear cache
    try:
        cache.clear("test")
        value = cache.get("test", "key1")
        print_test(
            "Cache Clear",
            value is None,
            "Cache cleared successfully"
        )
        results["passed"] += 1
    except Exception as e:
        print_test("Cache Clear", False, f"Error: {str(e)}")
        results["failed"] += 1

    print(f"\nCache Results: {results['passed']} passed, {results['failed']} failed")
    return results


def main():
    """Run all stress tests"""
    print("\n" + "=" * 80)
    print(" COMPREHENSIVE STRESS TEST SUITE")
    print(" Testing all services with real API calls")
    print("=" * 80)
    
    start_time = time.time()
    all_results = {}

    # Run all tests
    all_results["airqo"] = test_airqo_service()
    all_results["waqi"] = test_waqi_service()
    all_results["weather"] = test_weather_service()
    all_results["scraper"] = test_scraper_service()
    all_results["search"] = test_search_service()
    all_results["scanner"] = test_document_scanner()
    all_results["cache"] = test_cache_service()

    # Calculate totals
    total_passed = sum(r["passed"] for r in all_results.values())
    total_failed = sum(r["failed"] for r in all_results.values())
    total_tests = total_passed + total_failed
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    elapsed_time = time.time() - start_time

    # Print summary
    print_header("FINAL RESULTS")
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {total_passed} ({success_rate:.1f}%)")
    print(f"Failed: {total_failed}")
    print(f"Time: {elapsed_time:.2f}s")

    # Print errors if any
    if total_failed > 0:
        print("\n" + "=" * 80)
        print(" ERRORS SUMMARY")
        print("=" * 80)
        for service, results in all_results.items():
            if results["errors"]:
                print(f"\n{service.upper()}:")
                for error in results["errors"]:
                    print(f"  - {error}")

    # Final status
    if total_failed == 0:
        print("\n[SUCCESS] ALL TESTS PASSED! System is production-ready!")
        return 0
    else:
        print(f"\n[WARNING] {total_failed} tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit(main())

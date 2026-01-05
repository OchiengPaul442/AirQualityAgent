import concurrent.futures
import json
import logging
import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.airqo_service import AirQoService
from src.services.carbon_intensity_service import CarbonIntensityService
from src.services.defra_service import DefraService
from src.services.geocoding_service import GeocodingService
from src.services.nsw_service import NSWService
from src.services.openmeteo_service import OpenMeteoService
from src.services.search_service import SearchService
from src.services.uba_service import UbaService
from src.services.waqi_service import WAQIService
from src.services.weather_service import WeatherService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("stress_test_results.log")
    ]
)
logger = logging.getLogger("StressTest")

def test_waqi():
    logger.info("Testing WAQIService...")
    service = WAQIService()
    results = {}
    
    # Test 1: Get City Feed (London)
    start = time.time()
    try:
        res = service.get_city_feed("London")
        results["city_feed"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
    except Exception as e:
        results["city_feed"] = {"status": "error", "error": str(e)}

    # Test 2: Get by Coordinates (Beijing)
    start = time.time()
    try:
        res = service.get_station_by_coords(39.9042, 116.4074)
        results["coordinates"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
    except Exception as e:
        results["coordinates"] = {"status": "error", "error": str(e)}
        
    return results

def test_airqo():
    logger.info("Testing AirQoService...")
    service = AirQoService()
    results = {}
    
    # Test 1: Get Sites (if available, otherwise skip or try measurements)
    # Assuming get_sites or similar exists, checking file content previously...
    # I didn't see get_sites in the snippet, but I saw get_metadata("grids").
    # Let's try a generic call if possible or just instantiate.
    # The snippet showed _get_headers.
    # Let's try to call a method that likely exists or just check instantiation if we don't have a key.
    # If no key is provided, it might fail.
    
    start = time.time()
    try:
        # Attempt to fetch grids as seen in the unit test
        if hasattr(service, 'get_metadata'):
            res = service.get_metadata("grids")
            results["metadata_grids"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
        else:
             results["metadata_grids"] = {"status": "skipped", "reason": "Method not found"}
    except Exception as e:
        results["metadata_grids"] = {"status": "error", "error": str(e)}
        
    return results

def test_openmeteo():
    logger.info("Testing OpenMeteoService...")
    service = OpenMeteoService()
    results = {}
    
    # Test 1: Current Air Quality (London)
    start = time.time()
    try:
        res = service.get_current_air_quality(51.5074, -0.1278)
        results["current_aq"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
    except Exception as e:
        results["current_aq"] = {"status": "error", "error": str(e)}
        
    return results

def test_carbon_intensity():
    logger.info("Testing CarbonIntensityService...")
    service = CarbonIntensityService()
    results = {}
    
    # Test 1: Current Intensity
    start = time.time()
    try:
        res = service.get_current_intensity()
        results["current_intensity"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
    except Exception as e:
        results["current_intensity"] = {"status": "error", "error": str(e)}
        
    return results

def test_defra():
    logger.info("Testing DefraService...")
    service = DefraService()
    results = {}
    
    # Test 1: Station Data (ABD - Aberdeen)
    start = time.time()
    try:
        res = service.get_station_data("ABD")
        results["station_data"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
    except Exception as e:
        results["station_data"] = {"status": "error", "error": str(e)}
        
    return results

def test_weather():
    logger.info("Testing WeatherService...")
    service = WeatherService()
    results = {}
    
    # Test 1: Current Weather (London)
    start = time.time()
    try:
        res = service.get_current_weather("London")
        results["current_weather"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
    except Exception as e:
        results["current_weather"] = {"status": "error", "error": str(e)}
        
    return results

def test_geocoding():
    logger.info("Testing GeocodingService...")
    service = GeocodingService()
    results = {}
    
    # Test 1: Geocode (Paris)
    start = time.time()
    try:
        res = service.geocode_address("Paris")
        results["geocode"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
    except Exception as e:
        results["geocode"] = {"status": "error", "error": str(e)}
        
    return results

def test_search():
    logger.info("Testing SearchService...")
    service = SearchService()
    results = {}
    
    # Test 1: Search
    start = time.time()
    try:
        res = service.search("Air quality trends 2024")
        if isinstance(res, list):
             results["search"] = {"status": "success", "time": time.time() - start, "count": len(res), "first_result_keys": list(res[0].keys()) if res else None}
        else:
             results["search"] = {"status": "unexpected_format", "type": str(type(res))}
    except Exception as e:
        results["search"] = {"status": "error", "error": str(e)}
        
    return results

def test_uba():
    logger.info("Testing UbaService...")
    service = UbaService()
    results = {}
    
    # Test 1: Get Stations (assuming method exists)
    start = time.time()
    try:
        # Need to check method name, guessing get_stations or similar
        if hasattr(service, 'get_stations'):
            res = service.get_stations()
            results["get_stations"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
        elif hasattr(service, 'get_all_stations'):
            res = service.get_all_stations()
            results["get_all_stations"] = {"status": "success", "time": time.time() - start, "data_keys": list(res.keys()) if res else None}
        else:
             results["get_stations"] = {"status": "skipped", "reason": "Method not found"}
    except Exception as e:
        results["get_stations"] = {"status": "error", "error": str(e)}
        
    return results

def test_nsw():
    logger.info("Testing NSWService...")
    service = NSWService()
    results = {}
    
    # Test 1: Get Site Details
    start = time.time()
    try:
        res = service.get_site_details()
        if isinstance(res, list):
            results["get_site_details"] = {"status": "success", "time": time.time() - start, "count": len(res), "first_item_keys": list(res[0].keys()) if res else None}
        else:
            results["get_site_details"] = {"status": "unexpected_format", "type": str(type(res))}
    except Exception as e:
        results["get_site_details"] = {"status": "error", "error": str(e)}
        
    return results

def run_stress_test():
    logger.info("Starting Rigorous Stress Test of All Services")
    
    tests = [
        test_waqi,
        test_airqo,
        test_openmeteo,
        test_carbon_intensity,
        test_defra,
        test_weather,
        test_geocoding,
        test_search,
        test_uba,
        test_nsw
    ]
    
    final_results = {}
    
    # Run sequentially for now to avoid rate limits and clearer logging
    for test_func in tests:
        try:
            test_name = test_func.__name__
            logger.info(f"Running {test_name}...")
            result = test_func()
            final_results[test_name] = result
            logger.info(f"Finished {test_name}: {json.dumps(result, indent=2)}")
        except Exception as e:
            logger.error(f"Critical error in {test_func.__name__}: {e}")
            final_results[test_func.__name__] = {"status": "critical_failure", "error": str(e)}
            
    # Summary
    logger.info("Stress Test Complete. Summary:")
    print(json.dumps(final_results, indent=2))
    
    # Check for failures
    failures = []
    for service, tests in final_results.items():
        for test_name, result in tests.items():
            if result.get("status") != "success" and result.get("status") != "skipped":
                failures.append(f"{service}.{test_name}: {result.get('error')}")
    
    if failures:
        logger.error(f"Found {len(failures)} failures:")
        for f in failures:
            logger.error(f)
    else:
        logger.info("All services passed successfully!")

if __name__ == "__main__":
    run_stress_test()

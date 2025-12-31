"""
Comprehensive test script for data accuracy validation

Tests all data sources to ensure they correctly report AQI vs concentration values.
"""

import os
import sys

# Set UTF-8 encoding for Windows compatibility
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors="replace")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, errors="replace")

sys.path.insert(0, ".")

from src.services.airqo_service import AirQoService
from src.services.openmeteo_service import OpenMeteoService
from src.services.waqi_service import WAQIService


def test_waqi():
    """Test WAQI service - should return AQI with estimated concentrations"""
    print("=" * 80)
    print("TESTING WAQI SERVICE (Returns AQI, estimates concentration)")
    print("=" * 80)
    
    waqi = WAQIService()
    
    try:
        # Test with a known city
        data = waqi.get_city_feed("kampala")
        
        if data.get("status") == "ok" and "data" in data:
            api_data = data["data"]
            
            print(f"\n✓ City: {api_data['city']['name']}")
            print(f"✓ Overall AQI: {api_data.get('aqi')}")
            
            # Check if conversion happened
            if "pollutant_details" in api_data:
                print("\n✓ Pollutant Details (AQI → Concentration conversion):")
                for pollutant, details in api_data["pollutant_details"].items():
                    if pollutant == "pm25":
                        print(f"  PM2.5:")
                        print(f"    - AQI: {details['aqi']}")
                        print(f"    - Est. Concentration: {details['concentration_ugm3']} µg/m³")
                        print(f"    - Category: {details['category']}")
                
                return True
            else:
                print("\n✗ ERROR: No pollutant_details found in response")
                return False
        else:
            print(f"\n✗ ERROR: {data.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return False


def test_airqo():
    """Test AirQo service - should return concentrations with calculated AQI"""
    print("\n" + "=" * 80)
    print("TESTING AIRQO SERVICE (Returns concentration, calculates AQI)")
    print("=" * 80)
    
    airqo = AirQoService()
    
    try:
        data = airqo.get_recent_measurements(city="Kampala")
        
        if data.get("success") and "measurements" in data:
            meas = data["measurements"][0]
            
            print(f"\n✓ Site: {meas.get('siteDetails', {}).get('location_name', 'N/A')}")
            print(f"✓ Time: {meas.get('time', 'N/A')}")
            
            if "pm2_5" in meas:
                pm25 = meas["pm2_5"]
                print(f"\n✓ PM2.5 Data:")
                print(f"  - Concentration: {pm25.get('value')} µg/m³")
                print(f"  - Calculated AQI: {pm25.get('aqi', 'N/A')}")
                print(f"  - Category: {pm25.get('category', 'N/A')}")
                print(f"  - Data Type: {pm25.get('data_type', 'N/A')}")
                
                # Validate
                if pm25.get('data_type') == 'concentration' and pm25.get('aqi'):
                    return True
                else:
                    print("\n✗ ERROR: Missing AQI calculation or data_type")
                    return False
            else:
                print("\n✗ ERROR: No PM2.5 data found")
                return False
        else:
            print(f"\n✗ ERROR: {data.get('message', 'No measurements found')}")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return False


def test_openmeteo():
    """Test OpenMeteo service - should return concentrations"""
    print("\n" + "=" * 80)
    print("TESTING OPENMETEO SERVICE (Returns concentration)")
    print("=" * 80)
    
    openmeteo = OpenMeteoService()
    
    try:
        # Test with coordinates for Kampala
        data = openmeteo.get_current_air_quality(
            latitude=0.3476,
            longitude=32.5825,
            timezone="Africa/Kampala"
        )
        
        if "current" in data:
            current = data["current"]
            
            print(f"\n✓ Location: Kampala (0.3476, 32.5825)")
            print(f"✓ Time: {current.get('time', 'N/A')}")
            
            # Check for enriched PM2.5 data
            if "pm2_5_concentration" in current:
                print(f"\n✓ PM2.5 Data:")
                print(f"  - Concentration: {current.get('pm2_5_concentration')} µg/m³")
                print(f"  - Calculated AQI: {current.get('pm2_5_aqi', 'N/A')}")
                print(f"  - Category: {current.get('pm2_5_category', 'N/A')}")
                return True
            elif "pm2_5" in current:
                print(f"\n⚠ Warning: PM2.5 found but not enriched")
                print(f"  - Raw value: {current.get('pm2_5')}")
                return False
            else:
                print("\n✗ ERROR: No PM2.5 data found")
                return False
        else:
            print("\n✗ ERROR: No current data found")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return False


def main():
    """Run all tests and report results"""
    print("\n" + "=" * 80)
    print("AIR QUALITY DATA ACCURACY VALIDATION TEST SUITE")
    print("=" * 80)
    print("\nThis test validates that all data sources correctly handle")
    print("the difference between AQI values and concentration values.\n")
    
    results = {
        "WAQI": test_waqi(),
        "AirQo": test_airqo(),
        "OpenMeteo": test_openmeteo()
    }
    
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for service, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{service:15} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL TESTS PASSED - Data accuracy is validated!")
    else:
        print("✗ SOME TESTS FAILED - Please review the errors above")
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

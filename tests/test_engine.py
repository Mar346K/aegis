import aegis._engine

def run_test():
    print("--- Initiating Aegis Engine Test ---")
    
    # Initialize the Rust engine once
    engine = aegis._engine.AegisEngine()

    # Test 1: Clean Payload
    clean_data = b"GET /index.html HTTP/1.1\r\nHost: example.com\r\n\r\n"
    is_dropped_1 = engine.scan_payload(clean_data)
    print(f"Test 1 (Clean Data) -> Drop Packet? {is_dropped_1}")

    # Test 2: Malicious Payload (Fake AWS Key)
    dirty_data = b"POST /api/v1/upload HTTP/1.1\r\nAuthorization: AKIAIOSFODNN7EXAMPLE\r\n\r\n"
    is_dropped_2 = engine.scan_payload(dirty_data)
    print(f"Test 2 (AWS Key)    -> Drop Packet? {is_dropped_2}")

if __name__ == "__main__":
    run_test()
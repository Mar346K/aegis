import asyncio
from aegis.proxy import handle_client

async def run_integration_tests():
    print("=========================================")
    print("  INITIATING PROXY INTEGRATION TESTS")
    print("=========================================")
    
    # 1. Start the Aegis proxy in the background for testing
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8080)
    await asyncio.sleep(0.1) # Give the socket a microsecond to bind

    try:
        # ---------------------------------------------------------
        # TEST 1: The Clean Request
        # ---------------------------------------------------------
        print("[*] Running Test 1: Simulating clean outbound traffic...")
        reader, writer = await asyncio.open_connection('127.0.0.1', 8080)
        
        # Send a standard HTTP GET request
        clean_request = b"GET /get HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n"
        writer.write(clean_request)
        await writer.drain()
        
        response = await reader.read(4096)
        if b"200 OK" in response:
            print("  -> [PASS] Clean traffic successfully routed and returned.")
        else:
            print("  -> [FAIL] Clean traffic was dropped or malformed.")
        writer.close()

        # ---------------------------------------------------------
        # TEST 2: The Exfiltration Attempt
        # ---------------------------------------------------------
        print("\n[*] Running Test 2: Simulating Data Exfiltration (AWS Key)...")
        reader2, writer2 = await asyncio.open_connection('127.0.0.1', 8080)
        
        # Send an HTTP request loaded with a fake AWS secret
        dirty_request = b"POST /post HTTP/1.1\r\nHost: httpbin.org\r\nAuthorization: AKIAIOSFODNN7EXAMPLE\r\n\r\n"
        writer2.write(dirty_request)
        await writer2.drain()
        
        response2 = await reader2.read(4096)
        if b"403 Forbidden" in response2:
            print("  -> [PASS] Zero-Trust policy enforced. Connection violently severed.")
        else:
            print("  -> [FAIL] Secret leaked to the internet!")
        writer2.close()

    finally:
        # 3. Graceful test teardown
        server.close()
        await server.wait_closed()
        print("=========================================")
        print("  TESTS COMPLETE")
        print("=========================================")

if __name__ == "__main__":
    # Silence the standard proxy print statements to keep test output clean
    import sys, os
    sys.stdout = open(os.devnull, 'w') if not sys.stdout.isatty() else sys.stdout
    
    asyncio.run(run_integration_tests())
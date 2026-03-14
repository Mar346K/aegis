import asyncio
from aegis.proxy import handle_client

async def main():
    # Bind the proxy to localhost on port 8080
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8080)
    addr = server.sockets[0].getsockname()
    
    print("=========================================")
    print("      AEGIS ZERO-TRUST SIDECAR V1        ")
    print("=========================================")
    print(f"[*] Proxy running and listening on {addr}")
    print(f"[*] Rust Heuristic Engine: ONLINE")
    print("=========================================\n")
    
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Aegis shutting down gracefully.")
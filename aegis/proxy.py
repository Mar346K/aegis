import asyncio
import re
import aegis._engine

# Initialize the Rust engine ONCE for the entire application.
# This prevents memory overhead and shares the Aho-Corasick state machine.
ENGINE = aegis._engine.AegisEngine()

async def handle_client(local_reader, local_writer):
    client_addr = local_writer.get_extra_info('peername')
    print(f"[+] New connection intercepted from {client_addr}")

    remote_writer = None
    try:
        # 1. Read the initial outbound request chunk (Preventing OOM)
        data = await local_reader.read(8192)
        if not data:
            return

        # 2. The Bridge: Pass to Rust Engine for Zero-Copy evaluation
        if ENGINE.scan_payload(data):
            print(f"[!] EXFILTRATION DETECTED from {client_addr}! Violently terminating.")
            # Chapter 4: Violent Termination (403 Forbidden)
            local_writer.write(b"HTTP/1.1 403 Forbidden\r\nX-Aegis-Enforcement: Blocked\r\n\r\n")
            await local_writer.drain()
            return

        # 3. If clean, parse the destination from the HTTP headers
        host_match = re.search(b"Host: ([^\r\n:]+)", data)
        if not host_match:
            print("[-] Malformed request, dropping.")
            return
        
        host = host_match.group(1).decode('utf-8')
        port = 80 # Defaulting to plaintext HTTP for our V1 MVP
        print(f"[>] Routing clean traffic to {host}:{port}")

        # 4. Open connection to the external destination
        remote_reader, remote_writer = await asyncio.open_connection(host, port)
        
        # Forward the initial clean payload
        remote_writer.write(data)
        await remote_writer.drain()

        # 5. Set up asynchronous bidirectional piping
        async def forward(src, dst, is_outbound=False):
            while True:
                try:
                    chunk = await src.read(8192)
                    if not chunk:
                        break
                    
                    # Scan subsequent outbound chunks mid-stream
                    if is_outbound and ENGINE.scan_payload(chunk):
                        print("[!] EXFILTRATION DETECTED mid-stream! Severing.")
                        break
                        
                    dst.write(chunk)
                    await dst.drain()
                except ConnectionResetError:
                    break

        # Run both data pipes concurrently without blocking the main loop
        await asyncio.gather(
            forward(local_reader, remote_writer, is_outbound=True),
            forward(remote_reader, local_writer, is_outbound=False)
        )

    except Exception as e:
        pass # Silently drop generic socket errors for proxy stability
    finally:
        # Chapter 4: Graceful Teardown
        local_writer.close()
        if remote_writer:
            remote_writer.close()
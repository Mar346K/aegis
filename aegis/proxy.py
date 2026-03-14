import asyncio
import re
import aegis._engine
from aegis.telemetry import log_exfiltration_attempt

# Initialize the Rust engine ONCE for the entire application.
ENGINE = aegis._engine.AegisEngine()

async def handle_client(local_reader, local_writer):
    client_addr = local_writer.get_extra_info('peername')
    print(f"[+] New connection intercepted from {client_addr}")

    remote_writer = None
    try:
        # 1. Read the initial outbound request chunk
        data = await local_reader.read(8192)
        if not data:
            return

        # 2. The Bridge: Pass to Rust Engine
        if ENGINE.scan_payload(data):
            print(f"[!] EXFILTRATION DETECTED from {client_addr}! Violently terminating.")
            log_exfiltration_attempt(client_addr) # AUDIT LOG FIRED
            local_writer.write(b"HTTP/1.1 403 Forbidden\r\nX-Aegis-Enforcement: Blocked\r\n\r\n")
            await local_writer.drain()
            return

        # 3. If clean, parse the destination
        host_match = re.search(b"Host: ([^\r\n:]+)", data)
        if not host_match:
            print("[-] Malformed request, dropping.")
            return
        
        host = host_match.group(1).decode('utf-8')
        port = 80 
        print(f"[>] Routing clean traffic to {host}:{port}")

        # 4. Open connection to the external destination
        remote_reader, remote_writer = await asyncio.open_connection(host, port)
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
                        log_exfiltration_attempt(client_addr, host) # AUDIT LOG FIRED
                        break
                        
                    dst.write(chunk)
                    await dst.drain()
                except ConnectionResetError:
                    break

        await asyncio.gather(
            forward(local_reader, remote_writer, is_outbound=True),
            forward(remote_reader, local_writer, is_outbound=False)
        )

    except Exception as e:
        pass 
    finally:
        local_writer.close()
        if remote_writer:
            remote_writer.close()
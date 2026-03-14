# Aegis: Architecture & System Design

**Aegis** is a zero-trust network sidecar acting as a local egress proxy. Its primary directive is Data Exfiltration Prevention—intercepting outbound traffic and asynchronously dropping packets if heuristic scanning detects plaintext API keys or secrets.

To achieve high concurrency without sacrificing computational speed, Aegis utilizes a Polyglot Architecture: Python (`asyncio`) for I/O-bound proxy routing, and Rust (via `PyO3`) for CPU-bound heuristic evaluation.

---

## Chapter 1: The Intercept (The Egress Proxy Layer)

The objective of the Intercept layer is to act as a highly concurrent, memory-safe local chokepoint. Every outbound HTTP/TCP request from the local machine (or targeted application) is routed through this Python daemon before reaching the wider internet.

### 1.1 The Local Listener & Chokepoint
Aegis operates as a forward proxy bound to a local port (e.g., `127.0.0.1:8080`). The host operating system or specific target applications are configured via environment variables (e.g., `HTTP_PROXY`, `HTTPS_PROXY`) to route outbound traffic through this interface. While a framework like FastAPI may be used to serve a local configuration or dashboard API, the core proxy engine relies on Python's low-level `asyncio.start_server` to manage raw TCP socket streams, ensuring maximum control over malformed packets and network protocols.

### 1.2 Asynchronous Stream Handling
Network I/O is inherently slow compared to CPU cycles. To prevent the proxy from introducing intolerable latency or blocking the local application, Aegis relies entirely on asynchronous event loops.
* **Coroutines over Threads:** When a new connection hits the local port, `asyncio` spawns a lightweight coroutine rather than a heavy OS thread.
* **Non-Blocking I/O:** Using `asyncio.StreamReader` and `asyncio.StreamWriter`, the proxy asynchronously accepts incoming local payloads and pipes them to the external destination server, allowing the sidecar to handle thousands of concurrent outbound connections with minimal overhead.

### 1.3 Buffer and Memory Management (Preventing OOM)
To guarantee system stability, the proxy must never load entire payloads into RAM simultaneously. If an application attempts to upload a multi-gigabyte file, reading the entire payload into memory would trigger an Out-Of-Memory (OOM) crash.
* **Chunked Streaming:** The Python proxy reads the incoming data streams in fixed-size blocks (e.g., 8KB or 16KB chunks).
* **Sequential Evaluation:** These chunks are passed across the boundary to the Rust evaluation engine sequentially, ensuring the memory footprint of the proxy remains microscopic regardless of the total payload size.

### 1.4 The MITM Evolution (Pipeline Design Pattern)
Modern web traffic is predominantly encrypted via TLS (HTTPS). Because a heuristic engine cannot evaluate encrypted ciphertexts, Aegis must eventually act as a Man-In-The-Middle (MITM) to inspect payloads. To achieve this modularly, the asynchronous stream handlers utilize a Pipeline Design Pattern.
* **V1 (Plaintext Pipeline):** The core routing engine and Rust FFI boundary are validated using standard HTTP `GET` and `POST` requests. The `StreamReader` chunks are piped directly to the evaluation engine.
* **V2 (TLS Injection):** To intercept HTTPS, the Protocol Handler intercepts HTTP `CONNECT` requests, generates a forged certificate for the target domain via a local Root CA, and wraps the raw socket in a Python `ssl.SSLContext` using `loop.start_tls()`. This abstraction ensures the downstream Rust engine remains decoupled from the encryption layer, receiving only streams of decrypted bytes.

---

## Chapter 2: The Bridge (The Python-Rust FFI Boundary)

Moving data between a high-level interpreted language (Python) and a low-level systems language (Rust) introduces context-switching overhead. This Foreign Function Interface (FFI) boundary, built using `PyO3`, is designed to minimize latency and ensure memory safety during the handoff.

### 2.1 The Data Contract
To eliminate the severe performance penalty of serializing and deserializing complex objects (like JSON) across the boundary, the data contract strictly utilizes raw byte arrays.
* Python passes the network chunks from `asyncio` as raw `bytes` objects.
* The `PyO3` bridge maps these directly to Rust's `&[u8]` (byte slices). This avoids iterating through high-level Python string objects, which carry heavy metadata overhead, and ensures the data remains in contiguous memory blocks.

### 2.2 Memory Ownership & Zero-Copy Ambitions
Bridging Python's Garbage Collector (GC) with Rust's strict Ownership and Borrow Checker model requires precise memory management to avoid segmentation faults.
* Aegis targets a "Zero-Copy" architecture at the boundary. `PyO3` allows Rust to safely borrow the underlying memory buffer of the Python `bytes` object without copying the data into a new Rust `Vec`.
* Rust evaluates the borrowed memory, makes its `Allow/Drop` decision, and returns the boolean verdict before Python's GC is permitted to mutate or drop that memory reference.

### 2.3 Bypassing the GIL (Global Interpreter Lock)
Python's GIL prevents multiple threads from executing Python bytecodes simultaneously. If the Rust engine holds the GIL while running intensive heuristic scans, all other concurrent network connections in the Python proxy will block.
* **Execution Flow:** Upon entering the Rust function, `PyO3` explicitly releases the GIL (`Python::allow_threads`).
* The Rust engine executes the CPU-bound heuristics on a background thread. Meanwhile, the Python proxy remains free to continue routing hundreds of other asynchronous I/O packets. Rust only re-acquires the GIL momentarily to return the final evaluation verdict.

### 2.4 State Management: The Rolling Buffer
Because Chapter 1 established that payloads are evaluated in isolated memory chunks (e.g., 8KB) to prevent OOM errors, a critical vulnerability exists: a sensitive string (e.g., an AWS API key like `AKIAIOSFODNN7EXAMPLE`) could be split exactly across the boundary of two chunks.
* To mitigate this, the Rust engine maintains connection-specific state. It utilizes a tiny, rolling window buffer that stores a fixed number of bytes (e.g., the last 128 bytes) from the previous chunk.
* When the subsequent chunk arrives, Rust prepends the rolling buffer before scanning, guaranteeing that no exfiltrated secret escapes detection by straddling a chunk boundary.

---

## Chapter 3: The Engine (High-Speed Heuristic Evaluation)

Once the network payload crosses the FFI boundary into Rust, the core Data Exfiltration Prevention engine takes over. This module is strictly CPU-bound. Its architectural mandate is to scan raw byte streams for sensitive data with near-zero latency, ensuring the proxy does not bottleneck outbound network traffic.

### 3.1 The Multi-Pattern Matrix (Aho-Corasick Algorithm)
Standard Regular Expressions (Regex) are incredibly inefficient for scanning large payloads against hundreds of different secret signatures (e.g., AWS keys, GitHub tokens, Stripe API keys). A naive regex approach evaluates patterns sequentially, leading to severe performance degradation as the signature database grows.
* **The Solution:** Aegis utilizes the Aho-Corasick algorithm, a finite-state machine that searches for multiple string patterns simultaneously.
* **Time Complexity:** Aho-Corasick guarantees an $O(n + m + z)$ time complexity, where $n$ is the length of the payload chunk, $m$ is the total length of all patterns, and $z$ is the number of matches. This means the evaluation time remains largely constant whether we are scanning for 10 secret signatures or 10,000. It reads the byte stream in a single pass.

### 3.2 Entropy & Heuristic Analysis
While Aho-Corasick efficiently catches known, structured secrets (e.g., strings starting with `AKIA...` or `ghp_...`), it cannot catch undocumented or custom cryptographic keys. To detect these, the Rust engine employs heuristic analysis.
* **Shannon Entropy Calculation:** The engine identifies highly randomized, unstructured strings (such as Base64-encoded RSA private keys) by calculating their information density using Shannon Entropy:
$$H = -\sum_{i=1}^{n} p_i \log_2(p_i)$$
Where $p_i$ is the probability of a given character appearing in the evaluated chunk. If a string block exceeds a specific entropy threshold (e.g., $H > 4.5$ for alphanumeric strings), it is flagged as a potential cryptographic secret.
* **Contextual Validation:** Because high entropy alone can yield false positives (e.g., compressed image data or compiled binaries), the engine cross-references high-entropy blocks with surrounding contextual byte markers (e.g., `Authorization: Bearer`, `private_key`, or `=` padding in Base64) to finalize the verdict.

### 3.3 The Fail-Fast Execution Model
In a zero-trust sidecar, absolute security takes precedence over complete telemetry. The engine is not designed to catalog every single secret in a compromised payload; it is designed to stop the exfiltration immediately.
* **Short-Circuiting:** The Rust engine employs a strict fail-fast execution model. The absolute microsecond the Aho-Corasick automaton registers a critical match, or the entropy threshold alongside a context marker is breached, the evaluation loop short-circuits.
* **Immediate Handoff:** The engine immediately releases any remaining payload bytes, re-acquires the Python GIL, and passes a `Drop` signal back across the PyO3 boundary. This prevents wasting CPU cycles on an inherently compromised connection.

### 3.4 Concurrency & Thread-Safe State
Because the Python proxy routes traffic asynchronously, the Rust engine will be invoked concurrently by hundreds of different `asyncio` tasks.
* **Stateless Scanning with Stateful Buffers:** The core Aho-Corasick automaton and heuristic configurations are initialized once at startup and shared across threads as immutable, read-only references.
* **Connection Context:** To support the rolling buffer (defined in Chapter 2) needed to catch secrets spanning chunk boundaries, the Rust engine maintains an isolated, thread-safe state map (e.g., utilizing `DashMap` or a similar concurrent data structure). Each buffer is keyed to a unique connection ID passed from Python, ensuring that concurrent evaluations never corrupt each other's memory space.

---

## Chapter 4: The Verdict (Asynchronous Enforcement & Auditing)

The final phase of the Aegis pipeline occurs when the Rust heuristic engine returns an evaluation signal (`Allow` or `Drop`) across the PyO3 boundary back to the Python proxy. This chapter details how the `asyncio` event loop enforces the zero-trust policy and securely logs the event without compromising the very data it is designed to protect.

### 4.1 Connection Passthrough (The Allow State)
If the Rust engine evaluates a chunk and returns an `Allow` signal, the proxy must seamlessly forward the data to avoid bottlenecking the local application.
* **Stream Pipelining:** The Python proxy takes the cleared byte chunk and immediately writes it to the destination `asyncio.StreamWriter`.
* **Awaiting the Drain:** To prevent memory backpressure—where the local application sends data faster than the proxy can forward it to the external server—the proxy yields control back to the event loop using `await writer.drain()`. This ensures Aegis remains responsive and memory-safe even during massive data transfers.

### 4.2 Violent Termination (The Drop State)
When the Rust engine detects a plaintext secret and returns a `Drop` signal, Aegis must aggressively sever the connection before the compromised chunk leaves the local machine.
* **HTTP Interception:** If the protocol handler (defined in Chapter 1) recognizes an active HTTP session, Aegis injects an immediate `403 Forbidden` response back to the local application, complete with a custom header (e.g., `X-Aegis-Enforcement: Blocked`) to signal why the request failed.
* **TCP Reset (RST):** If the proxy is handling a raw TCP stream where standard HTTP responses are invalid, Aegis forcefully closes the underlying socket. It issues a TCP RST (Reset) packet by destroying the `StreamWriter` without a graceful FIN handshake, instantly killing the outbound route.

### 4.3 Secure Telemetry & Auditing
A zero-trust sidecar must maintain an immutable audit trail of exfiltration attempts. However, logging the intercepted payload would inherently violate compliance, as Aegis would effectively become a centralized vault of leaked plaintext secrets.
* **Secret Masking:** The auditing module is strictly forbidden from logging the matched string. Instead, the Rust engine returns a metadata payload alongside the `Drop` signal, containing only the signature type (e.g., `AWS_ACCESS_KEY_ID`, `HIGH_ENTROPY_BASE64`) and the length of the matched string.
* **The Event Log:** The Python proxy writes a structured JSON log entry containing the timestamp, the local PID (Process ID) of the offending application, the destination IP/Hostname, and the matched signature type.
* **Compliance Ready:** This ensures the telemetry is actionable for security operations and fully compliant with enterprise data governance standards, proving the tool is safe for deployment in distributed environments.

### 4.4 Graceful Teardown
Once a connection is terminated or successfully completed, the proxy must clean up its state to prevent memory leaks and dangling file descriptors.
* The Python `asyncio` task explicitly closes both the local `StreamReader` and the external `StreamWriter`.
* A signal is sent to the Rust engine to drop the connection's specific rolling buffer from its concurrent state map, freeing the allocated memory back to the system immediately.
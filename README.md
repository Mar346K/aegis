# 🛡️ Aegis: High-Performance Zero-Trust Egress Proxy

[![Aegis CI/CD](https://github.com/Mar346K/aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/Mar346K/aegis/actions/workflows/ci.yml)

Aegis is a highly concurrent, memory-safe network sidecar designed for Data Exfiltration Prevention. Built with a hybrid polyglot architecture, it intercepts outbound HTTP/TCP traffic and asynchronously terminates connections if heuristic scanning detects plaintext API keys, cryptographic secrets, or highly entropic payloads.

By utilizing Python (`asyncio`) for non-blocking network routing and a Rust (`PyO3`) compiled engine for CPU-bound multi-pattern matching, Aegis achieves high-speed traffic inspection while entirely bypassing the Python Global Interpreter Lock (GIL).


## 🧠 Core Architecture Highlights

* **Zero-Copy FFI Boundary:** Python `bytes` chunks are passed to the Rust engine as borrowed `&[u8]` slices, avoiding costly memory duplication and preventing OOM crashes on large file uploads.
* **$O(n)$ Heuristic Engine:** Replaces naive regex with the Aho-Corasick finite-state machine in Rust to evaluate hundreds of secret signatures simultaneously in a single, lightning-fast pass.
* **True Concurrency (GIL Bypass):** The `PyO3` bridge explicitly releases the Python GIL (`py.allow_threads`) during evaluation, allowing the `asyncio` proxy to route thousands of concurrent packets without blocking.
* **Compliance-Safe Telemetry:** Aegis logs exfiltration attempts (e.g., matching signature type, local PID, timestamp) without ever writing the plaintext secret to disk.

📖 **[Read the full System Design & Architecture Document here](ARCHITECTURE.md)**

## 🛠️ Quick Start & Installation

Aegis is built using `maturin` to seamlessly compile the Rust FFI extension into a native Python module.

**Prerequisites**
* Python 3.10+
* Rust (`cargo`)
* Maturin

**Build from Source**
```bash
# Clone the repository
git clone [https://github.com/Mar346K/aegis.git](https://github.com/Mar346K/aegis.git)
cd aegis

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Compile the Rust engine and install the Python package
pip install maturin
maturin develop --release

# Run the Aegis proxy daemon
python aegis/main.py
```

### 🧪 Running the Test Suite
Aegis includes automated integration tests that spin up the local proxy, route mock payloads through the FFI boundary, and validate the enforcement logic.

```Bash
python tests/test_engine.py
python tests/test_proxy.py
```

# Aegis: Zero-Trust Network Sidecar

[![Aegis CI/CD](https://github.com/Mar346K/aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/Mar346K/aegis/actions/workflows/ci.yml)

Aegis is a high-performance, polyglot egress proxy designed to prevent data exfiltration. It utilizes asynchronous Python (`asyncio`) for non-blocking I/O routing and a compiled Rust engine (`PyO3`) for zero-copy, microsecond-latency heuristic evaluation (Aho-Corasick & Shannon Entropy).

For full technical details, memory management strategies, and benchmark considerations, please see the [Aegis Architecture & System Design Document](ARCHITECTURE.md).
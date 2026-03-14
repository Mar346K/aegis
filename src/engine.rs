use aho_corasick::AhoCorasick;
use pyo3::prelude::*;

/// The core heuristic engine exposed to Python.
#[pyclass]
pub struct AegisEngine {
    matcher: AhoCorasick,
}

#[pymethods]
impl AegisEngine {
    /// Initializes the engine and compiles the multi-pattern state machine.
    /// Python will call this exactly once when the proxy starts.
    #[new]
    pub fn new() -> Self {
        // In a production build, these would be loaded dynamically from a rule file.
        // For our textbook V1, we hardcode critical DevSecOps exfiltration vectors.
        let patterns = &[
            "AKIA",                  // AWS Access Key ID prefix
            "ghp_",                  // GitHub Personal Access Token
            "sk_live_",              // Stripe Secret Key
            "BEGIN RSA PRIVATE KEY", // Standard PEM header
            "xoxb-",                 // Slack Bot Token
        ];

        // Compile the Aho-Corasick automaton
        let matcher = AhoCorasick::new(patterns)
            .expect("Failed to build Aho-Corasick automaton");

        AegisEngine { matcher }
    }

    /// The zero-copy FFI boundary. 
    /// Takes a borrowed byte slice (&[u8]) directly from Python's memory.
    /// Returns True if a secret is found (DROP), False if clean (ALLOW).
    #[pyo3(signature = (payload))]
    pub fn scan_payload(&self, py: Python<'_>, payload: &[u8]) -> bool {
        // EXTREMELY IMPORTANT: Release the Python GIL!
        // This allows Python to route other network packets concurrently 
        // while Rust crunches the CPU-bound heuristics on this background thread.
        py.allow_threads(|| {
            
            // 1. Signature Matching (Fail Fast)
            // Aho-Corasick scans the entire payload in a single pass O(n).
            if self.matcher.is_match(payload) {
                return true; // Secret found! Short-circuit and signal DROP.
            }

            // 2. Heuristic Analysis (Shannon Entropy)
            // If no known signature is found, check for high-entropy crypto keys.
            if self.calculate_entropy(payload) > 4.5 {
                // Note: In V2, we would cross-reference this with context markers 
                // to prevent false positives on compressed data.
                return true; // Suspiciously randomized data found! Signal DROP.
            }

            // If both checks pass, the payload is clean.
            false 
        })
    }
}

impl AegisEngine {
    /// Calculates the Shannon Entropy of a byte slice to detect randomized secrets.
    fn calculate_entropy(&self, data: &[u8]) -> f64 {
        if data.is_empty() {
            return 0.0;
        }

        let mut frequencies = [0usize; 256];
        for &byte in data {
            frequencies[byte as usize] += 1;
        }

        let mut entropy = 0.0;
        let len = data.len() as f64;

        for &count in &frequencies {
            if count > 0 {
                let probability = (count as f64) / len;
                entropy -= probability * probability.log2();
            }
        }

        entropy
    }
}
use aho_corasick::AhoCorasick;
use pyo3::prelude::*;

#[pyclass]
pub struct AegisEngine {
    matcher: AhoCorasick,
}

#[pymethods]
impl AegisEngine {
    #[new]
    pub fn new() -> Self {
        let patterns = &[
            "AKIA",                  // AWS Access Key ID
            "ghp_",                  // GitHub Token
            "sk_live_",              // Stripe Secret
            "BEGIN RSA PRIVATE KEY", // PEM Header
            "xoxb-",                 // Slack Token
        ];
        let matcher = AhoCorasick::new(patterns).expect("Failed to build Aho-Corasick");
        AegisEngine { matcher }
    }

    #[pyo3(signature = (payload))]
    pub fn scan_payload(&self, py: Python<'_>, payload: &[u8]) -> bool {
        py.allow_threads(|| {
            // 1. Signature Matching (Fail Fast)
            if self.matcher.is_match(payload) {
                return true; 
            }

            // 2. Heuristic Analysis (Shannon Entropy)
            // ARCHITECT'S NOTE: Disabled for V1. 
            // Running entropy math on raw, un-tokenized HTTP headers 
            // causes immediate false positives. V2 will tokenize first.
            //
            // if self.calculate_entropy(payload) > 4.5 {
            //     return true;
            // }

            false 
        })
    }
}

impl AegisEngine {
    fn calculate_entropy(&self, data: &[u8]) -> f64 {
        if data.is_empty() { return 0.0; }
        let mut frequencies = [0usize; 256];
        for &byte in data { frequencies[byte as usize] += 1; }
        
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
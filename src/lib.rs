use pyo3::prelude::*;

// Import the engine module we just created
mod engine;
use engine::AegisEngine;

/// The initialization of the Python module.
#[pymodule]
fn _engine(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Register the AegisEngine class with the Python module
    m.add_class::<AegisEngine>()?;
    Ok(())
}
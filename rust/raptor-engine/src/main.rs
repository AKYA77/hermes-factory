//! Command-line driver for the exact sequential quote replay engine.
//!
//! Reads a JSON request (profile, spec, quotes, signals) and writes the exact
//! execution result as JSON on stdout. Prices in the output are integer multiples
//! of the instrument tick (`price_int`), so a caller can compare them exactly.

use std::env;
use std::fs;

use serde::Deserialize;

use raptor_engine::{
    replay, Profile, ProfileIn, Quote, Signal, Spec, SpecIn,
};

#[derive(Deserialize)]
struct Request {
    profile: ProfileIn,
    spec: SpecIn,
    #[serde(default = "default_conservative")]
    conservative: bool,
    quotes: Vec<Quote>,
    signals: Vec<Signal>,
}

fn default_conservative() -> bool {
    true
}

fn main() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    let path = args
        .get(1)
        .ok_or("usage: raptor-engine <request.json>")?;
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let request: Request = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    let profile = Profile::from_input(&request.profile)?;
    let spec = Spec::from_input(&request.spec)?;
    let result = replay(
        &profile,
        &spec,
        &request.quotes,
        &request.signals,
        request.conservative,
    )?;
    println!(
        "{}",
        serde_json::to_string(&result).map_err(|e| e.to_string())?
    );
    Ok(())
}

//! Command-line driver for the exact sequential quote replay engine.
//!
//! Reads a JSON request (profile, spec, quotes, signals) and writes the exact
//! execution result as JSON on stdout. Prices in the output are integer multiples
//! of the instrument tick (`price_int`), so a caller can compare them exactly.
//!
//! Options:
//!   --batch-size N     save and restore the engine state every N quotes
//!   --dump-state PATH  write the final engine state as JSON
//!   --resume-from PATH start from a previously dumped engine state
//!
//! `--batch-size`, `--dump-state` and `--resume-from` together provide the
//! restart and batch-size evidence the migration gate requires: a run split at
//! any quote boundary and resumed must produce exactly the same result as one
//! uninterrupted pass.

use std::env;
use std::fs;

use serde::Deserialize;

use raptor_engine::{Profile, ProfileIn, Quote, Replayer, ReplayerState, Signal, Spec, SpecIn};

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
    let usage = "usage: raptor-engine <request.json> [--batch-size N] \
                 [--dump-state PATH] [--resume-from PATH]";
    let path = args.get(1).ok_or(usage)?;

    let mut batch_size: Option<usize> = None;
    let mut dump_state: Option<String> = None;
    let mut resume_from: Option<String> = None;
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--batch-size" => {
                i += 1;
                let value = args.get(i).ok_or("--batch-size needs a value")?;
                batch_size = Some(value.parse().map_err(|_| "invalid --batch-size")?);
            }
            "--dump-state" => {
                i += 1;
                dump_state = Some(args.get(i).ok_or("--dump-state needs a path")?.clone());
            }
            "--resume-from" => {
                i += 1;
                resume_from = Some(args.get(i).ok_or("--resume-from needs a path")?.clone());
            }
            other => return Err(format!("unknown argument {other:?}\n{usage}")),
        }
        i += 1;
    }

    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let request: Request = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    let profile = Profile::from_input(&request.profile)?;
    let spec = Spec::from_input(&request.spec)?;

    let mut replayer = match &resume_from {
        Some(path) => {
            let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
            let state: ReplayerState = serde_json::from_str(&text).map_err(|e| e.to_string())?;
            Replayer::restore(
                state,
                &profile,
                &spec,
                &request.signals,
                request.conservative,
            )
        }
        None => Replayer::new(&profile, &spec, &request.signals, request.conservative),
    };

    let quotes = &request.quotes;
    if let Some(size) = batch_size {
        if size == 0 {
            return Err("--batch-size must be at least 1".to_string());
        }
        for (offset, q) in quotes.iter().enumerate() {
            replayer.step(q)?;
            if (offset + 1) % size == 0 {
                let encoded =
                    serde_json::to_string(&replayer.state()).map_err(|e| e.to_string())?;
                let restored: ReplayerState =
                    serde_json::from_str(&encoded).map_err(|e| e.to_string())?;
                replayer = Replayer::restore(
                    restored,
                    &profile,
                    &spec,
                    &request.signals,
                    request.conservative,
                );
            }
        }
    } else {
        for q in quotes {
            replayer.step(q)?;
        }
    }

    if let Some(path) = dump_state {
        let encoded = serde_json::to_string(&replayer.state()).map_err(|e| e.to_string())?;
        fs::write(&path, encoded).map_err(|e| e.to_string())?;
    }

    let result = replayer.finish();
    println!(
        "{}",
        serde_json::to_string(&result).map_err(|e| e.to_string())?
    );
    Ok(())
}

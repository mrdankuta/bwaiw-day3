//! Eyeball helper: pipe a month-inputs JSON document on stdin, get the
//! Plan document on stdout. Uses the exact JSON seam the WASM binding
//! will expose. Example:
//!   echo '{"income_cents":10000,...}' | cargo run --example plan
use std::io::Read;

fn main() {
    let mut input = String::new();
    std::io::stdin()
        .read_to_string(&mut input)
        .expect("read stdin");
    match budget_engine::plan_from_json(&input) {
        Ok(plan) => println!("{plan}"),
        Err(e) => {
            eprintln!("error: {e}");
            std::process::exit(1);
        }
    }
}

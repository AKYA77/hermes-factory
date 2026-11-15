//! RaptorBT-derived exact bid/ask execution engine.
//!
//! This is a from-scratch Rust implementation of the Hermes Factory execution
//! contract. It reproduces the reference semantics implemented in Python under
//! `factory/simulation/`:
//!
//! - `effective_quotes`: 2-pip minimum spread, wider observed spread preserved,
//!   outward tick-grid rounding.
//! - `eligible_price`: separate 2-pip adverse slippage on market and stop-market
//!   fills, outward tick-grid rounding, distinct limit behaviour.
//! - `size_position`: 10% equity risk budget with the adverse stop excursion
//!   included in projected loss.
//! - bracket replay: entry market, stop-market, take-profit limit, deadline
//!   timeout, one open position at a time.
//!
//! All arithmetic is exact. Prices are integer multiples of the instrument tick;
//! money and size are exact rationals. Nothing is rounded except where the
//! reference policy explicitly rounds.

use num_bigint::BigInt;
use num_traits::{One, Signed, ToPrimitive, Zero};
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;

pub const NANOS: i64 = 1_000_000_000;

// --------------------------------------------------------------------------
// Exact rational
// --------------------------------------------------------------------------

/// Arbitrary-precision rational.
///
/// The reference policy rounds conversion rates to 28 significant decimal
/// digits, so denominators reach 10^27 and the product of two such values
/// exceeds `i128`. Exact comparison and arithmetic therefore require big
/// integers; a fixed-width type silently wraps in release builds.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Rat {
    pub n: BigInt,
    pub d: BigInt,
}

fn gcd_big(mut a: BigInt, mut b: BigInt) -> BigInt {
    a = a.abs();
    b = b.abs();
    while !b.is_zero() {
        let t = &a % &b;
        a = b;
        b = t;
    }
    if a.is_zero() {
        BigInt::one()
    } else {
        a
    }
}

/// Round `num / den` to nearest, ties to even. `den` must be positive.
fn round_half_even_big(num: &BigInt, den: &BigInt) -> BigInt {
    let negative = num < &BigInt::zero();
    let n = num.abs();
    let q = &n / den;
    let r = &n % den;
    let twice = &r * 2u32;
    let m = if twice > *den || (twice == *den && (&q % 2u32) != BigInt::zero()) {
        q + 1u32
    } else {
        q
    };
    if negative {
        -m
    } else {
        m
    }
}

impl Rat {
    pub fn new(n: BigInt, d: BigInt) -> Self {
        assert!(!d.is_zero(), "zero denominator");
        let (n, d) = if d < BigInt::zero() { (-n, -d) } else { (n, d) };
        let g = gcd_big(n.clone(), d.clone());
        Rat {
            n: n / &g,
            d: d / &g,
        }
    }

    pub fn big(n: BigInt) -> Self {
        Rat {
            n,
            d: BigInt::one(),
        }
    }

    pub fn int(n: i128) -> Self {
        Rat::big(BigInt::from(n))
    }

    pub fn zero() -> Self {
        Rat::big(BigInt::zero())
    }

    pub fn is_zero(&self) -> bool {
        self.n.is_zero()
    }

    pub fn add(&self, o: &Rat) -> Rat {
        Rat::new(&self.n * &o.d + &o.n * &self.d, &self.d * &o.d)
    }

    pub fn sub(&self, o: &Rat) -> Rat {
        Rat::new(&self.n * &o.d - &o.n * &self.d, &self.d * &o.d)
    }

    pub fn mul(&self, o: &Rat) -> Rat {
        Rat::new(&self.n * &o.n, &self.d * &o.d)
    }

    pub fn div(&self, o: &Rat) -> Rat {
        Rat::new(&self.n * &o.d, &self.d * &o.n)
    }

    pub fn neg(&self) -> Rat {
        Rat {
            n: -self.n.clone(),
            d: self.d.clone(),
        }
    }

    pub fn cmp(&self, o: &Rat) -> Ordering {
        (&self.n * &o.d).cmp(&(&o.n * &self.d))
    }

    pub fn le(&self, o: &Rat) -> bool {
        self.cmp(o) != Ordering::Greater
    }

    pub fn ge(&self, o: &Rat) -> bool {
        self.cmp(o) != Ordering::Less
    }

    pub fn max(&self, o: &Rat) -> Rat {
        if self.cmp(o) == Ordering::Less {
            o.clone()
        } else {
            self.clone()
        }
    }

    pub fn min(&self, o: &Rat) -> Rat {
        if self.cmp(o) == Ordering::Greater {
            o.clone()
        } else {
            self.clone()
        }
    }

    pub fn floor(&self) -> BigInt {
        let mut q = &self.n / &self.d;
        if self.n < BigInt::zero() && (&self.n % &self.d) != BigInt::zero() {
            q = q - BigInt::one();
        }
        q
    }

    pub fn ceil(&self) -> BigInt {
        let mut q = &self.n / &self.d;
        if self.n > BigInt::zero() && (&self.n % &self.d) != BigInt::zero() {
            q = q + BigInt::one();
        }
        q
    }

    /// Parse an exact decimal string such as "0.001" or "-20".
    pub fn from_decimal(s: &str) -> Result<Self, String> {
        let s = s.trim();
        let (neg, body) = match s.strip_prefix('-') {
            Some(rest) => (true, rest),
            None => (false, s),
        };
        let (int_part, frac_part) = match body.split_once('.') {
            Some((a, b)) => (a, b),
            None => (body, ""),
        };
        if int_part.is_empty() && frac_part.is_empty() {
            return Err("empty decimal".to_string());
        }
        if !int_part.chars().all(|c| c.is_ascii_digit())
            || !frac_part.chars().all(|c| c.is_ascii_digit())
        {
            return Err(format!("invalid decimal {s:?}"));
        }
        let digits = format!("{int_part}{frac_part}");
        let n: BigInt = digits.parse().map_err(|_| "decimal overflow".to_string())?;
        let d = BigInt::from(10u32).pow(frac_part.len() as u32);
        let r = Rat::new(n, d);
        Ok(if neg { r.neg() } else { r })
    }

    /// Round to 28 significant decimal digits, half-even.
    ///
    /// This mirrors `decimal_amount` in `factory/monetary.py`, which divides two
    /// `Decimal` values under `prec = 28` and `ROUND_HALF_EVEN`.
    pub fn round_sig28(&self) -> Rat {
        if self.n.is_zero() {
            return Rat::zero();
        }
        let sign = self.n < BigInt::zero();
        let n = self.n.abs();
        let d = self.d.clone();
        // e = floor(log10(n/d))
        let mut e: i64 = 0;
        if n >= d {
            let mut cur = n.clone();
            while cur >= &d * 10u32 {
                cur = cur / 10u32;
                e += 1;
            }
        } else {
            let mut cur = n.clone();
            while &cur * 10u32 < d {
                cur = cur * 10u32;
                e -= 1;
            }
            // The loop stops with cur/d in [0.1, 1), so n/d = (cur/d) * 10^e
            // lies in [10^(e-1), 10^e) and floor(log10(n/d)) is one lower.
            e -= 1;
        }
        let s = 27 - e;
        let (m, den) = if s >= 0 {
            let scale = BigInt::from(10u32).pow(s as u32);
            (round_half_even_big(&(&n * &scale), &d), scale)
        } else {
            let scale = BigInt::from(10u32).pow((-s) as u32);
            (round_half_even_big(&n, &(&d * &scale)), scale)
        };
        let r = Rat::new(m, den);
        if sign {
            r.neg()
        } else {
            r
        }
    }

    /// Plain decimal string of the 28-significant-digit representation.
    pub fn to_decimal_string(&self) -> String {
        let r = self.round_sig28();
        if r.n.is_zero() {
            return "0".to_string();
        }
        let sign = if r.n < BigInt::zero() { "-" } else { "" };
        let digits = r.n.abs().to_string();
        let k = (r.d.to_string().len() as i64) - 1;
        let body = if k == 0 {
            digits
        } else if (digits.len() as i64) > k {
            let split = digits.len() - k as usize;
            format!("{}.{}", &digits[..split], &digits[split..])
        } else {
            format!("0.{}{}", "0".repeat(k as usize - digits.len()), digits)
        };
        format!("{sign}{body}")
    }
}

// --------------------------------------------------------------------------
// Contracts
// --------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Side {
    Buy,
    Sell,
}

impl Side {
    pub fn flip(self) -> Side {
        match self {
            Side::Buy => Side::Sell,
            Side::Sell => Side::Buy,
        }
    }
    pub fn as_str(self) -> &'static str {
        match self {
            Side::Buy => "BUY",
            Side::Sell => "SELL",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum OrderType {
    Market,
    StopMarket,
    Limit,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ProfileIn {
    pub instrument: String,
    pub tick_size: String,
    pub pip_size: String,
    pub price_scale: i64,
    pub base_currency: String,
    pub quote_currency: String,
    pub contract_multiplier: String,
    pub volume_step: String,
    pub min_volume: String,
    pub max_volume: String,
    pub margin_rate: String,
    pub min_stop_ticks: i64,
    #[serde(default = "zero_string")]
    pub commission_per_unit: String,
}

fn zero_string() -> String {
    "0".to_string()
}

#[derive(Clone, Debug)]
pub struct Profile {
    pub instrument: String,
    pub tick_int: i64,
    pub pip_int: i64,
    pub price_scale: i64,
    pub base_currency: String,
    pub quote_currency: String,
    pub contract_multiplier: Rat,
    pub volume_step: Rat,
    pub min_volume: Rat,
    pub max_volume: Rat,
    pub margin_rate: Rat,
    pub min_stop_ticks: i64,
    pub commission_per_unit: Rat,
    pub volume_precision: usize,
}

/// Number of digits after the decimal point in a decimal string.
fn decimal_places(text: &str) -> usize {
    match text.split_once('.') {
        Some((_, fraction)) => fraction.len(),
        None => 0,
    }
}

impl Profile {
    /// Round a quantity the way the reference's `make_qty` does: convert to the
    /// nearest binary64 value, then round that value to the instrument's size
    /// precision using round-half-to-even.
    pub fn round_volume(&self, qty: &Rat) -> Rat {
        let value = match (qty.n.to_f64(), qty.d.to_f64()) {
            (Some(n), Some(d)) if d != 0.0 => n / d,
            _ => return qty.clone(),
        };
        let rendered = format!("{:.*}", self.volume_precision, value);
        Rat::from_decimal(&rendered).unwrap_or_else(|_| qty.clone())
    }

    pub fn from_input(p: &ProfileIn) -> Result<Self, String> {
        let tick = Rat::from_decimal(&p.tick_size)?;
        let pip = Rat::from_decimal(&p.pip_size)?;
        let scale = Rat::int(p.price_scale as i128);
        let tick_int = tick.mul(&scale).floor();
        let pip_int = pip.mul(&scale).floor();
        if tick_int <= BigInt::zero() || pip_int <= BigInt::zero() {
            return Err("tick/pip must be positive on the price grid".to_string());
        }
        if (&pip_int % &tick_int) != BigInt::zero() {
            return Err("pip_size must be a whole number of ticks".to_string());
        }
        Ok(Profile {
            instrument: p.instrument.clone(),
            tick_int: tick_int.to_i64().ok_or("tick overflow")?,
            pip_int: pip_int.to_i64().ok_or("pip overflow")?,
            price_scale: p.price_scale,
            base_currency: p.base_currency.clone(),
            quote_currency: p.quote_currency.clone(),
            contract_multiplier: Rat::from_decimal(&p.contract_multiplier)?,
            volume_step: Rat::from_decimal(&p.volume_step)?,
            min_volume: Rat::from_decimal(&p.min_volume)?,
            max_volume: Rat::from_decimal(&p.max_volume)?,
            margin_rate: Rat::from_decimal(&p.margin_rate)?,
            min_stop_ticks: p.min_stop_ticks,
            commission_per_unit: Rat::from_decimal(&p.commission_per_unit)?,
            volume_precision: decimal_places(&p.volume_step),
        })
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct SpecIn {
    pub stop_ticks: i64,
    #[serde(default = "default_rr")]
    pub target_rr: String,
    #[serde(default = "default_hold")]
    pub max_hold_seconds: i64,
    #[serde(default = "default_direction")]
    pub direction: String,
    /// Optional finite-book model, mirroring the reference's test-injected
    /// `FiniteEligibleBook`. `null` means unbounded L1 depth (production).
    #[serde(default)]
    pub partial: Option<PartialIn>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct PartialIn {
    pub order_type: String,
    #[serde(default)]
    pub side: Option<String>,
    #[serde(default = "default_divisor")]
    pub divisor: i64,
}

fn default_divisor() -> i64 {
    2
}

fn default_rr() -> String {
    "3".to_string()
}
fn default_hold() -> i64 {
    86400
}
fn default_direction() -> String {
    "both".to_string()
}

#[derive(Clone, Debug)]
pub struct Spec {
    pub stop_ticks: i64,
    pub target_rr: i64,
    pub max_hold_seconds: i64,
    pub direction: Direction,
    pub partial: Option<Partial>,
}

#[derive(Clone, Debug)]
pub struct Partial {
    pub order_type: OrderType,
    pub side: Option<Side>,
    pub divisor: i64,
}

impl Partial {
    /// The executable quantity available to an order of the given role/side.
    fn available(&self, profile: &Profile, role: &str, side: Side, requested: &Rat) -> Rat {
        let order_type = match role {
            "ENTRY" => OrderType::Market,
            "STOP_LOSS" => OrderType::StopMarket,
            "TAKE_PROFIT" => OrderType::Limit,
            _ => OrderType::Market,
        };
        if order_type != self.order_type {
            return requested.clone();
        }
        if self.order_type == OrderType::Market && self.side.is_some() && self.side != Some(side) {
            return requested.clone();
        }
        let order_qty = profile.round_volume(requested);
        if self.divisor <= 1 {
            return order_qty;
        }
        let capped = order_qty.div(&Rat::int(self.divisor as i128));
        profile.round_volume(&capped)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Direction {
    Both,
    Long,
    Short,
}

impl Spec {
    pub fn from_input(s: &SpecIn) -> Result<Self, String> {
        let target_rr = s
            .target_rr
            .parse::<i64>()
            .map_err(|_| "invalid target_rr")?;
        let direction = match s.direction.as_str() {
            "both" => Direction::Both,
            "long" => Direction::Long,
            "short" => Direction::Short,
            other => return Err(format!("invalid direction {other:?}")),
        };
        let partial = match &s.partial {
            None => None,
            Some(p) => {
                let order_type = match p.order_type.as_str() {
                    "MARKET" => OrderType::Market,
                    "STOP_MARKET" => OrderType::StopMarket,
                    "LIMIT" => OrderType::Limit,
                    other => return Err(format!("invalid partial order type {other:?}")),
                };
                let side = match p.side.as_deref() {
                    None => None,
                    Some("BUY") => Some(Side::Buy),
                    Some("SELL") => Some(Side::Sell),
                    Some(other) => return Err(format!("invalid partial side {other:?}")),
                };
                Some(Partial {
                    order_type,
                    side,
                    divisor: p.divisor,
                })
            }
        };
        Ok(Spec {
            stop_ticks: s.stop_ticks,
            target_rr,
            max_hold_seconds: s.max_hold_seconds,
            direction,
            partial,
        })
    }
}

#[derive(Clone, Copy, Debug, Deserialize)]
pub struct Quote {
    pub ts: i64,
    pub bid: i64,
    pub ask: i64,
}

#[derive(Clone, Copy, Debug, Deserialize)]
pub struct Signal {
    pub available_at: i64,
    pub side: SideIn,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "UPPERCASE")]
pub enum SideIn {
    Buy,
    Sell,
}

impl From<SideIn> for Side {
    fn from(s: SideIn) -> Side {
        match s {
            SideIn::Buy => Side::Buy,
            SideIn::Sell => Side::Sell,
        }
    }
}

// --------------------------------------------------------------------------
// Pricing
// --------------------------------------------------------------------------

fn div_round(num: i128, den: i128, up: bool) -> i64 {
    let q = num / den;
    let r = num % den;
    let v = if up {
        if r != 0 {
            q + 1
        } else {
            q
        }
    } else {
        q
    };
    v as i64
}

/// 2-pip minimum spread, wider observed spread preserved, outward tick rounding.
pub fn effective_quotes(
    bid: i64,
    ask: i64,
    p: &Profile,
    conservative: bool,
) -> Result<(i64, i64), String> {
    if bid > ask {
        return Err("inverted quote".to_string());
    }
    if !conservative {
        return Ok((bid, ask));
    }
    let spread = (ask - bid).max(2 * p.pip_int);
    let mid2 = bid + ask;
    let bid2 = mid2 - spread;
    let ask2 = mid2 + spread;
    let b = div_round(bid2 as i128, 2 * p.tick_int as i128, false);
    let a = div_round(ask2 as i128, 2 * p.tick_int as i128, true);
    Ok((b, a))
}

/// The quantity an order of the given role may actually execute: the reference
/// rounds the order quantity to the instrument's size increment, and a finite
/// eligible book further caps it (the capped quantity is rounded again).
fn order_quantity(
    profile: &Profile,
    requested: &Rat,
    partial: &Option<Partial>,
    role: &str,
    side: Side,
) -> Rat {
    match partial {
        Some(p) => p.available(profile, role, side, requested),
        None => profile.round_volume(requested),
    }
}

/// Separate 2-pip adverse slippage on market and stop-market fills, outward
/// tick-grid rounding. Limit orders receive no slippage.
pub fn eligible_price(
    price: i64,
    side: Side,
    order_type: OrderType,
    p: &Profile,
    conservative: bool,
) -> i64 {
    let slip = if conservative && matches!(order_type, OrderType::Market | OrderType::StopMarket) {
        2 * p.pip_int
    } else {
        0
    };
    let raw = if side == Side::Buy {
        price + slip
    } else {
        price - slip
    };
    let r = raw as i128;
    let t = p.tick_int as i128;
    let rounded = if side == Side::Buy {
        let q = r / t;
        if r % t != 0 {
            (q + 1) * t
        } else {
            r
        }
    } else {
        let q = r / t;
        if r % t != 0 && r < 0 {
            (q - 1) * t
        } else {
            q * t
        }
    };
    rounded as i64
}

/// Dated executable FX conversion to the USD account, decimal28 rounded.
pub fn conversion_rate(p: &Profile, eff_bid: i64, eff_ask: i64, side: Side) -> Result<Rat, String> {
    if p.quote_currency == "USD" {
        return Ok(Rat::int(1));
    }
    if p.base_currency != "USD" {
        return Err("UNKNOWN_CONVERSION".to_string());
    }
    let unit = if side == Side::Sell { eff_ask } else { eff_bid };
    if unit <= 0 {
        return Err("INVALID_CONVERSION_QUOTE".to_string());
    }
    let scale = Rat::int(p.price_scale as i128);
    let unit_dec = Rat::int(unit as i128).div(&scale);
    let rate = Rat::int(1).div(&unit_dec);
    Ok(rate.round_sig28())
}

pub enum SizeResult {
    Eligible {
        size: Rat,
        risk: Rat,
        risk_budget: Rat,
        margin: Rat,
    },
    SkippedStopLevel,
    SkippedMinVolume,
    SkippedMargin,
}

impl std::fmt::Debug for SizeResult {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SizeResult::Eligible {
                size,
                risk,
                risk_budget,
                margin,
            } => write!(
                f,
                "Eligible(size={:?} risk={:?} budget={:?} margin={:?})",
                size, risk, risk_budget, margin
            ),
            SizeResult::SkippedStopLevel => write!(f, "SkippedStopLevel"),
            SizeResult::SkippedMinVolume => write!(f, "SkippedMinVolume"),
            SizeResult::SkippedMargin => write!(f, "SkippedMargin"),
        }
    }
}

/// 10% equity risk budget; projected loss includes the adverse stop excursion.
pub fn size_position(
    equity: Rat,
    entry: i64,
    stop: i64,
    p: &Profile,
    quote_to_account: Rat,
    conservative: bool,
) -> Result<SizeResult, String> {
    if quote_to_account.cmp(&Rat::zero()) != Ordering::Greater {
        return Err("UNKNOWN_CONVERSION".to_string());
    }
    let distance = (entry - stop).abs();
    if distance < p.min_stop_ticks * p.tick_int {
        return Ok(SizeResult::SkippedStopLevel);
    }
    let adverse = if conservative { 2 * p.pip_int } else { 0 };
    let scale = Rat::int(p.price_scale as i128);
    let loss_per_unit = Rat::int((distance + adverse) as i128)
        .div(&scale)
        .mul(&p.contract_multiplier)
        .mul(&quote_to_account);
    let risk_budget = equity
        .mul(&Rat::new(BigInt::from(1), BigInt::from(10)))
        .max(&Rat::zero());
    let raw = risk_budget.div(&loss_per_unit).min(&p.max_volume);
    let steps = raw.div(&p.volume_step).floor();
    let size = Rat::big(steps).mul(&p.volume_step);
    if size.cmp(&p.min_volume) == Ordering::Less {
        return Ok(SizeResult::SkippedMinVolume);
    }
    let risk = size.mul(&loss_per_unit);
    let margin = size
        .mul(&Rat::int(entry as i128))
        .div(&scale)
        .mul(&p.contract_multiplier)
        .mul(&quote_to_account)
        .mul(&p.margin_rate);
    if margin.cmp(&equity) == Ordering::Greater {
        return Ok(SizeResult::SkippedMargin);
    }
    Ok(SizeResult::Eligible {
        size,
        risk,
        risk_budget,
        margin,
    })
}

// --------------------------------------------------------------------------
// Replay
// --------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExitFillRecord {
    pub price_int: i64,
    #[serde(with = "rat_serde")]
    pub size: Rat,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FillOut {
    pub role: String,
    pub ts: i64,
    pub qi: usize,
    pub side: String,
    pub price_int: i64,
    pub size_num: String,
    pub size_den: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrderStateOut {
    pub role: String,
    pub terminal: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TradeOut {
    pub side: String,
    pub entry_ts: i64,
    pub entry_qi: usize,
    pub exit_ts: Option<i64>,
    pub exit_qi: Option<usize>,
    pub entry_price_int: i64,
    pub exit_price_int: Option<i64>,
    pub stop_int: i64,
    pub target_int: i64,
    pub flags: Vec<String>,
    pub exit_reason: Option<String>,
    pub exit_reasons: Vec<String>,
    pub order_states: Vec<OrderStateOut>,
    pub pnl_num: String,
    pub pnl_den: String,
    pub entered_num: String,
    pub entered_den: String,
    pub requested_num: String,
    pub requested_den: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SkipOut {
    pub ts: i64,
    pub status: String,
}

/// Per-trade realized equity observation. Reported only when the caller opts in
/// with `--emit-equity`; the default result schema stays byte-identical so the
/// frozen Nautilus goldens remain comparable.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EquityRecord {
    pub entry_ts: i64,
    pub exit_ts: Option<i64>,
    #[serde(with = "rat_serde")]
    pub before: Rat,
    #[serde(with = "rat_serde")]
    pub after: Rat,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EquityOut {
    pub trades: Vec<EquityRecord>,
    #[serde(with = "rat_serde")]
    pub ending_equity: Rat,
    #[serde(with = "rat_serde")]
    pub initial_equity: Rat,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplayResult {
    pub fills: Vec<FillOut>,
    pub trades: Vec<TradeOut>,
    pub open_trade: Option<TradeOut>,
    pub skips: Vec<SkipOut>,
    pub quote_count: usize,
    #[serde(skip_serializing_if = "Option::is_none", default)]
    pub equity: Option<EquityOut>,
}

/// Serde bridge for `Rat` so the engine state can be persisted and restored.
mod rat_serde {
    use super::Rat;
    use serde::{Deserialize, Deserializer, Serialize, Serializer};

    #[derive(Serialize, Deserialize)]
    struct RatRepr {
        n: String,
        d: String,
    }

    pub fn serialize<S: Serializer>(value: &Rat, serializer: S) -> Result<S::Ok, S::Error> {
        RatRepr {
            n: value.n.to_string(),
            d: value.d.to_string(),
        }
        .serialize(serializer)
    }

    pub fn deserialize<'de, D: Deserializer<'de>>(deserializer: D) -> Result<Rat, D::Error> {
        let repr = RatRepr::deserialize(deserializer)?;
        Ok(Rat {
            n: repr.n.parse().map_err(serde::de::Error::custom)?,
            d: repr.d.parse().map_err(serde::de::Error::custom)?,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Position {
    side: Side,
    entry_price: i64,
    entry_ts: i64,
    entry_qi: usize,
    stop: i64,
    target: i64,
    price_scale: i64,
    #[serde(with = "rat_serde")]
    requested: Rat,
    #[serde(with = "rat_serde")]
    cost: Rat,
    #[serde(with = "rat_serde")]
    entered: Rat,
    #[serde(with = "rat_serde")]
    exited: Rat,
    #[serde(with = "rat_serde")]
    realized_exact: Rat,
    #[serde(with = "rat_serde")]
    commission_per_unit: Rat,
    #[serde(with = "rat_serde")]
    equity_at_entry: Rat,
    flags: Vec<String>,
    order_states: Vec<(String, String, Option<String>)>,
    exit_roles: Vec<String>,
    safety_pending: bool,
    exit_fills: Vec<ExitFillRecord>,
}

impl Position {
    fn quantity(&self) -> Rat {
        self.entered.sub(&self.exited)
    }

    /// Whether the order with the given role is still resting (submitted and
    /// not yet terminated). Cancelled protection cannot fill.
    fn order_active(&self, role: &str) -> bool {
        self.order_states
            .iter()
            .any(|(_, order_role, terminal)| order_role == role && terminal.is_none())
    }

    /// Set the terminal state of the order with the given role.
    fn terminate(&mut self, role: &str, status: &str) {
        for order in self.order_states.iter_mut() {
            if order.1 == role {
                order.2 = Some(status.to_string());
            }
        }
    }

    /// Register a resting order for the given role.
    fn register(&mut self, role: &str) {
        if !self.order_states.iter().any(|o| o.1 == role) {
            self.order_states.push((
                format!("{role}-{}", self.order_states.len()),
                role.to_string(),
                None,
            ));
        }
    }

    fn order_states_out(&self) -> Vec<OrderStateOut> {
        let mut out: Vec<OrderStateOut> = self
            .order_states
            .iter()
            .map(|(_, role, terminal)| OrderStateOut {
                role: role.clone(),
                terminal: terminal.clone(),
            })
            .collect();
        out.sort_by(|a, b| a.role.cmp(&b.role));
        out
    }

    fn apply_fill(
        &mut self,
        price: i64,
        size: &Rat,
        _order_side: Side,
        conv: Rat,
        role: &str,
    ) -> Rat {
        let scale = Rat::int(self.price_scale as i128);
        let price_dec = Rat::int(price as i128).div(&scale);
        // The reference charges the configured per-unit commission on every fill,
        // entry and exit alike, denominated in the instrument's quote currency.
        let fee = self.commission_per_unit.mul(size).mul(&conv);
        let delta;
        if role == "ENTRY" {
            self.cost = self.cost.add(&size.mul(&price_dec));
            self.entered = self.entered.add(size);
            delta = Rat::zero();
        } else {
            self.exit_fills.push(ExitFillRecord {
                price_int: price,
                size: size.clone(),
            });
            let sign = if self.side == Side::Buy {
                Rat::int(1)
            } else {
                Rat::int(-1)
            };
            if size.cmp(&self.quantity()) == Ordering::Equal {
                delta = price_dec.mul(size).sub(&self.cost).mul(&sign);
                self.cost = Rat::zero();
            } else {
                let basis = self.cost.div(&self.quantity());
                delta = price_dec.sub(&basis).mul(size).mul(&sign);
                self.cost = self.cost.sub(&basis.mul(size));
            }
            self.exited = self.exited.add(size);
        }
        let delta = delta.sub(&fee);
        let account_delta = delta.mul(&conv);
        self.realized_exact = self.realized_exact.add(&account_delta);
        account_delta
    }

    fn to_trade(
        &self,
        exit_ts: Option<i64>,
        exit_qi: Option<usize>,
        _exit_price: Option<i64>,
        _reason: Option<String>,
        _equity_after: &Rat,
    ) -> TradeOut {
        TradeOut {
            side: self.side.as_str().to_string(),
            entry_ts: self.entry_ts,
            entry_qi: self.entry_qi,
            exit_ts,
            exit_qi,
            entry_price_int: self.entry_price,
            exit_price_int: {
                let closed = !self.entered.is_zero() && self.quantity().is_zero();
                let total: Rat = self
                    .exit_fills
                    .iter()
                    .fold(Rat::zero(), |a, record| a.add(&record.size));
                if !closed || total.is_zero() {
                    None
                } else {
                    // The reference aggregates a multi-fill exit into a
                    // quantity-weighted average price.
                    let weighted: Rat = self.exit_fills.iter().fold(Rat::zero(), |a, record| {
                        a.add(&Rat::int(record.price_int as i128).mul(&record.size))
                    });
                    Some(weighted.div(&total).floor().to_i64().unwrap_or(0))
                }
            },
            stop_int: self.stop,
            target_int: self.target,
            flags: self.flags.clone(),
            exit_reason: {
                let mut reasons = self.exit_roles.clone();
                reasons.sort();
                reasons.dedup();
                let closed = !self.entered.is_zero() && self.quantity().is_zero();
                if !closed {
                    None
                } else if reasons.len() == 1 {
                    Some(reasons[0].clone())
                } else {
                    Some("MIXED".to_string())
                }
            },
            exit_reasons: {
                let closed = !self.entered.is_zero() && self.quantity().is_zero();
                let mut reasons = self.exit_roles.clone();
                reasons.sort();
                reasons.dedup();
                if closed {
                    reasons
                } else {
                    Vec::new()
                }
            },
            order_states: self.order_states_out(),
            pnl_num: "0".to_string(),
            pnl_den: "1".to_string(),
            entered_num: self.entered.n.to_string(),
            entered_den: self.entered.d.to_string(),
            requested_num: self.requested.n.to_string(),
            requested_den: self.requested.d.to_string(),
        }
    }
}

/// One quote of sequential exact replay: matching phase, deadline close, safety
/// close and signal evaluation, in the reference's per-quote order.
#[allow(clippy::too_many_arguments)]
fn step_impl(
    profile: &Profile,
    spec: &Spec,
    signals: &[Signal],
    conservative: bool,
    i: usize,
    q: &Quote,
    equity: &mut Rat,
    open: &mut Option<Position>,
    sig_idx: &mut usize,
    fills: &mut Vec<FillOut>,
    trades: &mut Vec<TradeOut>,
    skips: &mut Vec<SkipOut>,
    equity_log: &mut Vec<EquityRecord>,
    emit_equity: bool,
) -> Result<(), String> {
    let (b, a) = effective_quotes(q.bid, q.ask, profile, conservative)?;

    // (a) Matching phase. Resting protection is evaluated against this
    //     quote. Protection that has passed its deadline was already
    //     cancelled by the clock alert, so it cannot fill here.
    if let Some(mut pos) = open.take() {
        let deadline = pos.entry_ts + spec.max_hold_seconds * NANOS;
        let exit = if q.ts >= deadline
            || !pos.order_active("STOP_LOSS") && !pos.order_active("TAKE_PROFIT")
        {
            None
        } else if pos.side == Side::Buy {
            if b <= pos.stop && pos.order_active("STOP_LOSS") {
                Some((
                    eligible_price(b, Side::Sell, OrderType::StopMarket, profile, conservative),
                    "STOP_LOSS",
                ))
            } else if b >= pos.target && pos.order_active("TAKE_PROFIT") {
                Some((b, "TAKE_PROFIT"))
            } else {
                None
            }
        } else if a >= pos.stop && pos.order_active("STOP_LOSS") {
            Some((
                eligible_price(a, Side::Buy, OrderType::StopMarket, profile, conservative),
                "STOP_LOSS",
            ))
        } else if a <= pos.target && pos.order_active("TAKE_PROFIT") {
            Some((a, "TAKE_PROFIT"))
        } else {
            None
        };
        if let Some((price, role)) = exit {
            let exit_side = pos.side.flip();
            let conv = conversion_rate(profile, b, a, exit_side)?;
            let qty = pos.quantity();
            let avail = order_quantity(profile, &qty, &spec.partial, role, exit_side);
            let delta = pos.apply_fill(price, &avail, exit_side, conv, role);
            *equity = equity.add(&delta).round_sig28();
            pos.exit_roles.push(role.to_string());
            fills.push(FillOut {
                role: role.into(),
                ts: q.ts,
                qi: i,
                side: exit_side.as_str().to_string(),
                price_int: price,
                size_num: avail.n.to_string(),
                size_den: avail.d.to_string(),
            });
            if avail.cmp(&qty) == Ordering::Less {
                // A partial protection fill cancels the order remainder and
                // its sibling; the position stays open for a safety close.
                pos.terminate(role, "CANCELED");
                pos.terminate(
                    if role == "STOP_LOSS" {
                        "TAKE_PROFIT"
                    } else {
                        "STOP_LOSS"
                    },
                    "CANCELED",
                );
                if !pos.flags.iter().any(|f| f == "PROTECTION_LOST") {
                    pos.flags.push("PROTECTION_LOST".into());
                }
                pos.safety_pending = true;
                *open = Some(pos);
            } else {
                pos.terminate(role, "FILLED");
                pos.terminate(
                    if role == "STOP_LOSS" {
                        "TAKE_PROFIT"
                    } else {
                        "STOP_LOSS"
                    },
                    "CANCELED",
                );
                let mut t =
                    pos.to_trade(Some(q.ts), Some(i), Some(price), Some(role.into()), equity);
                if emit_equity {
                    equity_log.push(EquityRecord {
                        entry_ts: pos.entry_ts,
                        exit_ts: Some(q.ts),
                        before: pos.equity_at_entry.clone(),
                        after: equity.round_sig28(),
                    });
                }
                t.pnl_num = pos.account_realized().n.to_string();
                t.pnl_den = pos.account_realized().d.to_string();
                trades.push(t);
            }
        } else {
            *open = Some(pos);
        }
    }

    // (b) Strategy callback. A deadline close submits a market exit that
    //     fills immediately against the current quote, updating equity
    //     before any new position is sized at this same quote.
    if let Some(mut pos) = open.take() {
        let deadline = pos.entry_ts + spec.max_hold_seconds * NANOS;
        if q.ts >= deadline {
            let exit_side = pos.side.flip();
            let book = if pos.side == Side::Buy { b } else { a };
            let price = eligible_price(book, exit_side, OrderType::Market, profile, conservative);
            let conv = conversion_rate(profile, b, a, exit_side)?;
            let qty = pos.quantity();
            let avail = order_quantity(profile, &qty, &spec.partial, "TIMEOUT", exit_side);
            let delta = pos.apply_fill(price, &avail, exit_side, conv, "TIMEOUT");
            *equity = equity.add(&delta).round_sig28();
            pos.exit_roles.push("TIMEOUT".to_string());
            pos.terminate("STOP_LOSS", "CANCELED");
            pos.terminate("TAKE_PROFIT", "CANCELED");
            pos.register("TIMEOUT");
            let flag = if q.ts == deadline {
                "TIMEOUT"
            } else {
                "DELAYED_TIMEOUT_QUOTE"
            };
            if !pos.flags.iter().any(|f| f == flag) {
                pos.flags.push(flag.to_string());
            }
            fills.push(FillOut {
                role: "TIMEOUT".into(),
                ts: q.ts,
                qi: i,
                side: exit_side.as_str().to_string(),
                price_int: price,
                size_num: avail.n.to_string(),
                size_den: avail.d.to_string(),
            });
            if avail.cmp(&qty) == Ordering::Less {
                // The exit remainder is cancelled and the position stays
                // open; a later quote submits a fresh exit order.
                pos.terminate("TIMEOUT", "CANCELED");
                *open = Some(pos);
            } else {
                pos.terminate("TIMEOUT", "FILLED");
                let mut t = pos.to_trade(
                    Some(q.ts),
                    Some(i),
                    Some(price),
                    Some("TIMEOUT".into()),
                    equity,
                );
                if emit_equity {
                    equity_log.push(EquityRecord {
                        entry_ts: pos.entry_ts,
                        exit_ts: Some(q.ts),
                        before: pos.equity_at_entry.clone(),
                        after: equity.round_sig28(),
                    });
                }
                t.pnl_num = pos.account_realized().n.to_string();
                t.pnl_den = pos.account_realized().d.to_string();
                trades.push(t);
            }
        } else {
            *open = Some(pos);
        }
    }

    // (b2) Safety close: protection was lost, so the remaining position is
    //      exited at the current executable quote.
    if let Some(mut pos) = open.take() {
        if pos.safety_pending {
            let exit_side = pos.side.flip();
            let book = if pos.side == Side::Buy { b } else { a };
            let price = eligible_price(book, exit_side, OrderType::Market, profile, conservative);
            let conv = conversion_rate(profile, b, a, exit_side)?;
            let qty = pos.quantity();
            let avail = order_quantity(profile, &qty, &spec.partial, "SAFETY_CLOSE", exit_side);
            let delta = pos.apply_fill(price, &avail, exit_side, conv, "SAFETY_CLOSE");
            *equity = equity.add(&delta).round_sig28();
            pos.exit_roles.push("SAFETY_CLOSE".into());
            pos.safety_pending = false;
            if !pos.flags.iter().any(|f| f == "SAFETY_CLOSE") {
                pos.flags.push("SAFETY_CLOSE".into());
            }
            pos.register("SAFETY_CLOSE");
            pos.terminate("SAFETY_CLOSE", "FILLED");
            fills.push(FillOut {
                role: "SAFETY_CLOSE".into(),
                ts: q.ts,
                qi: i,
                side: exit_side.as_str().to_string(),
                price_int: price,
                size_num: avail.n.to_string(),
                size_den: avail.d.to_string(),
            });
            if pos.quantity().is_zero() {
                let mut t = pos.to_trade(
                    Some(q.ts),
                    Some(i),
                    Some(price),
                    Some("SAFETY_CLOSE".into()),
                    equity,
                );
                if emit_equity {
                    equity_log.push(EquityRecord {
                        entry_ts: pos.entry_ts,
                        exit_ts: Some(q.ts),
                        before: pos.equity_at_entry.clone(),
                        after: equity.round_sig28(),
                    });
                }
                t.pnl_num = pos.account_realized().n.to_string();
                t.pnl_den = pos.account_realized().d.to_string();
                trades.push(t);
            } else {
                *open = Some(pos);
            }
        } else {
            *open = Some(pos);
        }
    }

    // (c) Signals: eligible once available_at is strictly before the quote.
    while *sig_idx < signals.len() && signals[*sig_idx].available_at < q.ts {
        let sig_side = signals[*sig_idx].side.into();
        *sig_idx += 1;
        if open.is_some() {
            skips.push(SkipOut {
                ts: q.ts,
                status: "SKIPPED_OVERLAP".into(),
            });
            continue;
        }
        let allowed = match spec.direction {
            Direction::Both => true,
            Direction::Long => sig_side == Side::Buy,
            Direction::Short => sig_side == Side::Sell,
        };
        if !allowed {
            continue;
        }
        let book = if sig_side == Side::Buy { a } else { b };
        let entry = eligible_price(book, sig_side, OrderType::Market, profile, conservative);
        let sign = if sig_side == Side::Buy { 1 } else { -1 };
        let distance = spec.stop_ticks * profile.tick_int;
        let stop = entry - sign * distance;
        let target = entry + sign * distance * spec.target_rr;
        if stop <= 0 || target <= 0 {
            skips.push(SkipOut {
                ts: q.ts,
                status: "SKIPPED_PRICE_LEVEL".into(),
            });
            continue;
        }
        let liquidation = if sig_side == Side::Buy { b } else { a };
        if (liquidation - stop) * sign < profile.min_stop_ticks * profile.tick_int {
            skips.push(SkipOut {
                ts: q.ts,
                status: "SKIPPED_STOP_LEVEL".into(),
            });
            continue;
        }
        let risk_side = if sig_side == Side::Buy {
            Side::Sell
        } else {
            Side::Buy
        };
        let risk_conversion = conversion_rate(profile, b, a, risk_side)?;
        let sizing = size_position(
            equity.clone(),
            entry,
            stop,
            profile,
            risk_conversion,
            conservative,
        )?;
        let size = match sizing {
            SizeResult::Eligible { size, .. } => size,
            SizeResult::SkippedStopLevel => {
                skips.push(SkipOut {
                    ts: q.ts,
                    status: "SKIPPED_STOP_LEVEL".into(),
                });
                continue;
            }
            SizeResult::SkippedMinVolume => {
                skips.push(SkipOut {
                    ts: q.ts,
                    status: "SKIPPED_MIN_VOLUME".into(),
                });
                continue;
            }
            SizeResult::SkippedMargin => {
                skips.push(SkipOut {
                    ts: q.ts,
                    status: "SKIPPED_MARGIN".into(),
                });
                continue;
            }
        };
        let native_size = size.mul(&profile.contract_multiplier);
        let conv = conversion_rate(profile, b, a, sig_side)?;
        let mut pos = Position {
            side: sig_side,
            entry_price: entry,
            entry_ts: q.ts,
            entry_qi: i,
            stop,
            target,
            price_scale: profile.price_scale,
            requested: native_size.clone(),
            cost: Rat::zero(),
            entered: Rat::zero(),
            exited: Rat::zero(),
            realized_exact: Rat::zero(),
            commission_per_unit: profile.commission_per_unit.clone(),
            equity_at_entry: equity.round_sig28(),
            flags: Vec::new(),
            order_states: Vec::new(),
            exit_roles: Vec::new(),
            safety_pending: false,
            exit_fills: Vec::new(),
        };
        pos.register("ENTRY");
        pos.register("STOP_LOSS");
        pos.register("TAKE_PROFIT");
        let avail = order_quantity(profile, &native_size, &spec.partial, "ENTRY", sig_side);
        pos.apply_fill(entry, &avail, sig_side, conv, "ENTRY");
        fills.push(FillOut {
            role: "ENTRY".into(),
            ts: q.ts,
            qi: i,
            side: sig_side.as_str().to_string(),
            price_int: entry,
            size_num: avail.n.to_string(),
            size_den: avail.d.to_string(),
        });
        if avail.cmp(&native_size) == Ordering::Less {
            // The IOC remainder is cancelled, and cancelling the parent
            // order cancels the attached protection (order group).
            pos.terminate("ENTRY", "CANCELED");
            pos.terminate("STOP_LOSS", "CANCELED");
            pos.terminate("TAKE_PROFIT", "CANCELED");
            if !pos.flags.iter().any(|f| f == "PROTECTION_LOST") {
                pos.flags.push("PROTECTION_LOST".into());
            }
            pos.safety_pending = true;
        } else {
            pos.terminate("ENTRY", "FILLED");
        }
        *open = Some(pos);
    }

    Ok(())
}

/// Persisted engine state: everything needed to resume a replay at a quote
/// boundary. The state is a pure function of the quotes consumed.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplayerState {
    #[serde(with = "rat_serde")]
    equity: Rat,
    #[serde(default)]
    equity_log: Vec<EquityRecord>,
    #[serde(with = "rat_serde")]
    initial_equity: Rat,
    open: Option<Position>,
    sig_idx: usize,
    index: usize,
    fills: Vec<FillOut>,
    trades: Vec<TradeOut>,
    skips: Vec<SkipOut>,
}

/// Resumable sequential replay. `step` advances one quote; `state`/`restore`
/// split a run at any quote boundary without changing the result, which is the
/// restart and batch-size evidence the migration gate requires.
pub struct Replayer<'a> {
    profile: &'a Profile,
    spec: &'a Spec,
    signals: &'a [Signal],
    conservative: bool,
    emit_equity: bool,
    state: ReplayerState,
}

impl<'a> Replayer<'a> {
    pub fn new(
        profile: &'a Profile,
        spec: &'a Spec,
        signals: &'a [Signal],
        conservative: bool,
        emit_equity: bool,
    ) -> Self {
        Replayer {
            profile,
            spec,
            signals,
            conservative,
            emit_equity,
            state: ReplayerState {
                equity: Rat::int(20),
                equity_log: Vec::new(),
                initial_equity: Rat::int(20),
                open: None,
                sig_idx: 0,
                index: 0,
                fills: Vec::new(),
                trades: Vec::new(),
                skips: Vec::new(),
            },
        }
    }

    pub fn step(&mut self, q: &Quote) -> Result<(), String> {
        let i = self.state.index;
        self.state.index += 1;
        step_impl(
            self.profile,
            self.spec,
            self.signals,
            self.conservative,
            i,
            q,
            &mut self.state.equity,
            &mut self.state.open,
            &mut self.state.sig_idx,
            &mut self.state.fills,
            &mut self.state.trades,
            &mut self.state.skips,
            &mut self.state.equity_log,
            self.emit_equity,
        )
    }

    pub fn finish(self) -> ReplayResult {
        let mut equity_log = self.state.equity_log.clone();
        let mut open_trade = None;
        if let Some(pos) = self.state.open.as_ref() {
            let mut t = pos.to_trade(None, None, None, None, &self.state.equity);
            t.pnl_num = pos.account_realized().n.to_string();
            t.pnl_den = pos.account_realized().d.to_string();
            if !t.flags.iter().any(|f| f == "NO_EXECUTABLE_EXIT_QUOTE") {
                t.flags.push("NO_EXECUTABLE_EXIT_QUOTE".into());
            }
            if self.emit_equity {
                equity_log.push(EquityRecord {
                    entry_ts: pos.entry_ts,
                    exit_ts: None,
                    before: pos.equity_at_entry.clone(),
                    after: self.state.equity.round_sig28(),
                });
            }
            open_trade = Some(t);
        }
        ReplayResult {
            fills: self.state.fills,
            trades: self.state.trades,
            open_trade,
            skips: self.state.skips,
            quote_count: self.state.index,
            equity: if self.emit_equity {
                Some(EquityOut {
                    trades: equity_log,
                    ending_equity: self.state.equity.round_sig28(),
                    initial_equity: self.state.initial_equity.clone(),
                })
            } else {
                None
            },
        }
    }

    pub fn state(&self) -> ReplayerState {
        self.state.clone()
    }

    pub fn restore(
        state: ReplayerState,
        profile: &'a Profile,
        spec: &'a Spec,
        signals: &'a [Signal],
        conservative: bool,
        emit_equity: bool,
    ) -> Self {
        Replayer {
            profile,
            spec,
            signals,
            conservative,
            emit_equity,
            state,
        }
    }
}

/// Sequential exact quote replay with engine-managed brackets and one open
/// position. This is the authoritative fallback execution mode.
pub fn replay(
    profile: &Profile,
    spec: &Spec,
    quotes: &[Quote],
    signals: &[Signal],
    conservative: bool,
) -> Result<ReplayResult, String> {
    let mut replayer = Replayer::new(profile, spec, signals, conservative, false);
    for q in quotes {
        replayer.step(q)?;
    }
    Ok(replayer.finish())
}

impl Position {
    fn account_realized(&self) -> Rat {
        self.realized_exact.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    pub fn usdchf_in() -> ProfileIn {
        ProfileIn {
            instrument: "USDCHF".into(),
            tick_size: "0.00001".into(),
            pip_size: "0.00010".into(),
            price_scale: 100000,
            base_currency: "USD".into(),
            quote_currency: "CHF".into(),
            contract_multiplier: "1".into(),
            volume_step: "0.001".into(),
            min_volume: "0.001".into(),
            max_volume: "100000".into(),
            margin_rate: "0.001".into(),
            min_stop_ticks: 1,
            commission_per_unit: "0".into(),
        }
    }

    fn usdchf() -> Profile {
        Profile::from_input(&usdchf_in()).unwrap()
    }

    pub fn position(profile: &Profile, side: Side) -> Position {
        Position {
            side,
            entry_price: 95063,
            entry_ts: 1,
            entry_qi: 0,
            stop: 94863,
            target: 95663,
            price_scale: profile.price_scale,
            requested: Rat::int(1000),
            cost: Rat::zero(),
            entered: Rat::zero(),
            exited: Rat::zero(),
            realized_exact: Rat::zero(),
            commission_per_unit: profile.commission_per_unit.clone(),
            equity_at_entry: Rat::int(20),
            flags: Vec::new(),
            order_states: Vec::new(),
            exit_roles: Vec::new(),
            safety_pending: false,
            exit_fills: Vec::new(),
        }
    }

    #[test]
    fn usdchf_buy_sizing_matches_reference() {
        let profile = usdchf();
        let conv = conversion_rate(&profile, 95022, 95043, Side::Sell).unwrap();
        let result = size_position(Rat::int(20), 95063, 94863, &profile, conv, true).unwrap();
        match result {
            SizeResult::Eligible { size, margin, .. } => {
                assert_eq!(size.n.to_string(), "864027");
                assert_eq!(size.d.to_string(), "1000");
                assert!(margin.cmp(&Rat::int(20)) == Ordering::Less);
            }
            other => panic!("expected eligible, got {other:?}"),
        }
    }

    #[test]
    fn commission_is_charged_on_entry_and_exit() {
        // A per-unit commission is charged on every fill, entry and exit alike,
        // in the instrument's quote currency, matching the reference ledger.
        let mut input = usdchf_in();
        input.commission_per_unit = "1".into();
        let profile = Profile::from_input(&input).unwrap();
        let conv = Rat::int(1);
        let size = Rat::int(1000);
        let mut pos = position(&profile, Side::Buy);
        let entry_delta = pos.apply_fill(95063, &size, Side::Buy, conv.clone(), "ENTRY");
        assert_eq!(entry_delta.n.to_string(), "-1000");
        assert_eq!(entry_delta.d.to_string(), "1");
        pos.apply_fill(95163, &size, Side::Sell, conv, "STOP_LOSS");
        assert_eq!(pos.realized_exact.n.to_string(), "-1999");
        assert_eq!(pos.realized_exact.d.to_string(), "1");
    }

    #[test]
    fn decimal28_rounding_matches_reference() {
        // 2 / 0.002314741... must round to 28 significant digits, half-even.
        let value = Rat::int(2).div(&Rat::int(2314741)).mul(&Rat::int(1000000));
        let rounded = value.round_sig28();
        assert_eq!(rounded.d.to_string().len() - 1, 27);
    }
}

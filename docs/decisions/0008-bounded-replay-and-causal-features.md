# Bounded replay, causal features and accounting checks

Status: development increment; NOT_READY. No scientific cost/risk change.

Closed bars now keep a rolling midpoint close/high/low instead of a per-tick list.
One source pass updates all requested timeframes; bounded history and monotonic
higher-bar publication queues retain the previous compiler's end/available-at
rules. Fixture reference tests cover sparse gaps and equal timestamps. Execution
still requires available_at < execution timestamp, so a quote and its timestamp
ties cannot execute information that quote published. No unobserved candle is
fabricated. Feature identity describes bars separately from strategy stops/risk;
indicator identity adds its exact operator/parameters/version. L2 sharing and
incremental cross-partition caches remain unfinished.

Production worker/evaluation no longer materialize entire quote and tick arrays.
Canonical reads use bounded Arrow batches, half-open window predicates and
Parquet statistics pruning. A transient reversible numeric disk spool (32 bytes
per source quote) validates units/order/grid before engine delivery and supplies
forensic ranges. The spool is removed on success or exception; it is not a new
canonical data format. Temporary disk allowance is capped at 4 GiB with a 256 MiB
free-space reserve. Large jobs exceeding the allowance fail explicitly and must
be partitioned by a future checkpoint-aware scheduler, never silently shortened.

Nautilus 1.231.0's supported add_data_iterator drives a single event loop across
bounded chunks. Repeated engine.run calls at arbitrary chunks could flush timers
between equal-time quotes; the single native iterator avoids that change. Start
and end bounds are explicit, and the received quote count must match input.
Memory/reference mode is private test/benchmark-only, not accepted worker input.
Tests compare full outputs for batches of 1/2/3/8192, including deadline/tie/gap
boundaries, partials and open censored trades.

Production diagnostic output stores exact summaries plus canonical-path/v1 source
hash/row references and ordered fills. Original quotes remain lossless. Inline
paths are a small-fixture compatibility interface capped at 100,000 points/trade.
Reconstruction streams the original executable-side quotes and fill-specific basis;
no path interpolation. Native/Factory records remain bounded by explicit 50,000
record limits; overflow fails the job, rather than dropping failed attempts.
These are engineering admission limits, not performance-based scientific screens.
An actual 8-GB cgroup/Contabo stress and multi-day soak is still required.

Independent cash/inventory reconciliation compares native position lifetimes,
order/trade fill IDs/quantities/prices/fees, signed inventory, native account and
position realized totals, Factory exact cash and equity. Any unexplained mismatch
is an integrity failure. Native USD Money uses rounded floating-point calculations;
its balance is displayed separately from exact Decimal hypothetical equity. A
nonzero native-minus-exact residual is explicitly DIFFERENCE_REQUIRES_POLICY,
not claimed exact account parity. Supported USD fixture accounting is improved;
real monetary evaluation remains blocked pending the currency-rounding/profile
contract. No Gold/JPY monetary convention is invented or approved.

feed_probe is a developer-only real-source native delivery test with NO signals,
orders, objectives or official experiments. It uses observed source price geometry
and unused fixture monetary scaffolding, never a verified broker profile. It
counts zero full strategy replays. Its resource measurements cannot satisfy real
strategy throughput, profitability, full C3 or target-host gates.

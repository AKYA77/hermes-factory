# ADR 0014 — Persistent managed holdout influence and execution

Authority: blueprint §§10.1–10.4 and the owner's final end-to-end mandate.
No risk/cost/ranking/split default is changed. Window boundaries are explicit
owner-supplied immutable inputs. This is a scientific enforcement foundation;
it does not by itself establish independent validation or SOFTWARE_VERIFIED.

Migration 005 adds immutable input-use, holdout, frozen-selection, consumption and
evaluation-result ledgers. Holdout protection applies to instrument/evidence-kind
and absolute half-open time spans across dataset aliases, views and revisions.
Synthetic and historical universes are separate. Reservation rejects prior
managed input uses and pre-migration protocol/job/experiment influences. It
requires a recorded external-use declaration; the software cannot certify that
an OS user never inspected a file outside the managed application. An already
observed period cannot be relabeled unseen by changing its dataset hash.

Training registration, enqueue, worker execution and registry completion enforce
the protection. Fixed-window evaluation records all actual past-only feature
warm-up spans, not merely scored entry spans. Direct unprotected exploratory OOS
runs remain explicitly uncontrolled and cannot promote a strategy. Protected
confirmation requires a single matching final window, a frozen verified preceding
training candidate and its exact consumed authorization. All native evidence
continues to come from Nautilus, on the existing exact source/execution contract.

Consumption is durable before the evaluation starts. A crash or failed attempt
never restores unseen status. Recovery may enqueue/retrieve/replay only the same
frozen experiment and observation identity; this adds no independent sample.
Another candidate cannot replace the selection. Failures and consumption survive
restart. Structural source verification is not counted as strategy information;
research/compiler input use is. Multiple final reservations with intervening
protected warm-up data fail conservatively rather than granting cross-holdout
access. Later reporting authorization must be explicit and separately labeled.

The existing supervised, fenced, memory/wall-limited coordinator now also runs
validation workers. Immutable evaluation artifacts/results are separate from
training experiments and optimizer feedback; no API accepts their metrics.
CLI/API reserve/freeze/enqueue/status/detail use actual registry data and existing
operator/viewer roles. Historical monetary/profile gates remain unchanged.
Complete WFO refitting, annual/pooled reporting, sensitivity/multiple testing and
validation promotion are the next integrated work, not waived by this increment.

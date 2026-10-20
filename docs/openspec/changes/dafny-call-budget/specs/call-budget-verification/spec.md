## ADDED Requirements

### Requirement: exact per-grant budget model

The experiment SHALL define an independent Dafny model of one grant with a
fixed positive limit, a nonnegative used-call counter and active state. It SHALL
model atomic request and deactivation transitions and retain exhausted states
in the verified domain. Other eligibility checks SHALL be explicit assumptions.

#### Scenario: eligible request below the limit

- GIVEN an active grant, an eligible request and `used < limit`
- WHEN the modeled request transition occurs
- THEN it is allowed and the counter increases by exactly one
- AND the limit and active state are unchanged

#### Scenario: denial preserves the budget

- GIVEN the grant is inactive, the request is ineligible or `used = limit`
- WHEN the modeled request transition occurs
- THEN it is denied and the counter, limit and active state are unchanged

#### Scenario: deactivation prevents later authorization

- GIVEN any reachable modeled state
- WHEN deactivation occurs and any finite sequence of requests follows
- THEN deactivation leaves the counter unchanged
- AND every subsequent request is denied without consuming budget

### Requirement: proof and negative control

The experiment SHALL prove initialization, transition preservation and the
finite-sequence invariant that the counter equals the number of authorized
requests and does not exceed the limit. It SHALL retain one incorrect guard
variant, changing only `<` to `<=` while preserving the contract.

#### Scenario: valid model has complete verification evidence

- GIVEN the recorded model and pinned Dafny toolchain
- WHEN the verification target runs
- THEN all declared properties are verified without assuming the conclusions,
  leaving proof stubs or disabling verification
- AND input eligibility and atomicity remain explicit boundary assumptions
- AND source hashes, tool versions, commands and diagnostics are retained

#### Scenario: boundary violation is detected

- GIVEN the incorrect guard and the witness `used = limit = 1`
- WHEN the negative control is verified against the unchanged contract
- THEN the expected budget obligation fails
- AND missing tooling, parsing errors, crashes and timeouts cannot count as
  successful detection of that violation

### Requirement: honest comparison with runtime tests

The experiment SHALL compare the formal properties with current Python gateway
tests and behavior tests for denial accounting and authorized operation failure.
It SHALL distinguish a proof of the abstract model from tests of the runtime.

#### Scenario: Python accounting is characterized

- GIVEN an isolated local gateway and a fixed grant budget
- WHEN authorization is denied before dispatch
- THEN a behavior test confirms that no call slot is consumed
- AND another behavior test confirms that an authorized operation returning
  an execution error still consumes its slot

#### Scenario: evidence claims stay within the boundary

- GIVEN a verified model and passing runtime tests
- WHEN observations are documented
- THEN the report names the properties, assumptions and Python correspondence gap
- AND makes no claim of a verified database, race-free deployment, run-wide cap,
  cancellation of admitted work or hallucination-free model
- AND raw evidence remains under ignored `.lab/experiments/call-budget-dafny/`

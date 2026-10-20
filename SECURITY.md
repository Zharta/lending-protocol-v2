# Security policy

Zharta runs a bug bounty for the deployed smart contracts listed under
**Scope**. This policy covers smart contracts only.

## Reporting

Email **security@zharta.com**. It is the only channel for vulnerability reports;
reports sent to other addresses may not reach us. Include:

- the affected contract, chain and address;
- a description of the issue and its impact;
- your severity assessment (see **Severity**);
- a proof of concept that runs on a local fork (required for Critical and High).

Do not disclose the issue publicly or to third parties until we confirm it is
resolved or agree to disclosure in writing.

## Scope

Deployed instances of the contracts below, at the addresses in
[`configs/prod/`](configs/prod/) (`p2p.json` for each chain).

| Contract | Source | Chains |
|---|---|---|
| P2PLendingNfts | `contracts/P2PLendingNfts.vy` | Ethereum, ApeChain, Robinhood Chain |
| P2PLendingControl | `contracts/P2PLendingControl.vy` | Ethereum, ApeChain, Robinhood Chain |

Anything else is out of scope. That includes:

- `LenderClaim`, which is no longer in use;
- `ArcadeProxy`, whose deployed instances are not authorized on the lending
  contracts;
- contracts with no production entry in `configs/prod/` (`BendDAOProxy`,
  `NftfiProxy`, `GondiProxy`, `AaveFlash`, `EIP3156Flash`).

## Severity

We classify severity with the [Immunefi Vulnerability Severity Classification
System v2.3](https://immunefi.com/immunefi-vulnerability-severity-classification-system-v2-3/)
for smart contracts. Severity is judged by the impact on the in-scope deployed
contracts at the time of the report. Issues that require elevated privileges or
uncommon user interaction may be downgraded or rejected.

**Critical**
- Manipulation of governance voting result deviating from voted outcome and
  resulting in a direct change from intended effect of original results
- Direct theft of any user funds, whether at-rest or in-motion, other than
  unclaimed yield
- Direct theft of any user NFTs, whether at-rest or in-motion, other than
  unclaimed royalties
- Permanent freezing of funds
- Permanent freezing of NFTs
- Unauthorized minting of NFTs
- Predictable or manipulable RNG that results in abuse of the principal or NFT
- Unintended alteration of what the NFT represents (e.g. token URI, payload,
  artistic content)
- Protocol insolvency

**High**
- Theft of unclaimed yield
- Theft of unclaimed royalties
- Permanent freezing of unclaimed yield
- Permanent freezing of unclaimed royalties
- Temporary freezing of funds
- Temporary freezing NFTs

**Medium**
- Smart contract unable to operate due to lack of token funds
- Block stuffing
- Griefing (e.g. no profit motive for an attacker, but damage to the users or
  the protocol)
- Theft of gas
- Unbounded gas consumption

**Low**
- Contract fails to deliver promised returns, but doesn't lose value

## Rewards

Only **Critical** and **High** reports are eligible for a reward. Zharta sets
each amount case by case, based on severity and the funds at risk on the
deployed contracts at the time of the report. Medium, Low and informational
reports are acknowledged but not rewarded. Payment details are agreed with the
reporter when a reward is offered.

A report is eligible only if:

- it is the first valid report of the issue, by time of receipt at
  security@zharta.com;
- it affects an in-scope contract and includes a working proof of concept;
- the issue, or another with the same root cause, is not listed in
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md), not described in the audit reports in
  [`audits/`](audits/), and was not reported to us earlier by someone else (if
  it was, we tell you the date of the earlier report);
- the reporter followed the rules below.

## Out of scope

- Contracts not listed under **Scope**, including mocks under
  `contracts/auxiliary/`, tests, scripts and configuration files.
- Third-party contracts: tokens, NFT collections, price feeds, delegation
  registries, flash-loan providers and external protocols.
- Issues that require access to privileged keys or roles, or leaked
  credentials; centralization risks.
- Incorrect data supplied by third-party oracles (oracle manipulation remains in
  scope).
- Basic economic or governance attacks (e.g. 51%), lack of liquidity, Sybil
  attacks, and depegging of an external stablecoin that the attacker does not
  cause.
- Behaviour of third-party integrations built on these contracts.
- Best-practice recommendations, gas optimizations, code style and feature
  requests.
- Theoretical issues without a working proof of concept, and automated scanner
  output.
- Websites, apps, APIs and infrastructure. This policy covers smart contracts
  only.

## Rules

- Test only on local forks. Never test against mainnet or public testnets.
- Do not interact with other users' positions, funds or data.
- No denial of service, spam or high-volume automated testing against Zharta
  systems.
- No phishing or social engineering.
- No public disclosure before the issue is resolved (see **Reporting**).

Reports that break these rules are not eligible for a reward.

## Known issues

Closed reports are listed in [KNOWN_ISSUES.md](KNOWN_ISSUES.md). Findings in
the audit reports in [`audits/`](audits/) are known as well.

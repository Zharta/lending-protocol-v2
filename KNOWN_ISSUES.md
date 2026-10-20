# Known issues

These issues were reported to Zharta and are closed. They are not eligible for
a bug bounty reward, and neither is any issue with the same root cause.
Findings in the audit reports in [`audits/`](audits/) are known as well.

| ID | Component | Issue | Resolution | Reported |
|---|---|---|---|---|
| KI-01 | `P2PLendingNfts` | Offer signatures are not restricted to the canonical low-s form, and the offer id is derived from the raw signature. A second valid encoding of a signed offer is treated as a different offer. This affects single-use offer tracking and offer revocation. | Acknowledged, won't fix in the deployed contracts. | 2 Oct 2026 |
| KI-02 | `ArcadeProxy`, `BendDAOProxy`, `NftfiProxy`, `GondiProxy` | The flash-loan callback authenticates the flash-loan provider but doesn't check that the proxy started the loan, which exposes token approvals granted to the proxy. | Mitigated. The deployed `ArcadeProxy` instances are no longer authorized on the lending contracts; the other proxies are not deployed. | 14 Oct 2026 |
| KI-03 | `P2PLendingNfts.replace_loan_lender` | When the new principal doesn't cover the borrower's accrued interest and fees, the lender who calls the replacement forgoes the accrued interest and pays the borrower-broker fee. | By design. Only the current lender can call it, and all fees are known beforehand. | 14 Oct 2026 |

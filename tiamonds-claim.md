
1. Deploy the `lender_claim` in prod

```bash
make deploy-ethereum
```

2. Authorize the `lender_claim` delegation for the lender


```bash
export MAINNET_URL=...
export LENDER_PK=...
export DELEGATE_ADDRESS=0x12E2B70C57F966e190a7Eb661915dD4BEde536BD
cast send --private-key $LENDER_PK --rpc-url $MAINNET_URL 0x0000000000000000000000000000000000000000 --auth $DELEGATE_ADDRESS

```


3. Claim the collateral on ape console

```python
loan_id = "0x5697ef2836a9b308ff6e8ce7a02b702bcfbfc9e39ab960a512e53ee9e8e1a87a"
loan = get_loan(loan_id)
p2p_usdc_nfts.claim_defaulted_loan_collateral(loan, sender=lender)
```

4. Remove delegation

```bash
cast send --private-key $LENDER_PK --rpc-url $MAINNET_URL 0x0000000000000000000000000000000000000000 --auth 0x0000000000000000000000000000000000000000
```

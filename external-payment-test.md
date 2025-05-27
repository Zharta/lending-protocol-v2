# External payment test


## Wallets / contracts addresses


| **Name**                          | **Chain**        | **Address implementation**                   |
| ---                               | ---              | ---                                          |
| P2P lending contract              | curtis           | `0xBdbfa0fe1116B1770Bb2895235e3Ce0231dce931` |
| Lending pool                      | sepolia          | `0xf8fD741e0935b46cBD25a6dB78317Bd462898BA3` |
| Lender                            | curtis / sepolia | `0x00aA70B40A89aDF483f4068323789a64d791CCe5` |
| Escrow                            | curtis / sepolia | `0xF00C9AF0B4c9C7636e12c80E4f22D7d6FF219475` |
| Borrower                          | curtis / sepolia | `0x190Af7D087D32C61A2e23FB8aF192a58A6385DD1` |
| Operator                          | curtis / sepolia | `0x77672996cD93B722e5a5673D404C3A92AD8dd1Fd` |
| ERC721 (tokengators)              | curtis           | `0xB16A9612b91259ABA40862233e25f9685Ea0d738` |
| P2P lending contract token (WAPE) | curtis           | `0x69B5cfEfDd30467Ea985EBac1756d81EA871798c` |
| Payment token (USDC)              | sepolia          | `0x74540605Dc99f9cd65A3eA89231fFA727B1049E2` |


```
borrower = accounts.load("borrower")
lender = accounts.load("lender")
operator = accounts.load("operator")
escrow = accounts.load("escrow")
```

## Assets

* ERC721: tokengators 5
* Loan principal: 1000 WAPE
* Payment: 645 USDC

```
principal = int(1e21) # (1000 WAPE)
payment_amount = int(645e6) # (645 USDC)
token_id = 5
```

## Setup

```
# fund wallets
me.transfer(borrower, int(1e17))
me.transfer(escrow, int(1e17))
me.transfer(lender, int(1e17))
me.transfer(operator, int(1e17))
common_usdc.transfer(lender, payment_amount, sender=me)
common_wape.transfer(borrower, principal * 2, sender=me)

#send token to borrower
tokengators.transferFrom(me, borrower, token_id, sender=me)
assert tokengators.ownerOf(token_id) == borrower

# approve p2p contract to get tokens from escrow
tokengators.setApprovalForAll(p2p_ape_external, True, sender=escrow)
assert tokengators.isApprovedForAll(escrow, p2p_ape_external)
```


## Loan creation

### Lender deposits funds in the lending pool

```
common_usdc.approve(common_lending_pool_usdc, payment_amount, sender=lender)
common_lending_pool_usdc.deposit(payment_amount, sender=lender)
```

Transactions:
* [Approval](https://sepolia.etherscan.io/tx/0x17f171786f4ba8a2fcf9bec04e13eb2e25e08907f3d4dec06ccb19dccb379bc2)
* [Deposit](https://sepolia.etherscan.io/tx/0xc999f068be8c606ef15b886b5ca3cce8a20dbd128bd4733f69b418b8384c5920)

### Lender creates offer

```
draft = create_offer_draft(
    offer_type="COLLECTION",
    principal=principal,
    apr=100,
    p2p_contract_key="ape_external",
    duration=7*86400,
    expiration=now() + 10*86400,
    lender=lender.address,
    collection_key="tokengators",
    origination_fee_amount = 0,
    chain="curtis",
)
offer = create_offer_backend(lender, **draft)
```

```json
{
    'offer_id': '1166994ded8b345313e2eaa2c5c9cff9d330c360f4a24b2f4f7e3530cdaacb80',
    'chain': 'curtis',
    'offer_type': 'COLLECTION',
    'offer_display_type': 'AUTOMATIC',
    'principal': '1000000000000000000000',
    'interest': '191780821917808220',
    'payment_token': '0x69B5cfEfDd30467Ea985EBac1756d81EA871798c',
    'duration': 604800,
    'expiration': 1749205133,
    'lender': '0x00aA70B40A89aDF483f4068323789a64d791CCe5',
    'pro_rata': True,
    'size': 1,
    'tracing_id': '61d79edfeabccf6f0f4a34a9898de213d9ccbc98eab70636cc321e63f08b2ca1',
    'current_usage': 0,
    'p2p_contract_key': 'ape_external',
    'apr': 100,
    'effective_apr': 100,
    'repayment_amount': '1000191780821917808220',
    'origination_fee_amount': '0',
    'broker_upfront_fee_amount': '0',
    'broker_settlement_fee_bps': 0,
    'broker_address': '0x0000000000000000000000000000000000000000',
    'token_id': 0,
    'token_range_min': '0',
    'token_range_max': '115792089237316195423570985008687907853269984665640564039457584007913129639935',
    'collection_key': 'tokengators',
    'collection_key_hash': '9654a43f44ba44b65749206a683224e2dba51f2d7de9cd5215970326a08304b0',
    'collection_contract': '0xB16A9612b91259ABA40862233e25f9685Ea0d738',
    'trait_hash': '0000000000000000000000000000000000000000000000000000000000000000',
    'trait_name': None,
    'trait_value': None,
    'signature': {
        'v': '28',
        'r': '0xc3f37d1e1330cf8a4792927fe5eb860ddc29346010900884eb29079f9817df45',
        's': '0x61d72c375b22c7ef4b76e143a99925c515312fbb9c67f072600da2b9baa5e0e0'
    },
    'revoked': False,
    'offer_type_numerical': 2
}
```

### Borrower approves p2p contract for token and creates loan

```
create_loan(offer, token_id, p2p_ape_external, sender=borrower)
```

Transactions:
* [Approval](https://curtis.explorer.caldera.xyz/tx/0x64e9fa6d07318d10b9c0f69296d3247d374c43d47acf7af3b5bce0c30c3120fc)
* [Loan creation](https://curtis.explorer.caldera.xyz/tx/0x125dcc869492cbb10140b4883708006746d66002617398fe47c2c81d881a509c)


### Operator sends funds from LP to borrower

```
balance1 = common_usdc.balanceOf(borrower)
common_lending_pool_usdc.sendFunds(borrower, payment_amount, sender=operator)
balance2 = common_usdc.balanceOf(borrower)
```

Transactions:
* [Send funds](https://sepolia.etherscan.io/tx/0x1f32b02f8e42838407ef29889dffacf25de4c6a4f9d21da440f2d65f7890c510)

### Final state
* Borrower gets the funds
* Escrow gets the token

```
assert tokengators.ownerOf(token_id) == escrow
assert balance2 - balance1 == payment_amount
```


## Loan settlement

```
loan_id = "0xe3ce24f6af80a1dd7c75e4e042828abda26cac70f8dd8e953c13128131bbf2c5"
pay_loan(loan_id, p2p_ape_external, sender=borrower)
```

Transactions:
* [Approval](https://curtis.explorer.caldera.xyz/tx/0x377cf7d702f8d664a4f9dd0a0b48d3e222248ef8d2e9fde599b7f0937bebd1aa)
* [Loan settlement](https://curtis.explorer.caldera.xyz/tx/0xfa8be63e6aa2594649364fbf06788f95107cdfaa3d7de3ac8518e6e1e4eebf48)

```
assert tokengators.ownerOf(token_id) == borrower
```

# External payment test


## Wallets / contracts addresses


| **Name**                          | **Chain**        | **Address implementation**                   |
| ---                               | ---              | ---                                          |
| p2p lending contract              | curtis           | `0x13A18453c8aEeDb2e62502Dc74F0493B0E081C9C` |
| lending pool                      | sepolia          | `0xf8fD741e0935b46cBD25a6dB78317Bd462898BA3` |
| lender                            | curtis / sepolia | `0x00aA70B40A89aDF483f4068323789a64d791CCe5` |
| escrow                            | curtis / sepolia | `0xF00C9AF0B4c9C7636e12c80E4f22D7d6FF219475` |
| borrower                          | curtis / sepolia | `0x190Af7D087D32C61A2e23FB8aF192a58A6385DD1` |
| operator                          | curtis / sepolia | `0x77672996cD93B722e5a5673D404C3A92AD8dd1Fd` |
| erc721 tokengators                | curtis           | `0xB16A9612b91259ABA40862233e25f9685Ea0d738` |
| p2p lending contract token (WAPE) | curtis           | `0x69B5cfEfDd30467Ea985EBac1756d81EA871798c` |
| payment token (USDC)              | sepolia]         | `0x74540605Dc99f9cd65A3eA89231fFA727B1049E2` |


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

## SETUP

```
# fund wallets
me.transfer(borrower, int(1e17))
me.transfer(escrow, int(1e17))
me.transfer(lender, int(1e17))
me.transfer(operator, int(1e17))
common_usdc.transfer(lender, payment_amount, sender=me)

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
* [Approval](https://sepolia.etherscan.io/tx/0x4e9a905f766f46d0946cedcf373d4c0ec140dce96493b5d8aa0e109e01f0977b)
* [Deposit](https://sepolia.etherscan.io/tx/0xe14d208b7edd1be8f72df7a77bbec90d5130073c703afe24fc5a0a42d278c8a7)

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
    'offer_id': '1b13042eeb311733dad5e8c6060a665c6d1a8c34f035d0e5aac5472366255c00',
    'chain': 'curtis',
    'offer_type': 'COLLECTION',
    'offer_display_type': 'AUTOMATIC',
    'principal': '1000000000000000000000',
    'interest': '191780821917808220',
    'payment_token': '0x69B5cfEfDd30467Ea985EBac1756d81EA871798c',
    'duration': 604800,
    'expiration': 1749200832,
    'lender': '0x00aA70B40A89aDF483f4068323789a64d791CCe5',
    'pro_rata': True,
    'size': 1,
    'tracing_id': '5af6dd2ccc8f3a8e046a0b8004440780e97001f5773e631194112f6d33a6561f',
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
        'v': '27',
        'r': '0x542dee55e8d2f0d8b34d011ef93f95a63a03d96ec3837e410359704c9ceac22a',
        's': '0x7bd18ce2ee50bb4923a48d8e9eb7629c942e3a03971bff90037d9d9d70d320be'
    },
    'revoked': False,
    'offer_type_numerical': 2
}
```

### Borrower approves p2p contract for token and creates loan

```
tokengators.approve(p2p_ape_external, token_id, sender=borrower)
create_loan(offer, token_id, p2p_ape_external, sender=borrower)
```

Transactions:
* [Approval](https://curtis.explorer.caldera.xyz/tx/0x7a4ca81d1998523e200bb86393d8e42415e0a0570cbc505b0d6fd02c144c62cf)
* [Loan creation](https://curtis.explorer.caldera.xyz/tx/0x6b74d14206ac7e807c8d17dcec79f1972ac068ec891648c36589df184a03024e)


### Operator sends funds from LP to borrower

```
balance1 = common_usdc.balanceOf(borrower)
common_lending_pool_usdc.sendFunds(borrower, payment_amount, sender=operator)
balance2 = common_usdc.balanceOf(borrower)
```

Transactions:
* [Send funds](https://sepolia.etherscan.io/tx/0xbb143cc244d1cb644d9b4037b2dd3fc1ae39b2c1a047f328c98c8e475ab24ff7)

### Final state
* borrower gets the funds
* escrow gets the token

```
assert tokengators.ownerOf(token_id) == escrow
assert balance2 - balance1 == payment_amount
```

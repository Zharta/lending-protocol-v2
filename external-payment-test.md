# External payment test


## Wallets / contracts addresses


| **Name**                          | **Chain**        | **Address implementation**                   |
| ---                               | ---              | ---                                          |
| P2P lending contract              | sepolia          | `0x6Adf17dEF7fB76cba5a5ce0EceB6FC38b12e7a66` |
| Lending pool                      | curtis           | `0xF41aA7f8b8422157A458e839e1dB803fA339B315` |
| Lender                            | curtis / sepolia | `0x00aA70B40A89aDF483f4068323789a64d791CCe5` |
| Escrow                            | curtis / sepolia | `0xF00C9AF0B4c9C7636e12c80E4f22D7d6FF219475` |
| Borrower                          | curtis / sepolia | `0x190Af7D087D32C61A2e23FB8aF192a58A6385DD1` |
| Operator                          | curtis / sepolia | `0x77672996cD93B722e5a5673D404C3A92AD8dd1Fd` |
| ERC721 (MAYC)                     | sepolia          | `0x1a10c8d607a6Ab49c4C8d813Df118B64323F1dF1` |
| P2P lending contract token (APE)  | sepolia          | `0x66F549233CF1083182b29658260Aa3A7e13c6c39` |
| Payment token (WAPE)              | curtis           | `0x69B5cfEfDd30467Ea985EBac1756d81EA871798c` |


```
borrower = accounts.load("borrower")
lender = accounts.load("lender")
operator = accounts.load("operator")
escrow = accounts.load("escrow")
```

## Assets

* ERC721: MAYC 5
* Loan principal: 1000 WAPE
* Payment: 1000 WAPE

```
principal = int(1e21) # (1000 APE)
payment_amount = int(1e21) # (1000 WAPE)
token_id = 2
```

## Setup

```
# fund wallets
me.transfer(borrower, int(1e17))
me.transfer(escrow, int(1e17))
me.transfer(lender, int(1e17))
me.transfer(operator, int(1e17))
common_wape.transfer(lender, payment_amount, sender=me)
common_ape.transfer(borrower, principal * 2, sender=me)

#send token to borrower
mayc.transferFrom(me, borrower, token_id, sender=me)
assert mayc.ownerOf(token_id) == borrower

# approve p2p contract to get tokens from escrow
mayc.setApprovalForAll(p2p_ape_test, True, sender=escrow)
assert mayc.isApprovedForAll(escrow, p2p_ape_test)
```


## Loan creation

### Lender deposits funds in the lending pool

```
common_wape.approve(common_lending_pool_wape, payment_amount, sender=lender)
common_lending_pool_wape.deposit(payment_amount, sender=lender)
```

Transactions:
* [Approval](https://curtis.explorer.caldera.xyz/tx/0x5e5dd9d2f3ec7bc134c04b0611d898c451c5eb04545605667aae66260a82231d)
* [Deposit](https://curtis.explorer.caldera.xyz/tx/0x3d4d3c3f4c85f9144049005e237aa22e7cd64a4b80c87ea4cce00121c836edcb)

### Lender creates offer

```
draft = create_offer_draft(
    offer_type="COLLECTION",
    principal=principal,
    apr=100,
    p2p_contract_key="ape_test",
    duration=7*86400,
    expiration=now() + 10*86400,
    lender=lender.address,
    collection_key="mayc",
    origination_fee_amount = 0,
    chain="sepolia",
)
offer = create_offer_backend(lender, **draft)
```

```json
{
    'offer_id': '897f57e936c411bacd0b70e55736d3bd289ed06bf78ed12357f54ffa9bdbc33d',
    'chain': 'sepolia',
    'offer_type': 'COLLECTION',
    'offer_display_type': 'AUTOMATIC',
    'principal': '1000000000000000000000',
    'interest': '191780821917808220',
    'payment_token': '0x66F549233CF1083182b29658260Aa3A7e13c6c39',
    'duration': 604800,
    'expiration': 1749466467,
    'lender': '0x00aA70B40A89aDF483f4068323789a64d791CCe5',
    'pro_rata': True,
    'size': 1,
    'tracing_id': '4baa2ddf649c9606150ded5b14e339a586c6716733ce1f3aa870f72b7e6943b3',
    'current_usage': 0,
    'p2p_contract_key': 'ape_test',
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
    'collection_key': 'mayc',
    'collection_key_hash': '114e14e783e99c4fad5e2fc9977da428cde75700a285065b802d7debcacbd321',
    'collection_contract': '0x1a10c8d607a6Ab49c4C8d813Df118B64323F1dF1',
    'trait_hash': '0000000000000000000000000000000000000000000000000000000000000000',
    'trait_name': None,
    'trait_value': None,
    'signature': {
        'v': '27',
        'r': '0x450f3566897c4c96676bf1afe0c98b484563cc33df32fb706023ba0161fb50d4',
        's': '0x7fe5a168057b51310cca8ead8e881c8ae09ecc65a18b83757ac16f03fa705998'
    },
    'revoked': False,
    'offer_type_numerical': 2
}

```

### Borrower approves p2p contract for token and creates loan

```
create_loan(offer, token_id, p2p_ape_test, sender=borrower)
```

Transactions:
* [Approval](https://sepolia.etherscan.io/tx/0xf44d820c7b8f851a7ee6493a37018f001dd4d681f1cd4bfba8bae60890feca62)
* [Loan creation](https://sepolia.etherscan.io/tx/0x68e2804f2ce64e664d5df92c694271e9b44f453ec6d165b51e2c15051193a302)


### Operator sends funds from LP to borrower

```
balance1 = common_wape.balanceOf(borrower)
common_lending_pool_wape.sendFunds(borrower, payment_amount, sender=operator)
balance2 = common_wape.balanceOf(borrower)
```

Transactions:
* [Send funds](https://curtis.explorer.caldera.xyz/tx/0x61984ec22e20f2f061c1925d143e8633a1c20e8573b6010a03b72923a3b1264b)

### Final state
* Borrower gets the funds
* Escrow gets the token

```
assert mayc.ownerOf(token_id) == escrow
assert balance2 - balance1 == payment_amount
```


## Loan settlement

```
loan_id = "0x8d465f2de11ad1edf803947189304f5ea6fcce46c6fab96ceeda2cbaf1ddf4e4"
pay_loan(loan_id, p2p_ape_test, sender=borrower)
```

Transactions:
* [Approval](https://sepolia.etherscan.io/tx/0x79a4bc6265865498e7acc831c9bb2d7bc3fc639773f72d38d29ca2a1ff1beb98)
* [Loan settlement](https://sepolia.etherscan.io/tx/0x26372a415f2f18ff694cd90aee437a353cddb1d7bc0a153f86d5e8bf0dc7444b)

```
assert mayc.ownerOf(token_id) == borrower
```

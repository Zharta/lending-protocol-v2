# External gateway payment test


## Wallets / contracts addresses


| **Name**                          | **Chain**        | **Address implementation**                   |
| ---                               | ---              | ---                                          |
| P2P lending contract              | sepolia          | `0x9C875159E5571A652c070851242A59b5676C2043` |
| Lending pool                      | curtis           | `0xF41aA7f8b8422157A458e839e1dB803fA339B315` |
| Lender                            | curtis / sepolia | `0x00aA70B40A89aDF483f4068323789a64d791CCe5` |
| Escrow                            | curtis / sepolia | `0x832D9056AF4E611c53ed1d783eA4eC0e5c6fBce4` |
| Borrower                          | curtis / sepolia | `0x190Af7D087D32C61A2e23FB8aF192a58A6385DD1` |
| Operator                          | curtis / sepolia | `0x77672996cD93B722e5a5673D404C3A92AD8dd1Fd` |
| ERC721 (Cryptopunks 721)          | sepolia          | `0x9c0D2E0e20B04bAdb3bcC8323BDb408a63b2e929` |
| P2P lending contract token (APE)  | sepolia          | `0x66F549233CF1083182b29658260Aa3A7e13c6c39` |
| Payment token (WAPE)              | curtis           | `0x69B5cfEfDd30467Ea985EBac1756d81EA871798c` |


```
borrower = accounts.load("borrower")
lender = accounts.load("lender")
operator = accounts.load("operator")
escrow = "0x832D9056AF4E611c53ed1d783eA4eC0e5c6fBce4"
```

## Assets

* ERC721: Cryptopunks 721 token id 314
* Loan principal: 1000 WAPE
* Payment: 1000 WAPE

```
principal = int(1e21) # (1000 APE)
payment_amount = int(1e21) # (1000 WAPE)
token_id = 314
```

## Onchain Setup

```
# fund wallets
me.transfer(borrower, int(1e17))
me.transfer(lender, int(1e17))
me.transfer(operator, int(1e17))
common_wape.transfer(lender, payment_amount, sender=me)
common_ape.transfer(borrower, principal * 2, sender=me)
initial_borrower_balance_wape = common_wape.balanceOf(borrower)

#send token to borrower
punk721.transferFrom(me, borrower, token_id, sender=me)
assert punk721.ownerOf(token_id) == borrower

```


## Gateway Setup

Config `rpcApiWsHost` endpoints in `satp-gateway/config/config.json`:
```
        "connectorOptions": {
          "rpcApiWsHost": "wss://eth-sepolia.g.alchemy.com/v2/..."
        },
```

```bash

# start the gateway container
make start-gateway
rm satp-gateway/satp-hermes-gateway/logs/* || true
[+] Running 2/2
 ⠿ Network satp-gateway_default                  Created                                                                                                  0.1s
 ⠿ Container satp-gateway-satp-hermes-gateway-1  Started                                                                                                  0.2s


# register event listener in the gateway
make register-listener
Registering EVENT_LISTENING with READ_AND_UPDATE Tasks...
ENV=int ./.venv/bin/ape run satp_register_listener
Response:
{
    'taskID': '69b16707-ddc5-4970-a824-7d216e0aaa56',
    'type': 'READ_AND_UPDATE',
    'srcNetworkId': {'id': 'Sepolia', 'ledgerType': 'ETHEREUM'},
    'dstNetworkId': {'id': 'Curtis', 'ledgerType': 'ETHEREUM'},
    'srcContract': {
        'contractName': 'P2PLendingExternal',
        'contractAbi': [ ... ],
        'contractAddress': '0x9C875159E5571A652c070851242A59b5676C2043'
    },
    'dstContract': {
        'contractAbi': [ ...],
        'contractName': 'LendingPoolExternal',
        'contractBytecode': {'bytecode': '0x5f3560e0...'},
        'contractAddress': '0xF41aA7f8b8422157A458e839e1dB803fA339B315',
        'methodName': 'sendFunds'
    },
    'mode': 'EVENT_LISTENING',
    'status': 'ACTIVE',
    'timestamp': 1776849582973,
    'operations': [],
    'listeningOptions': {
        'eventSignature': 'LoanCreated(bytes32,uint256,uint256,address,uint256,uint256,address,address,address,uint256,(uint256,uint256,uint256,address)[],bool,bytes32,bytes32,address)' ,
        'filterParams': ['borrower', 'amount']
    }
}
Task ID: 69b16707-ddc5-4970-a824-7d216e0aaa56
Done

```

## Loan creation

### Lender deposits funds in the lending pool

```
common_wape.approve(common_lending_pool_wape, payment_amount, sender=lender)
common_lending_pool_wape.deposit(payment_amount, sender=lender)
```

Transactions:
* [Approval](https://curtis.explorer.caldera.xyz/tx/0x919c3a78d3eb64798e8a8e8ee52a6d1b2a03e3288aad00ffe14906a3f3f54452)
* [Deposit](https://curtis.explorer.caldera.xyz/tx/0xd953054d77fbc6c64f7605e2d29ec5b2cd58cb4c3aeb5da6253c66e9dd83ee20)

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
    collection_key="punk721",
    origination_fee_amount = 0,
    chain="sepolia",
)
offer = create_offer_backend(lender, **draft)
```

```json

{
    'offer_id': '8328dda8deafe9d13cde44f09e830e2ddeaf8540bb1fd9fb8c76a9422238d21c',
    'chain': 'sepolia',
    'offer_type': 'COLLECTION',
    'offer_display_type': 'AUTOMATIC',
    'principal': '1000000000000000000000',
    'interest': '191780821917808220',
    'payment_token': '0x66F549233CF1083182b29658260Aa3A7e13c6c39',
    'duration': 604800,
    'expiration': 1777713950,
    'lender': '0x00aA70B40A89aDF483f4068323789a64d791CCe5',
    'pro_rata': True,
    'size': 1,
    'tracing_id': '98a6f676a148e721792b86a035f2ea15670581096ec0a1c5693ff47b60e2f890',
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
    'collection_key': 'punk721',
    'collection_key_hash': '5a198fbd3076bec1658705e21690366abdd3f950a7301dd3da6c2fd358ece48e',
    'collection_contract': '0x9c0D2E0e20B04bAdb3bcC8323BDb408a63b2e929',
    'trait_hash': '0000000000000000000000000000000000000000000000000000000000000000',
    'trait_name': None,
    'trait_value': None,
    'signature': {
        'v': '28',
        'r': '0x6363479c553e043f149664e6f7128be1b560a12afc55863f95654b985d4fe821',
        's': '0x4fcec314b9f70c16e3ed02c26bf26f944e8ec09e4495783ca842bcbc67c8c9e8'
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
* [Approval](https://sepolia.etherscan.io/tx/0x97d93be1f61216eb148a8b22cc2e090908c08224c54baee2192263f202999cdc)
* [Loan creation](https://sepolia.etherscan.io/tx/0xdbba7fec1b5966260dd160cc9adea03d88f3cbeed2fdc5a366012e926e98c088)


### Gateway sends funds from LP to borrower


```
# check operations status for the task in the gateway
python satp-gateway/oracle-evm-check-status.py 59f742c3-77a2-4989-bb50-6721cae2651d
Response: {
    'taskID': '69b16707-ddc5-4970-a824-7d216e0aaa56',
    'type': 'READ_AND_UPDATE',
    'srcNetworkId': {'id': 'Sepolia', 'ledgerType': 'ETHEREUM'},
    'srcContract': {'contractName': 'P2PLendingExternal', 'contractAbi': [...], 'contractAddress': '0x9C875159E5571A652c070851242A59b5676C2043'},
    'dstNetworkId': {'id': 'Curtis', 'ledgerType': 'ETHEREUM'},
    'dstContract': {'contractAbi': [ ... ], 'contractName': 'LendingPoolExternal', 'contractBytecode': {'bytecode': '0x5f3560e01c60...'}, 'contractAddress': '0xF41aA7f8b8422157A458e839e1dB803fA339B315', 'methodName': 'sendFunds'},
    'timestamp': 1776849582973,
    'operations': [{
        'id': '98e8ad4d-007b-4de2-a384-29c4befbd0d0',
        'type': 'UPDATE',
        'networkId': {'id': 'Curtis', 'ledgerType': 'ETHEREUM'},
        'contract': {'contractName': 'LendingPoolExternal', 'contractAddress': '0xF41aA7f8b8422157A458e839e1dB803fA339B315', 'methodName': 'sendFunds', 'params': ['0x190Af7D087D32C61A2e23FB8aF192a58A6385DD1', '1000000000000000000000']},
        'status': 'SUCCESS',
        'output': {
            'transactionId': '0x532e47afd898c70d8fe2246beb8ff8274a8fd011453d57dae834382cb1b9c349',
            'transactionReceipt': {
                'blockHash': '0xdd4169b9e17ba062fa72360ae43eadab87fbebc1755fb2fc1e248b9c095f9ea7',
                'blockNumber': '32520645',
                'cumulativeGasUsed': '63765',
                'effectiveGasPrice': '101682760000',
                'from': '0x77672996cd93b722e5a5673d404c3a92ad8dd1fd',
                'gasUsed': '63765',
                'logs': [{
                    'address': '0xf41aa7f8b8422157a458e839e1db803fa339b315',
                    'topics': ['0xef265aa5ba98d1c64ea9531227080a274c7f2e0adbfb9a36869e5dc6abcab581', '0x000000000000000000000000190af7d087d32c61a2e23fb8af192a58a6385dd1'],
                    'data': '0x000000000000000000000000190af7d087d32c61a2e23fb8af192a58a6385dd100000000000000000000000000000000000000000000003635c9adc5dea0000000000000000000000000000069b5cfefdd30467ea985ebac1756d81ea871798c',
                    'blockNumber': '32520645',
                    'transactionHash': '0x532e47afd898c70d8fe2246beb8ff8274a8fd011453d57dae834382cb1b9c349',
                    'transactionIndex': '1',
                    'blockHash': '0xdd4169b9e17ba062fa72360ae43eadab87fbebc1755fb2fc1e248b9c095f9ea7',
                    'logIndex': '0',
                    'removed': False
                }, {
                    'address': '0x69b5cfefdd30467ea985ebac1756d81ea871798c',
                    'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef', '0x000000000000000000000000f41aa7f8b8422157a458e839e1db803fa339b315', '0x000000000000000000000000190af7d087d32c61a2e23fb8af192a58a6385dd1'],
                    'data': '0x00000000000000000000000000000000000000000000003635c9adc5dea00000',
                    'blockNumber': '32520645',
                    'transactionHash': '0x532e47afd898c70d8fe2246beb8ff8274a8fd011453d57dae834382cb1b9c349',
                    'transactionIndex': '1',
                    'blockHash': '0xdd4169b9e17ba062fa72360ae43eadab87fbebc1755fb2fc1e248b9c095f9ea7',
                    'logIndex': '1',
                    'removed': False
                }],
                'logsBloom': '0x00000000000000020000000000000000000000000000001000000002000000000000000000040000000010000000000000000000410000000000000000100000000000000000080000000008000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000010000000000800000000000000000000000000000000000000000000000000000000000000000000000008000000000000000000000000000000000080004000000000000000000002000000000000000000000000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000',
                'status': True,
                'to': '0xf41aa7f8b8422157a458e839e1db803fa339b315',
                'transactionHash': '0x532e47afd898c70d8fe2246beb8ff8274a8fd011453d57dae834382cb1b9c349',
                'transactionIndex': '1',
                'type': '2'
            }
        },
        'timestamp': 1776850056723}],
        'status': 'ACTIVE',
        'mode': 'EVENT_LISTENING',
        'listeningOptions': {
            'eventSignature': 'LoanCreated(bytes32,uint256,uint256,address,uint256,uint256,address,address,address,uint256,(uint256,uint256,uint256,address)[],bool,bytes32,bytes32,address)',
            'filterParams': ['borrower', 'amount']
        }
}

```

Transactions:
* [Send funds](https://curtis.explorer.caldera.xyz/tx/0x532e47afd898c70d8fe2246beb8ff8274a8fd011453d57dae834382cb1b9c349)

### Final state
* Borrower gets the funds
* Escrow gets the token

```
assert punk721.ownerOf(token_id) == escrow
final_borrower_balance_wape = common_wape.balanceOf(borrower)
assert final_borrower_balance_wape - initial_borrower_balance_wape == payment_amount
```


## Escrow approval for loan settlement

Approval via Porto app.

```
assert punk721.isApprovedForAll(escrow, p2p_ape_test)
```

Transactions:
* [Approval](https://sepolia.etherscan.io/tx/0x832d9056af4e611c53ed1d783ea4ec0e5c6fbce4)

## Loan settlement

```
loan_id = "0x9689b5761754e6fafc45225c0e3b5585ebda1cb4c87ee74ff33005a1b48719a4"
pay_loan(loan_id, p2p_ape_test, sender=borrower)
(ContractLogicError) transfer is not approved
```

Transactions:
* [Approval](https://sepolia.etherscan.io/tx/0xccdd8ee0c5ac14aebe140ea85633613a93a40e847dd5bd5934e887ef976d24a5)
* [Loan settlement](https://sepolia.etherscan.io/tx/0xd8244167e787f4dfb50f5456fb9d46c2cd23c0d61e25f537e7a0866d9072b415)

```
assert punk721.ownerOf(token_id) == borrower
```

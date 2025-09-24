# External gateway payment test


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

* ERC721: MAYC 2
* Loan principal: 1000 WAPE
* Payment: 1000 WAPE

```
principal = int(1e21) # (1000 APE)
payment_amount = int(1e21) # (1000 WAPE)
token_id = 2
```

## Onchain Setup

```
# fund wallets
me.transfer(borrower, int(1e17))
me.transfer(escrow, int(1e17))
me.transfer(lender, int(1e17))
me.transfer(operator, int(1e17))
common_wape.transfer(lender, payment_amount, sender=me)
common_ape.transfer(borrower, principal * 2, sender=me)
initial_borrower_balance_wape = common_wape.balanceOf(borrower)

#send token to borrower
mayc.transferFrom(me, borrower, token_id, sender=me)
assert mayc.ownerOf(token_id) == borrower

# approve p2p contract to get tokens from escrow
mayc.setApprovalForAll(p2p_ape_test, True, sender=escrow)
assert mayc.isApprovedForAll(escrow, p2p_ape_test)
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
    'taskID': '4354aa4c-13de-4f32-800f-74256aed01e9',
    'type': 'READ_AND_UPDATE',
    'srcNetworkId': {'id': 'Sepolia', 'ledgerType': 'ETHEREUM'},
    'dstNetworkId': {'id': 'Curtis', 'ledgerType': 'ETHEREUM'},
    'srcContract': {
        'contractName': 'P2PLendingExternal',
        'contractAbi': [ ... ],
        'contractAddress': '0x6Adf17dEF7fB76cba5a5ce0EceB6FC38b12e7a66'
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
    'timestamp': 1758711145984,
    'operations': [],
    'listeningOptions': {
        'eventSignature': 'LoanCreated(bytes32,uint256,uint256,address,uint256,uint256,address,address,address,uint256,(uint256,uint256,uint256,address)[],bool,bytes32,bytes32,address)' ,
        'filterParams': ['borrower', 'amount']
    }
}
Task ID: 4354aa4c-13de-4f32-800f-74256aed01e9
Done

```

## Loan creation

### Lender deposits funds in the lending pool

```
common_wape.approve(common_lending_pool_wape, payment_amount, sender=lender)
common_lending_pool_wape.deposit(payment_amount, sender=lender)
```

Transactions:
* [Approval](https://curtis.explorer.caldera.xyz/tx/0x233c4b46caf5e73c56d1d35744664406c0eabf58ed33a32abe77208c0dc0d2e9)
* [Deposit](https://curtis.explorer.caldera.xyz/tx/0xfd010291a382b25804e829f0cb8d96d9ae263796f1d4050e2b8aef151e2571b4)

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
    'offer_id': 'e4b2b8f1a29dddb132f491541b3d8bc6f1a32beb72ac8034c72b4f5038cb3246',
    'chain': 'sepolia',
    'offer_type': 'COLLECTION',
    'offer_display_type': 'AUTOMATIC',
    'principal': '1000000000000000000000',
    'interest': '191780821917808220',
    'payment_token': '0x66F549233CF1083182b29658260Aa3A7e13c6c39',
    'duration': 604800,
    'expiration': 1759574913,
    'lender': '0x00aA70B40A89aDF483f4068323789a64d791CCe5',
    'pro_rata': True,
    'size': 1,
    'tracing_id': '380881c688802b59ebfb6d62adca709951c3c887f2c1f67f7cce6d45a72c0fa7',
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
        'r': '0x89cb13e23f89e9246c113714b49489129df9ddb997b5ec16470df354269cfb46',
        's': '0x7deb50e1ee3fe11ae171fdfab86a811bc19c8c885ee7497420a358ba3b4e89a8'
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
* [Approval](https://sepolia.etherscan.io/tx/0x1fc1c89fd5d6ce87a7d2fd0f48fea178c3f9493e48d3bb36cc978ab72284829f)
* [Loan creation](https://sepolia.etherscan.io/tx/0xfb194c67cb89980bb7ad666f734517e4e8324acba5bc87af17761dcc65e0a2bb)


### Gateway sends funds from LP to borrower


```
# check operations status for the task in the gateway
python satp-gateway/oracle-evm-check-status.py 4354aa4c-13de-4f32-800f-74256aed01e9
Response: {
    'taskID': '4354aa4c-13de-4f32-800f-74256aed01e9',
    'type': 'READ_AND_UPDATE',
    'srcNetworkId': {'id': 'Sepolia', 'ledgerType': 'ETHEREUM'},
    'srcContract': {'contractName': 'P2PLendingExternal', 'contractAbi': [...], 'contractAddress': '0x6Adf17dEF7fB76cba5a5ce0EceB6FC38b12e7a66'},
    'dstNetworkId': {'id': 'Curtis', 'ledgerType': 'ETHEREUM'},
    'dstContract': {'contractAbi': [ ... ], 'contractName': 'LendingPoolExternal', 'contractBytecode': {'bytecode': '0x5f3560e01c60...'}, 'contractAddress': '0xF41aA7f8b8422157A458e839e1dB803fA339B315', 'methodName': 'sendFunds'},
    'timestamp': 1758711145984,
    'operations': [{
        'id': 'e6db6425-785d-4427-8ac4-59a099e03829',
        'type': 'UPDATE',
        'networkId': {'id': 'Curtis', 'ledgerType': 'ETHEREUM'},
        'contract': {'contractName': 'LendingPoolExternal', 'contractAddress': '0xF41aA7f8b8422157A458e839e1dB803fA339B315', 'methodName': 'sendFunds', 'params': ['0x190Af7D087D32C61A2e23FB8aF192a58A6385DD1', '1000000000000000000000']},
        'status': 'SUCCESS',
        'output': {
            'transactionId': '0x6a49e3d59ddbf78f65666259b117ce9b1d2e561a7e10c1fb2b39d66c52e782fe',
            'transactionReceipt': {
                'blockHash': '0x8946f50d2659b73d4f9db45c92756da1a6a910fbe92f789b7bcb9ad6eb228356',
                'blockNumber': '28697454',
                'cumulativeGasUsed': '54165',
                'effectiveGasPrice': '10000000',
                'from': '0x77672996cd93b722e5a5673d404c3a92ad8dd1fd',
                'gasUsed': '54165',
                'logs': [{
                    'address': '0xf41aa7f8b8422157a458e839e1db803fa339b315',
                    'topics': ['0xef265aa5ba98d1c64ea9531227080a274c7f2e0adbfb9a36869e5dc6abcab581', '0x000000000000000000000000190af7d087d32c61a2e23fb8af192a58a6385dd1'],
                    'data': '0x000000000000000000000000190af7d087d32c61a2e23fb8af192a58a6385dd100000000000000000000000000000000000000000000003635c9adc5dea0000000000000000000000000000069b5cfefdd30467ea985ebac1756d81ea871798c',
                    'blockNumber': '28697454',
                    'transactionHash': '0x6a49e3d59ddbf78f65666259b117ce9b1d2e561a7e10c1fb2b39d66c52e782fe',
                    'transactionIndex': '1',
                    'blockHash': '0x8946f50d2659b73d4f9db45c92756da1a6a910fbe92f789b7bcb9ad6eb228356',
                    'logIndex': '0',
                    'removed': False
                }, {
                    'address': '0x69b5cfefdd30467ea985ebac1756d81ea871798c',
                    'topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef', '0x000000000000000000000000f41aa7f8b8422157a458e839e1db803fa339b315', '0x000000000000000000000000190af7d087d32c61a2e23fb8af192a58a6385dd1'],
                    'data': '0x00000000000000000000000000000000000000000000003635c9adc5dea00000',
                    'blockNumber': '28697454',
                    'transactionHash': '0x6a49e3d59ddbf78f65666259b117ce9b1d2e561a7e10c1fb2b39d66c52e782fe',
                    'transactionIndex': '1',
                    'blockHash': '0x8946f50d2659b73d4f9db45c92756da1a6a910fbe92f789b7bcb9ad6eb228356',
                    'logIndex': '1',
                    'removed': False
                }],
                'logsBloom': '0x0000000...',
                'status': True,
                'to': '0xf41aa7f8b8422157a458e839e1db803fa339b315',
                'transactionHash': '0x6a49e3d59ddbf78f65666259b117ce9b1d2e561a7e10c1fb2b39d66c52e782fe',
                'transactionIndex': '1',
                'type': '2'
            }
        },
        'timestamp': 1758711192577
    }],
    'status': 'ACTIVE',
    'mode': 'EVENT_LISTENING',
    'listeningOptions': {
        'eventSignature': 'LoanCreated(bytes32,uint256,uint256,address,uint256,uint256,address,address,address,uint256,(uint256,uint256,uint256,address)[],bool,bytes32,bytes32,address)',
        'filterParams': ['borrower', 'amount']
    }
}

```

Transactions:
* [Send funds](https://curtis.explorer.caldera.xyz/tx/0x6a49e3d59ddbf78f65666259b117ce9b1d2e561a7e10c1fb2b39d66c52e782fe)

### Final state
* Borrower gets the funds
* Escrow gets the token

```
assert mayc.ownerOf(token_id) == escrow
final_borrower_balance_wape = common_wape.balanceOf(borrower)
assert final_borrower_balance_wape - initial_borrower_balance_wape == payment_amount
```


## Loan settlement

```
loan_id = "0xe60056de56bb06ed3d1751db6dbcfa3b912dda398fbc04b62371dd8882ea3624"
pay_loan(loan_id, p2p_ape_test, sender=borrower)
```

Transactions:
* [Approval](https://sepolia.etherscan.io/tx/0x16b97fe8b3fd5b3036c5660589842c56006e33c83b84a2805ef011eb769055d8)
* [Loan settlement](https://sepolia.etherscan.io/tx/0x52e9ae07b9634f9cecc14d5517441e48c246f852b13038135a9180029068a7a6)

```
assert mayc.ownerOf(token_id) == borrower
```

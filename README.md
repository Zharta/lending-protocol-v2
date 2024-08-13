# Zharta P2P Lending Protocol

## Introduction

This protocol implements a peer-to-peer lending system for NFTs. It allows NFT owners to use their assets as collateral to borrow cryptocurrency, while lenders can provide loans and earn interest. The protocol is designed to be trustless, efficient, and flexible, with support for various NFT standards including ERC721 and CryptoPunks.

## Overview

| **Version** | **Language**          | **Reference implementation**                  |
| ---         | ---                   | ---                                           |
| V1          | Vyper 0.3.7 - 0.3.10  | https://github.com/Zharta/protocol-v1         |
| V2          | Vyper 0.3.10          | https://github.com/Zharta/lending-protocol-v2 |

There are two major components in the protocol:
* the `P2PLendingNfts` contract support NFTs backed peer to peer lending
* the `P2PLendingControl` contract contains cross contract configurations

The lending of an NFT in the context of this protocol means that:
1. A lender provides a loan offer with specific terms
2. A borrower creates a loan using their NFT as collateral
3. The loan is created when the borrower accepts an offer
4. The borrower repays the loan within the specified term
5. If the borrower defaults, the lender can claim the NFT collateral
6. A loan may be replaced by the borrower while still ongoing, by accepting other offer
7. A loan may be replaced by the lender while still ongoing, within some defined conditions

In addition, the protocol supports a broker system to facilitate loans and integrates with a delegation registry for potential NFT rentals during the loan period.

## General considerations

The current status of the protocol follows certain assumptions:

1. Support for ERC721 NFTs and CryptoPunks as collateral
2. The set of accepted NFT contracts is whitelisted, defined in `P2PLendingControl`
3. Integration with a [delegation registry](https://delegate.xyz/) for potential NFT utility during loans
4. Use of native ETH or some ERC20 (eg USDC) as a payment token, defined at deployment time for each instance of `P2PLendingNfts`
5. The loan terms are part of the lender offers, which are signed and kept off-chain
6. Offers have an expiration timestamp and can also be revoked onchain
7. Brokers can be part of the loan negotiation and the protocol supports fees for both lender and borrower brokers
8. Additional fees are supported both for the protocol and for the lender (origination)

## Security

Below are the smart contract audits performed for the protocol so far:

| **Auditor**   | **Version**  | **Status**   | **PDF**                                                                                                                                |
| :-----------: | :----------: | :----------: | ---------                                                                                                                              |
| Red4Sec       | V1           | Done         | [Zharta - Audit Report Final.pdf](https://github.com/Zharta/protocol-v1/blob/main/docs/audits/Zharta%20-%20Audit%20Report%20Final.pdf) |
| Hacken        | V1           | Done         | [Zharta_SCAudit_Report_Final.pdf](https://github.com/Zharta/protocol-v1/blob/main/docs/audits/Zharta_SCAudit_Report_Final.pdf)         |
| Hacken        | V2           | Pending      |                                                                                                                                        |


## Architecture

As previously stated, there are two main components of the protocol:
* The core lending functionality implemented in the `P2PLendingNfts.vy` contract
* The collateral management and control logic implemented in the `P2PLendingControl.vy` contract

Users and other protocols should primarily interact with the `P2PLendingNfts.vy` contract. This contract is responsible for:
* Creating loans based on signed offers and collateral
* Settling loans
* Handling defaulted loans
* Replacing existing loans, either by the borrower's initiative or the lender's initiative
* Managing protocol fees
* Revoking unused offers
* Managing authorized proxies
* Setting and managing the delegation of collateral during loan creation

The `P2PLendingControl.vy` contract manages:
* Whitelisted NFT collections
* Broker locks on collateral
* Collateral status tracking


### Offers

Loans are created based on the borrower acceptance of offers from lenders, which specify the loan terms. The general features of an offer are:

1. **Offer Structure**: An offer is defined by the `Offer` structure, which includes:
   - Principal amount
   - Interest amount
   - Payment token address
   - Loan duration
   - Origination fee amount
   - Broker fees (upfront and settlement)
   - Broker address
   - Collateral contract address and token ID range
   - Expiration timestamp
   - Lender address
   - Pro-rata flag (for interest calculation)

2. **Signed Offers**: Lenders create and sign offers off-chain. These signed offers (`SignedOffer`) combine the `Offer` structure with a signature.

3. **Offer Validation**: When a borrower wants to create a loan using an offer, the protocol verifies the offer's signature and checks if it's still valid (not expired or fully utilized).

4. **Offer Utilization**: Each time an offer is used to create a loan, its utilization count is increased. An offer can be used multiple times up to its specified size.

5. **Offer Revocation**: Lenders can revoke their offers before they expire or are fully utilized.

6. **Collateral Range**: Offers specify a range of token IDs for the collateral, allowing flexibility in which specific NFT can be used as collateral within the same collection.

7. **Pro-rata Interest**: Offers can specify whether interest should be calculated on a pro-rata basis or for the full duration regardless of early repayment.

As offers are kept offchain, to prevent abusive usage of an offer some validations are in place:
1. Each offer has an expiration timestamp, after which it can't be used
2. Offers can be revoked before expiration by calling `revoke_offer` in `P2PLendingNfts`
3. Each offer has a `size` determining how many loans it can originate


### Loans

1. **Loan Creation (`create_loan`)**:
   The loan creation process begins with the verification of the offer's signature and its validity. Once verified, the NFT collateral is transferred to the contract, which can be either an ERC721 token or a CryptoPunk. If delegation is required, it is set up using delegate.xyz. The principal amount, minus any applicable fees, is then transferred from the lender to the borrower. Upfront fees are distributed to the relevant parties, and a loan record is created and stored within the contract.

2. **Loan Settlement (`settle_loan`)**:
   To settle a loan, the contract calculates the total repayment amount, which includes the principal, interest, and any fees. The borrower transfers this repayment amount to the contract. The contract then distributes the funds to the lender and any fee recipients. The collateral is transferred back to the borrower.

3. **Defaulted Loan Collateral Claim (`claim_defaulted_loan_collateral`)**:
   When a loan has defaulted, the lender can claim the collateral. The collateral is then transferred from the contract to the lender and no funds are transferred in this process.

4. **Loan Replacement by Borrower (`replace_loan`)**:
   A borrower can replace an existing loan with a new one by accepting a new offer. The contract calculates the settlement amounts for the current loan, which are equivalent of settling the current loan and accepting an offer for the same collateral. The repayment and fees for the current loan are distributed, and new loan terms are set up. No changes happen regarding the collateral ownership or delegation.

5. **Loan Replacement by Lender (`replace_loan_lender`)**:
   A lender can replace an existing loan with a new one by accepting a now offer on behalf of the borrower. The contract calculates the settlement amounts and any borrower compensation needed to ensure that:
* no additional liquidity is needed from the borrower;
* the borrowers repayment under the new conditions is not higher than the original loan's conditions (up until the original loan's maturity)

Funds are transferred to cover the new loan terms if needed. The repayment and fees for the current loan are distributed, and new loan terms are set up. No changes happen regarding the collateral ownership or delegation.

### Delegation

The protocol integrates with [delegation.xyz](https://delegate.xyz/) delegation registry V2, potentially allowing for NFT utility during the loan period. Delegation is set when a new loan is created and remains in place until the loan is settled, regardless of whether the collateral is claimed or returned to the borrower. Delegation is set in full, not using the registry's subdelegation feature.


### Fees

The protocol supports several types of fees:

* **Protocol Fee**: This is a fee that goes to the protocol. It can have both an upfront component, paid when the loan is created, and a settlement component, paid as a percentage of the interest during loan settlement. The protocol fee is defined in the `P2PLendingNfts` contract.
* **Origination Fee**: This is a fee paid to the lender when a loan is created. It can be defined as an upfront amount. It is part of the loan terms defined in the `Offer` structure.
* **Lender Broker Fee**: This is a fee paid to the broker facilitating the loan on the lender's side. It can have both an upfront component and a settlement component, defined as a percentage of the interest. It is part of the loan terms defined in the `Offer` structure.
* **Borrower Broker Fee**: This is a fee paid to the broker facilitating the loan on the borrower's side. It can have both an upfront component and a settlement component, defined as a percentage of the interest. It is specified by the borrower when the loan is created.

The upfront fees are paid during loan creation, while the settlement fees are paid as a fraction of the interest amount during loan settlement.


### Broker Locks

The `P2PLendingControl` contract manages temporary locks on collateral for brokers. Collateral owners can add a broker lock on a specific collateral, which defines the broker address and the expiration time of the lock. Brokers can remove the lock on the collateral they are assigned to before the expiration time. This allows brokers to facilitate loans while ensuring the collateral is not used elsewhere during the loan negotiation process.


### Roles

The protocol supports the following roles:
* `Owner`: Can update protocol parameters, change whitelisted collections, and manage the protocol
* `Borrower`: Defined as a individual role for each loan, can settle and replace their loans
* `Lender`: Defined as a individual role for each loan, can replace their loans and claim collateral in case of defaults
* `Broker`: Can have temporary locks on collateral


## Development

### Implementation

#### P2P Lending NFTs Contract (`P2PLendingNfts.vy`)

The P2P Lending NFTs contract facilitates peer-to-peer lending using NFTs as collateral. It manages loan offers, collateral locking, and loan settlements.

##### State variables

| **Variable**             | **Type**                    | **Mutable** | **Description**                                                |
| ---                      | ---                         | :-:         | ---                                                             |
| owner                    | `address`                   | Yes         | Address of the contract owner                                   |
| proposed_owner           | `address`                   | Yes         | Address of the proposed new owner                               |
| payment_token            | `address`                   | No          | Address of the payment token (ERC20) contract                   |
| protocol_wallet          | `address`                   | Yes         | Address of the protocol fee wallet                              |
| protocol_upfront_fee     | `uint256`                   | Yes         | Upfront fee amount for the protocol                             |
| protocol_settlement_fee  | `uint256`                   | Yes         | Settlement fee amount for the protocol                          |
| loans                    | `HashMap[bytes32, bytes32]` | Yes         | Mapping of loan IDs to loan state hashes                        |
| offer_count              | `HashMap[bytes32, uint256]` | Yes         | Mapping of offer IDs to their usage count                       |
| revoked_offers           | `HashMap[bytes32, bool]`    | Yes         | Mapping of offer IDs to their revocation status                 |
| authorized_proxies       | `HashMap[address, bool]`    | Yes         | Mapping of authorized proxy addresses                           |

##### Externalized State

In the P2PLendingNfts contract, certain state information is externalized to reduce gas costs while using the protocol. This approach primarily involves the Loan and Offer structures.

For Loans:
- The contract stores hashes of loan states in the `loans` mapping instead of storing the full loan data on-chain.
- When interacting with a loan (e.g., in functions like `settle_loan` and `replace_loan`), the full loan state is passed as an argument and validated by matching its hash against the stored hash.
- Changes to the loan state are hashed and stored, and the resulting state variables are published as events.

For Offers:
- The contract doesn't store full offer data on-chain. Instead, it tracks offer usage in the `offer_count` mapping and revocation status in the `revoked_offers` mapping.
- When creating a loan or interacting with an offer, the full offer data is passed as an argument and validated using the stored counters and the offer signature.

##### Structs

| **Struct** | **Variable**           | **Type**                        | **Description**                                               |
| ---        | ---                    | ---                             | ---                                                           |
| Offer      | principal              | `uint256`                       | Principal amount of the loan                                  |
|            | interest               | `uint256`                       | Interest amount of the loan                                   |
|            | payment_token          | `address`                       | Address of the payment token                                  |
|            | duration               | `uint256`                       | Duration of the loan                                          |
|            | expiration             | `uint256`                       | Expiration timestamp of the offer                             |
|            | lender                 | `address`                       | Address of the lender                                         |
|            | collateral_contract    | `address`                       | Address of the collateral NFT contract                        |
|            | collateral_min_token_id| `uint256`                       | Minimum token ID for the collateral range                     |
|            | collateral_max_token_id| `uint256`                       | Maximum token ID for the collateral range                     |
| Loan       | id                     | `bytes32`                       | Unique identifier of the loan                                 |
|            | amount                 | `uint256`                       | Loan amount                                                   |
|            | interest               | `uint256`                       | Interest amount                                               |
|            | payment_token          | `address`                       | Address of the payment token                                  |
|            | maturity               | `uint256`                       | Maturity timestamp of the loan                                |
|            | start_time             | `uint256`                       | Start timestamp of the loan                                   |
|            | borrower               | `address`                       | Address of the borrower                                       |
|            | lender                 | `address`                       | Address of the lender                                         |
|            | collateral_contract    | `address`                       | Address of the collateral NFT contract                        |
|            | collateral_token_id    | `uint256`                       | Token ID of the collateral                                    |

##### Relevant external functions

| **Function**                   | **Roles Allowed**    | **Modifier** | **Description**                                                 |
| ---                            | :-:                  | ---          | ---                                                             |
| create_loan                    | Any                  | Nonpayable   | Creates a new loan based on a signed offer                      |
| settle_loan                    | Borrower             | Payable      | Settles an existing loan                                        |
| claim_defaulted_loan_collateral| Lender               | Nonpayable   | Claims collateral for a defaulted loan                          |
| replace_loan                   | Borrower             | Payable      | Replaces an existing loan with a new one                        |
| replace_loan_lender            | Lender               | Payable      | Replaces a loan by the lender                                   |
| revoke_offer                   | Lender               | Nonpayable   | Revokes a signed offer                                          |
| set_protocol_fee               | Owner                | Nonpayable   | Sets the protocol fee                                           |
| change_protocol_wallet         | Owner                | Nonpayable   | Changes the protocol wallet address                             |
| set_proxy_authorization        | Owner                | Nonpayable   | Sets authorization for a proxy address                          |


#### P2P Lending Control Contract (`P2PLendingControl.vy`)

The P2P Lending Control contract manages lending parameters for P2P lending contracts, including whitelisted collections and broker pre-agreements.

##### State variables

| **Variable**             | **Type**                    | **Mutable** | **Description**                                                                |
| ---                      | ---                         | :-:         | ---                                                                             |
| owner                    | `address`                   | Yes         | Address of the contract owner                                                   |
| proposed_owner           | `address`                   | Yes         | Address of the proposed new owner                                               |
| max_broker_lock_duration | `uint256`                   | Yes         | Maximum duration for broker locks                                               |
| whitelisted              | `HashMap[address, bool]`    | Yes         | Mapping of whitelisted collection addresses                                     |
| broker_locks             | `HashMap[bytes32, BrokerLock]` | Yes      | Mapping of broker locks for collaterals                                         |

##### Structs

| **Struct**      | **Variable**    | **Type**    | **Description**                                               |
| ---             | ---             | ---         | ---                                                           |
| BrokerLock      | broker          | `address`   | Address of the broker                                         |
|                 | expiration      | `uint256`   | Expiration timestamp of the broker lock                       |
| WhitelistRecord | collection      | `address`   | Address of the collection                                     |
|                 | whitelisted     | `bool`      | Whitelisted status of the collection                          |
| CollateralStatus| broker_lock     | `BrokerLock`| Broker lock information for the collateral                    |
|                 | whitelisted     | `bool`      | Whitelisted status of the collateral collection               |

##### Relevant external functions

| **Function**                   | **Roles Allowed** | **Modifier** | **Description**                                                            |
| ---                            | :-:               | ---          | ---                                                                        |
| propose_owner                  | Owner             | Nonpayable   | Proposes a new owner for the contract                                      |
| claim_ownership                | Proposed Owner    | Nonpayable   | Allows the proposed owner to claim ownership                               |
| change_whitelisted_collections | Owner             | Nonpayable   | Updates the whitelisted status of collections                              |
| set_max_broker_lock_duration   | Owner             | Nonpayable   | Sets the maximum duration for broker locks                                 |
| add_broker_lock                | Collateral Owner  | Nonpayable   | Adds a broker lock for a specific collateral                               |
| remove_broker_lock             | Broker            | Nonpayable   | Removes a broker lock for a specific collateral                            |
| get_broker_lock                | Any               | View         | Retrieves the broker lock for a specific collateral                        |
| get_collateral_status          | Any               | View         | Retrieves the collateral status including broker lock and whitelist status |


### Testing

There are two types of tests implemented, running on py-evm using titanoboa:
1. Unit tests focus on individual functions for each contract, mocking external dependencies (eg WETH and delegation contracts)
2. Integration tests run on a forked chain, testing the integration between the contracts in the protocol and real implementations of the external dependencies

Additionaly, under `contracts/auxiliary` there are mock implementations of external dependencies **which are NOT part of the protocol** and are only used to support deployments in private and test networks:
```
contracts/
└── auxiliary
    ├── CryptoPunksMarketMock.vy
    ├── DelegationRegistryMock.vy
    ├── ERC20.vy
    ├── ERC721.vy
    └── WETH9Mock.vy
```

* The `ERC20.vy` and `ERC721.vy` contracts are used to deploy mock ERC20 and ERC721 tokens, respectively. 
* The `CryptoPunksMarketMock.vy` contract mocks the [CryptoPunksMarket](https://etherscan.io/token/0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb#code) contract.
* The `DelegationRegistryMock.vy` contract is used to deploy a mock implementation of the [delegate.xyz](https://delegate.xyz/) delegation contract V2.
* The `WETH9Mock.vy` contract mocks the [Wrapped Ether](https://etherscan.io/address/0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2#code) contract.

### Run the project

Run the following command to set everything up:
```
make install-dev
```

To run the tests:
* unit tests
```
make unit-tests
```
* integration tests
```
make integration-tests
```
* coverage
```
make coverage
```
* gas profiling
```
make gas
```

### Deployment

For each environment a makefile rule is available to deploy the contracts, eg for DEV:
```
make deploy-dev
```

Because the protocol depends on external contracts that may not be available in all environments, mocks are also deployed to replace them if needed.


| **Component**             | **DEV**                       | **INT**                                                                                                   | **PROD**                                                                                                                                 |
| ------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Network**               | Private network               | Sepolia                                                                                                   | Mainnet                                                                                                                                  |
| **Payment Contract**      | Mock (`ERC20.vy`)             | Mock (`ERC20.vy`)                                                                                         | USDC `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`                                                                                        |
| **WETH Contract**         | Mock (`WETH9Mock.vy`)         | Mock (`WETH9Mock.vy`)                                                                                     | WETH9 `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`                                                                                       |
| **NFT Contract**          | Mock (`ERC721.vy`)            | Mock (`ERC721.vy`)                                                                                        | Several, eg Koda `0xE012Baf811CF9c05c408e879C399960D1f305903`                                                                            |
| **Delegation Contract**   | Mock (`HotWalletMock.vy`)     | delegate.xyz DelegateRegistry `0x00000000000000447e69651d841bD8D104Bed493`                                | delegate.xyz DelegateRegistry `0x00000000000000447e69651d841bD8D104Bed493`                                                               |

Additionally, for each P2P Lending Market in each environment (e.g., NFTs backed USDC Loans PROD), the following contracts are deployed (the `P2PLendingControl` may be shared between Lending Markets):

| **Contract**        | **Deployment parameters**               | **Description**                                 |
| ---                 | ---                                     | ---                                             |
| `P2PLendingNfts`    | `_payment_token: address`               | Address of the payment token (ERC20) contract   |
|                     | `_max_protocol_settlement_fee: uint256` | Maximum protocol settlement fee                 |
|                     | `_delegation_registry: address`         | Address of the delegation registry              |
|                     | `_weth9: address`                       | Address of the WETH9 contract                   |
|                     | `_cryptopunks: address`                 | Address of the CryptoPunksMarket contract       |
|                     | `_controller: address`                  | Address of the P2PLendingControl contract       |
| `P2PLendingControl` | `_cryptopunks: address`                 | Address of the CryptoPunksMarket contract       |
|                     | `_max_broker_lock_duration: uint256`    | Maximum duration for broker locks on collateral |


# @version 0.4.1


# Interfaces

from ethereum.ercs import IERC721
from ethereum.ercs import IERC20


interface P2PLendingNfts:
    def claim_defaulted_loan_collateral(loan: Loan): nonpayable

# Structs

PROOF_MAX_SIZE: constant(uint256) = 32
MAX_FEES: constant(uint256) = 4
BPS: constant(uint256) = 10000

flag FeeType:
    PROTOCOL_FEE
    ORIGINATION_FEE
    LENDER_BROKER_FEE
    BORROWER_BROKER_FEE

flag OfferType:
    TOKEN
    COLLECTION
    TRAIT

struct Fee:
    type: FeeType
    upfront_amount: uint256
    interest_bps: uint256
    wallet: address

struct FeeAmount:
    type: FeeType
    amount: uint256
    wallet: address

struct Offer:
    principal: uint256
    interest: uint256
    payment_token: address
    duration: uint256
    origination_fee_amount: uint256
    broker_upfront_fee_amount: uint256
    broker_settlement_fee_bps: uint256
    broker_address: address
    offer_type: OfferType
    token_id: uint256
    token_range_min: uint256
    token_range_max: uint256
    collection_key_hash: bytes32
    trait_hash: bytes32
    expiration: uint256
    lender: address
    pro_rata: bool
    size: uint256
    tracing_id: bytes32


struct Signature:
    v: uint256
    r: uint256
    s: uint256

struct SignedOffer:
    offer: Offer
    signature: Signature

struct Loan:
    id: bytes32
    offer_id: bytes32
    offer_tracing_id: bytes32
    amount: uint256  # principal - origination_fee_amount
    interest: uint256
    payment_token: address
    maturity: uint256
    start_time: uint256
    borrower: address
    lender: address
    collateral_contract: address
    collateral_token_id: uint256
    fees: DynArray[Fee, MAX_FEES]
    pro_rata: bool
    delegate: address


struct CollectionStatus:
    contract: address
    trait_root: bytes32

struct PunkOffer:
    isForSale: bool
    punkIndex: uint256
    seller: address
    minValue: uint256
    onlySellTo: address

event LoanCreated:
    id: bytes32
    amount: uint256
    interest: uint256
    payment_token: address
    maturity: uint256
    start_time: uint256
    borrower: address
    lender: address
    collateral_contract: address
    collateral_token_id: uint256
    fees: DynArray[Fee, MAX_FEES]
    pro_rata: bool
    offer_id: bytes32
    offer_tracing_id: bytes32
    delegate: address

event LoanReplaced:
    id: bytes32
    amount: uint256
    interest: uint256
    payment_token: address
    maturity: uint256
    start_time: uint256
    collateral_contract: address
    collateral_token_id: uint256
    borrower: address
    lender: address
    fees: DynArray[Fee, MAX_FEES]
    pro_rata: bool
    original_loan_id: bytes32
    paid_principal: uint256
    paid_interest: uint256
    paid_settlement_fees: DynArray[FeeAmount, MAX_FEES]
    offer_id: bytes32
    offer_tracing_id: bytes32

event LoanReplacedByLender:
    id: bytes32
    amount: uint256
    interest: uint256
    payment_token: address
    maturity: uint256
    start_time: uint256
    collateral_contract: address
    collateral_token_id: uint256
    borrower: address
    lender: address
    fees: DynArray[Fee, MAX_FEES]
    pro_rata: bool
    original_loan_id: bytes32
    paid_principal: uint256
    paid_interest: uint256
    paid_settlement_fees: DynArray[FeeAmount, MAX_FEES]
    borrower_compensation: uint256
    offer_id: bytes32
    offer_tracing_id: bytes32

event LoanPaid:
    id: bytes32
    borrower: address
    lender: address
    payment_token: address
    paid_principal: uint256
    paid_interest: uint256
    paid_settlement_fees: DynArray[FeeAmount, MAX_FEES]

event LoanCollateralClaimed:
    id: bytes32
    borrower: address
    lender: address
    collateral_contract: address
    collateral_token_id: uint256

event OfferRevoked:
    offer_id: bytes32
    lender: address
    collection_key_hash: bytes32
    offer_type: OfferType

event OwnerProposed:
    owner: address
    proposed_owner: address

event OwnershipTransferred:
    old_owner: address
    new_owner: address

event ProtocolFeeSet:
    old_upfront_fee: uint256
    old_settlement_fee: uint256
    new_upfront_fee: uint256
    new_settlement_fee: uint256

event ProtocolWalletChanged:
    old_wallet: address
    new_wallet: address

event ProxyAuthorizationChanged:
    proxy: address
    value: bool

event TransferFailed:
    _to: address
    amount: uint256

event PendingTransfersClaimed:
    _to: address
    amount: uint256




@deploy
def __init__():
    pass

@external
def claim_defaulted_loan_collateral(p2p_contract_address: address, loan: Loan):
    extcall P2PLendingNfts(p2p_contract_address).claim_defaulted_loan_collateral(loan)


@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)

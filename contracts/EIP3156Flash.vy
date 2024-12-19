# @version 0.3.10

from vyper.interfaces import ERC165 as IERC165
from vyper.interfaces import ERC721 as IERC721
from vyper.interfaces import ERC20 as IERC20


interface P2PLendingNfts:
    def create_loan(
        offer: SignedOffer,
        collateral_token_id: uint256,
        collateral_proof: DynArray[bytes32, 32],
        delegate: address,
        borrower_broker_upfront_fee_amount: uint256,
        borrower_broker_settlement_fee_bps: uint256,
        borrower_broker: address
    ) -> bytes32: nonpayable
    def settle_loan(loan: Loan): nonpayable
    def claim_defaulted_loan_collateral(loan: Loan): nonpayable
    def replace_loan(
        loan: Loan,
        offer: SignedOffer,
        collateral_proof: DynArray[bytes32, 32],
        borrower_broker_upfront_fee_amount: uint256,
        borrower_broker_settlement_fee_bps: uint256,
        borrower_broker: address
    ) -> bytes32: nonpayable
    def replace_loan_lender(loan: Loan, offer: SignedOffer, collateral_proof: DynArray[bytes32, 32]) -> bytes32: nonpayable
    def revoke_offer(offer: SignedOffer): nonpayable
    def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4: view
    def payment_token() -> address: view


# https://eips.ethereum.org/EIPS/eip-3156
interface IFlashLender:
    def maxFlashLoan(token: address) -> uint256: view
    def flashFee(token: address, amount: uint256) -> uint256: view
    def flashLoan(receiver: address, token: address, amount: uint256, data: Bytes[1024]) -> bool: nonpayable

enum FeeType:
    PROTOCOL_FEE
    ORIGINATION_FEE
    LENDER_BROKER_FEE
    BORROWER_BROKER_FEE


struct Fee:
    type: FeeType
    upfront_amount: uint256
    interest_bps: uint256
    wallet: address

struct FeeAmount:
    type: FeeType
    amount: uint256
    wallet: address

enum OfferType:
    TOKEN
    COLLECTION
    TRAIT

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

struct CallbackData:
    dummy: uint256

ERC3156_CALLBACK_OK: constant(bytes32) = keccak256("ERC3156FlashBorrower.onFlashLoan")

MAX_FEES: constant(uint256) = 4

p2p_lending_nfts: public(immutable(address))
flash_lender: public(immutable(address))

@external
def __init__(_p2p_lending_nfts: address, _flash_lender: address):
    p2p_lending_nfts = _p2p_lending_nfts
    flash_lender = _flash_lender


@external
def onFlashLoan(
    initiator: address,
    token: address,
    amount: uint256,
    fee: uint256,
    data: Bytes[1024]
) -> bytes32:

    raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"callback"))
    assert msg.sender == flash_lender, "unauthorized"
    assert initiator == self, "unknown initiator"
    assert fee == 0, "fee not supported"

    callback_data: CallbackData = _abi_decode(data, CallbackData)

    payment_token: address = P2PLendingNfts(p2p_lending_nfts).payment_token()
    assert token == payment_token, "Invalid asset"

    assert IERC20(payment_token).balanceOf(self) >= amount, "Insufficient balance"

    # do stuff with the flash loan

    IERC20(payment_token).approve(flash_lender, amount + fee)
    return ERC3156_CALLBACK_OK


@external
def flash_loan(amount: uint256):
    raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"flash loan"))
    payment_token: address = P2PLendingNfts(p2p_lending_nfts).payment_token()
    callback_data: CallbackData = CallbackData({dummy: 42})
    assert IFlashLender(flash_lender).flashLoan(self, payment_token, amount, _abi_encode(callback_data)), "flash loan failed"

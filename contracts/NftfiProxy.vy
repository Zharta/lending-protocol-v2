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
    def payment_token() -> address: view


interface NFTfi:
    def payBackLoan(loan_id: uint32): nonpayable


interface IFlashLender:
    def maxFlashLoan(token: address) -> uint256: view
    def flashFee(token: address, amount: uint256) -> uint256: view
    def flashLoan(receiver: address, token: address, amount: uint256, data: Bytes[10240]) -> bool: nonpayable


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


PROOF_MAX_SIZE: constant(uint256) = 32

struct CallbackData:
    nftfi_contract: address
    approved: address
    payment_token: address
    loan_id: uint256
    amount: uint256
    signed_offer: SignedOffer
    borrower: address
    token_id: uint256
    collateral_proof: DynArray[bytes32, PROOF_MAX_SIZE]
    delegate: address
    borrower_broker_upfront_fee_amount: uint256
    borrower_broker_settlement_fee_bps: uint256
    borrower_broker: address



ERC3156_CALLBACK_OK: constant(bytes32) = keccak256("ERC3156FlashBorrower.onFlashLoan")

MAX_FEES: constant(uint256) = 4
BPS: constant(uint256) = 10000

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
    data: Bytes[10240]
) -> bytes32:

    # raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"callback"))
    assert msg.sender == flash_lender, "unauthorized"
    assert initiator == self, "unknown initiator"
    assert fee == 0, "fee not supported"

    callback_data: CallbackData = _abi_decode(data, CallbackData)

    payment_token: address = P2PLendingNfts(p2p_lending_nfts).payment_token()
    assert token == payment_token, "Invalid asset"

    assert IERC20(payment_token).balanceOf(self) >= amount, "Insufficient balance"

    IERC20(payment_token).approve(callback_data.approved, amount)
    NFTfi(callback_data.nftfi_contract).payBackLoan(convert(callback_data.loan_id, uint32))

    self._create_loan(
        callback_data.signed_offer,
        callback_data.token_id,
        callback_data.collateral_proof,
        callback_data.delegate,
        callback_data.borrower_broker_upfront_fee_amount,
        callback_data.borrower_broker_settlement_fee_bps,
        callback_data.borrower_broker
    )

    IERC20(payment_token).transferFrom(callback_data.borrower, self, amount)
    assert IERC20(payment_token).balanceOf(self) >= amount, "Insufficient balance"

    IERC20(payment_token).approve(flash_lender, amount + fee)
    return ERC3156_CALLBACK_OK


@internal
def _create_loan(
    offer: SignedOffer,
    collateral_token_id: uint256,
    proof: DynArray[bytes32, 32],
    delegate: address,
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
) -> bytes32:
    return P2PLendingNfts(p2p_lending_nfts).create_loan(
        offer,
        collateral_token_id,
        proof,
        delegate,
        borrower_broker_upfront_fee_amount,
        borrower_broker_settlement_fee_bps,
        borrower_broker
    )


@external
def refinance_loan_balancer(
    nftfi_contract: address,
    approved: address,
    loan_id: uint256,
    amount: uint256,
    signed_offer: SignedOffer,
    token_id: uint256,
    collateral_proof: DynArray[bytes32, 32],
    delegate: address,
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
):

    # raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"refinance"))
    # TODO add checklist for nftfi contracts

    payment_token: address = P2PLendingNfts(p2p_lending_nfts).payment_token()
    callback_data: CallbackData = CallbackData({
        nftfi_contract: nftfi_contract,
        approved: approved,
        payment_token: payment_token,
        loan_id: loan_id,
        amount: amount,
        signed_offer: signed_offer,
        borrower: msg.sender,
        token_id: token_id,
        collateral_proof: collateral_proof,
        delegate: delegate,
        borrower_broker_upfront_fee_amount: borrower_broker_upfront_fee_amount,
        borrower_broker_settlement_fee_bps: borrower_broker_settlement_fee_bps,
        borrower_broker: borrower_broker
    })

    assert IFlashLender(flash_lender).flashLoan(self, payment_token, amount, _abi_encode(callback_data)), "flash loan failed"

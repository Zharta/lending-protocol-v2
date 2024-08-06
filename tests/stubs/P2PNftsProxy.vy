# @version 0.3.10

from vyper.interfaces import ERC165 as IERC165
from vyper.interfaces import ERC721 as IERC721
from vyper.interfaces import ERC20 as IERC20


interface P2PLendingNfts:
    def create_loan(offer: SignedOffer, collateral_token_id: uint256, delegate: address, borrower_broker_upfront_fee_amount: uint256, borrower_broker_settlement_fee_bps: uint256, borrower_broker: address) -> bytes32: nonpayable
    def settle_loan(loan: Loan): payable
    def claim_defaulted_loan_collateral(loan: Loan): nonpayable
    def replace_loan(loan: Loan, offer: SignedOffer, borrower_broker_upfront_fee_amount: uint256, borrower_broker_settlement_fee_bps: uint256, borrower_broker: address) -> bytes32: payable
    def replace_loan_lender(loan: Loan, offer: SignedOffer) -> bytes32: payable
    def revoke_offer(offer: SignedOffer): nonpayable


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

struct Offer:
    principal: uint256
    interest: uint256
    payment_token: address
    duration: uint256
    origination_fee_amount: uint256
    broker_upfront_fee_amount: uint256
    broker_settlement_fee_bps: uint256
    broker_address: address
    collateral_contract: address
    collateral_min_token_id: uint256
    collateral_max_token_id: uint256
    expiration: uint256
    lender: address
    pro_rata: bool
    size: uint256


struct Signature:
    v: uint256
    r: uint256
    s: uint256

struct SignedOffer:
    offer: Offer
    signature: Signature

struct Loan:
    id: bytes32
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


MAX_FEES: constant(uint256) = 4
BPS: constant(uint256) = 10000

p2p_lending_nfts: address

@external
def __init__(_p2p_lending_nfts: address):
    self.p2p_lending_nfts = _p2p_lending_nfts

@external
def create_loan(
    offer: SignedOffer,
    collateral_token_id: uint256,
    delegate: address,
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
) -> bytes32:
    return P2PLendingNfts(self.p2p_lending_nfts).create_loan(
        offer,
        collateral_token_id,
        delegate,
        borrower_broker_upfront_fee_amount,
        borrower_broker_settlement_fee_bps,
        borrower_broker
    )

@payable
@external
def settle_loan(loan: Loan):
    P2PLendingNfts(self.p2p_lending_nfts).settle_loan(loan, value=msg.value)

@external
def claim_defaulted_loan_collateral(loan: Loan):
    P2PLendingNfts(self.p2p_lending_nfts).claim_defaulted_loan_collateral(loan)

@payable
@external
def replace_loan(
    loan: Loan,
    offer: SignedOffer,
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
) -> bytes32:
    return P2PLendingNfts(self.p2p_lending_nfts).replace_loan(
        loan,
        offer,
        borrower_broker_upfront_fee_amount,
        borrower_broker_settlement_fee_bps,
        borrower_broker,
        value=msg.value
    )

@payable
@external
def replace_loan_lender(loan: Loan, offer: SignedOffer) -> bytes32:
    return P2PLendingNfts(self.p2p_lending_nfts).replace_loan_lender(loan, offer, value=msg.value)


@external
def revoke_offer(offer: SignedOffer):
    P2PLendingNfts(self.p2p_lending_nfts).revoke_offer(offer)


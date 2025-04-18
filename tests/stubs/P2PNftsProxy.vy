# @version 0.4.1

from ethereum.ercs import IERC165
from ethereum.ercs import IERC721
from ethereum.ercs import IERC20


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


flag FeeType:
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

flag OfferType:
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


TOKEN_IDS_BATCH: constant(uint256) = 1 << 14
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
    proof: DynArray[bytes32, 32],
    delegate: address,
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
) -> bytes32:
    return P2PLendingNfts(self.p2p_lending_nfts).create_loan(
        offer,
        collateral_token_id,
        proof,
        delegate,
        borrower_broker_upfront_fee_amount,
        borrower_broker_settlement_fee_bps,
        borrower_broker
    )

@external
def settle_loan(loan: Loan):
    P2PLendingNfts(self.p2p_lending_nfts).settle_loan(loan)

@external
def claim_defaulted_loan_collateral(loan: Loan):
    P2PLendingNfts(self.p2p_lending_nfts).claim_defaulted_loan_collateral(loan)

@external
def replace_loan(
    loan: Loan,
    offer: SignedOffer,
    proof: DynArray[bytes32, 32],
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
) -> bytes32:
    return P2PLendingNfts(self.p2p_lending_nfts).replace_loan(
        loan,
        offer,
        proof,
        borrower_broker_upfront_fee_amount,
        borrower_broker_settlement_fee_bps,
        borrower_broker
    )

@external
def replace_loan_lender(loan: Loan, offer: SignedOffer, proof: DynArray[bytes32, 32]) -> bytes32:
    return P2PLendingNfts(self.p2p_lending_nfts).replace_loan_lender(loan, offer, proof)


@external
def revoke_offer(offer: SignedOffer):
    P2PLendingNfts(self.p2p_lending_nfts).revoke_offer(offer)

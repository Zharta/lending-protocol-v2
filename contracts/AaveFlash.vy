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


interface IFlashLoanSimpleReceiver:
    def executeOperation(asset: address, amount: uint256, premium: uint256, initiator: address, params: Bytes[1024]) -> bool: nonpayable
    def ADDRESSES_PROVIDER() -> address: view
    def POOL() -> address: view


interface IPoolProvider:
    def getPool() -> address: view


interface IPool:
    def flashLoanSimple(
        receiverAddress: address,
        asset: address,
        amount: uint256,
        params: Bytes[1024],
        referralCode: uint16
    ): nonpayable



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


MAX_FEES: constant(uint256) = 4
BPS: constant(uint256) = 10000

p2p_lending_nfts: address
aave_pool_provider: address

@external
def __init__(_p2p_lending_nfts: address, _aave_pool_provider: address):
    self.p2p_lending_nfts = _p2p_lending_nfts
    self.aave_pool_provider = _aave_pool_provider



@external
def executeOperation(
    asset: address,
    amount: uint256,
    premium: uint256,
    initiator: address,
    params: Bytes[1024]
) -> bool:
    raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"callback"))
    assert initiator == self, "who are you?"
    aave_pool: address = IPoolProvider(self.aave_pool_provider).getPool()
    payment_token: address = P2PLendingNfts(self.p2p_lending_nfts).payment_token()

    # assert premium == 0, "Premium not supported"

    assert IERC20(payment_token).balanceOf(self) >= amount + premium, "Insufficient balance"
    assert msg.sender == aave_pool, "Unauthorized"
    assert asset == payment_token, "Invalid asset"

# do stuff with the amount

    IERC20(payment_token).approve(aave_pool, amount + premium)

    return True


@external
@view
def ADDRESSES_PROVIDER() -> address:
    return self.aave_pool_provider

@external
@view
def POOL() -> address:
    return IPoolProvider(self.aave_pool_provider).getPool()

@external
def flash_loan(amount: uint256):
    raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"flash loan"))
    aave_pool: address = IPoolProvider(self.aave_pool_provider).getPool()
    payment_token: address = P2PLendingNfts(self.p2p_lending_nfts).payment_token()
    IERC20(payment_token).transferFrom(msg.sender, self, amount) # remove
    IPool(aave_pool).flashLoanSimple(self, payment_token, amount, b"", 0)

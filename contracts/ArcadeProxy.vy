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


interface Arcade:
    def repay(loan_id: uint256): nonpayable


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
    arcade_contract: address
    approved: address
    payment_token: address
    loan_id: uint256
    amount: uint256
    signed_offer: SignedOffer
    borrower: address
    token_id: uint256




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
    # raw_call(0x0000000000000000000000000000000000011111, _abi_encode(initiator))

    assert initiator == self, "who are you?"
    aave_pool: address = IPoolProvider(self.aave_pool_provider).getPool()
    payment_token: address = P2PLendingNfts(self.p2p_lending_nfts).payment_token()

    # assert premium == 0, "Premium not supported"
    callback_data: CallbackData = _abi_decode(params, CallbackData)

    IERC20(payment_token).transferFrom(callback_data.borrower, self, premium)
    assert IERC20(payment_token).balanceOf(self) >= amount + premium, "Insufficient balance"
    assert msg.sender == aave_pool, "Unauthorized"
    assert asset == payment_token, "Invalid asset"

    IERC20(payment_token).approve(callback_data.approved, amount)
    Arcade(callback_data.arcade_contract).repay(callback_data.loan_id)

    self._create_loan(
        callback_data.signed_offer,
        callback_data.token_id,
        [],
        empty(address),
        0,
        0,
        empty(address)
    )

    assert IERC20(payment_token).balanceOf(callback_data.borrower) >= amount, "Insufficient balance"
    IERC20(payment_token).transferFrom(callback_data.borrower, self, amount)

    assert IERC20(payment_token).balanceOf(self) >= amount + premium, "Insufficient balance"
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
    raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"1"))
    aave_pool: address = IPoolProvider(self.aave_pool_provider).getPool()
    payment_token: address = P2PLendingNfts(self.p2p_lending_nfts).payment_token()
    IERC20(payment_token).transferFrom(msg.sender, self, amount) # remove
    IPool(aave_pool).flashLoanSimple(self, payment_token, amount, b"", 0)


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
def pay_arcade_loan(
    arcade_contract: address,
    approved: address,
    payment_token: address,
    loan_id: uint256,
    amount: uint256,
):
    assert IERC20(payment_token).balanceOf(msg.sender) >= amount, "Insufficient borrower balance"
    IERC20(payment_token).transferFrom(msg.sender, self, amount)
    IERC20(payment_token).approve(approved, amount)
    assert IERC20(payment_token).balanceOf(self) >= amount, "Insufficient balance"
    Arcade(arcade_contract).repay(loan_id)


@external
def refinance_loan(
    arcade_contract: address,
    approved: address,
    loan_id: uint256,
    amount: uint256,
    signed_offer: SignedOffer,
    token_id: uint256,
):

    raw_call(0x0000000000000000000000000000000000011111, _abi_encode(b"refinance"))

    aave_pool: address = IPoolProvider(self.aave_pool_provider).getPool()
    payment_token: address = P2PLendingNfts(self.p2p_lending_nfts).payment_token()
    callback_data: CallbackData = CallbackData({
        arcade_contract: arcade_contract,
        approved: approved,
        payment_token: payment_token,
        loan_id: loan_id,
        amount: amount,
        signed_offer: signed_offer,
        borrower: msg.sender,
        token_id: token_id
    })

    IPool(aave_pool).flashLoanSimple(self, payment_token, amount, _abi_encode(callback_data), 0)

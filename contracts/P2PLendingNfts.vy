# @version 0.3.10

"""
@title P2PLendingNfts
@author [Zharta](https://zharta.io/)
@notice This contract facilitates peer-to-peer lending using NFTs as collateral.
@dev It facilitates peer-to-peer lending using NFTs as collateral.
      The contract allows lenders to offer loans and borrowers to accept them by providing NFTs as collateral.
      Key functionalities include:
      - Creating and managing loan offers
      - Accepting loan offers and locking NFTs as collateral
      - Accepts ERC721 and CryptoPunks NFTs as collateral
      - Delegating the collateral using [Delegate](https://delegate.xyz/) DelegateRegistry v2
      - Settling loans by repaying the principal and interest
      - Claiming collateral in case of loan default
      - Replacing existing loans with new terms
      - Four types of fees are supported: protocol fee, origination fee, lender broker fee, and borrower broker fee
      - Managing protocol fees and authorized proxies
      - Handling ownership transfer of the contract
      - Loan state is kept hashed in the contract to save gas
      The contract ensures secure and transparent lending operations within the Zharta ecosystem.
"""

# Interfaces

from vyper.interfaces import ERC165 as IERC165
from vyper.interfaces import ERC721 as IERC721
from vyper.interfaces import ERC20 as IERC20


interface WETH:
    def deposit(): payable
    def withdraw(_amount: uint256): nonpayable
    def transferFrom(_from: address, _to: address, _amount: uint256) -> bool: nonpayable
    def transfer(_to : address, _value : uint256) -> bool: nonpayable

interface CryptoPunksMarket:
    def transferPunk(to: address, punkIndex: uint256): nonpayable
    def buyPunk(punkIndex: uint256): payable
    def punksOfferedForSale(punkIndex: uint256) -> PunkOffer: view
    def punkIndexToAddress(punkIndex: uint256) -> address: view
    def offerPunkForSaleToAddress(punkIndex: uint256, minSalePriceInWei: uint256, toAddress: address): nonpayable

interface DelegationRegistry:
    def delegateERC721(delegate: address, contract: address, token_id: uint256, rights: bytes32, _value: bool) -> bytes32: nonpayable


# Structs

WHITELIST_BATCH: constant(uint256) = 100
TOKEN_IDS_BATCH: constant(uint256) = 1 << 8
MAX_FEES: constant(uint256) = 4
BPS: constant(uint256) = 10000

enum FeeType:
    PROTOCOL_FEE
    ORIGINATION_FEE
    LENDER_BROKER_FEE
    BORROWER_BROKER_FEE

enum OfferType:
    TOKEN
    COLLECTION

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
    offer_type: OfferType
    token_ids: DynArray[uint256, TOKEN_IDS_BATCH]
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


struct WhitelistRecord:
    collection: address
    whitelisted: bool


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
    collateral_contract: address
    offer_type: OfferType
    token_ids: DynArray[uint256, TOKEN_IDS_BATCH]

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

event WhitelistChanged:
    changed: DynArray[WhitelistRecord, WHITELIST_BATCH]


# Global variables

owner: public(address)
proposed_owner: public(address)

payment_token: public(immutable(address))
loans: public(HashMap[bytes32, bytes32])
delegation_registry: public(immutable(DelegationRegistry))
cryptopunks: public(immutable(CryptoPunksMarket))

protocol_wallet: public(address)
protocol_upfront_fee: public(uint256)
protocol_settlement_fee: public(uint256)
max_protocol_upfront_fee: public(immutable(uint256))
max_protocol_settlement_fee: public(immutable(uint256))
max_lender_broker_settlement_fee: public(immutable(uint256))
max_borrower_broker_settlement_fee: public(immutable(uint256))

offer_count: public(HashMap[bytes32, uint256])
revoked_offers: public(HashMap[bytes32, bool])

authorized_proxies: public(HashMap[address, bool])
whitelisted: public(HashMap[address, bool])

VERSION: constant(String[30]) = "P2PLendingNfts.20240916"

ZHARTA_DOMAIN_NAME: constant(String[6]) = "Zharta"
ZHARTA_DOMAIN_VERSION: constant(String[1]) = "1"

DOMAIN_TYPE_HASH: constant(bytes32) = keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
OFFER_TYPE_DEF: constant(String[330]) = "Offer(uint256 principal,uint256 interest,address payment_token,uint256 duration,uint256 origination_fee_amount," \
                                        "uint256 broker_upfront_fee_amount,uint256 broker_settlement_fee_bps,address broker_address,address collateral_contract," \
                                        "uint256 offer_type,uint256[] token_ids,uint256 expiration,address lender,bool pro_rata,uint256 size)"
OFFER_TYPE_HASH: constant(bytes32) = keccak256(OFFER_TYPE_DEF)

offer_sig_domain_separator: immutable(bytes32)


@external
def __init__(
    _payment_token: address,
    _delegation_registry: address,
    _cryptopunks: address,
    _protocol_upfront_fee: uint256,
    _protocol_settlement_fee: uint256,
    _protocol_wallet: address,
    _max_protocol_upfront_fee: uint256,
    _max_protocol_settlement_fee: uint256,
    _max_lender_broker_settlement_fee: uint256,
    _max_borrower_broker_settlement_fee: uint256,
):

    """
    @notice Initialize the contract with the given parameters.
    @param _payment_token The address of the payment token.
    @param _delegation_registry The address of the delegation registry.
    @param _cryptopunks The address of the CryptoPunksMarket contract.
    @param _protocol_upfront_fee The percentage (bps) of the principal paid to the protocol at origination.
    @param _protocol_settlement_fee The percentage (bps) of the interest paid to the protocol at settlement.
    @param _protocol_wallet The address where the protocol fees are accrued.
    """

    assert _protocol_wallet != empty(address), "wallet is the zero address"
    assert _payment_token != empty(address), "payment token is zero"
    assert _delegation_registry != empty(address), "delegation registry is zero"
    assert _cryptopunks != empty(address), "cryptopunks is zero"

    assert _protocol_upfront_fee <= _max_protocol_upfront_fee, "upfront fee exceeds max"
    assert _protocol_settlement_fee <= _max_protocol_settlement_fee, "settlement fee exceeds max"

    self.owner = msg.sender
    payment_token = _payment_token
    delegation_registry = DelegationRegistry(_delegation_registry)
    cryptopunks = CryptoPunksMarket(_cryptopunks)
    max_protocol_upfront_fee = _max_protocol_upfront_fee
    max_protocol_settlement_fee = _max_protocol_settlement_fee
    max_lender_broker_settlement_fee = _max_lender_broker_settlement_fee
    max_borrower_broker_settlement_fee = _max_borrower_broker_settlement_fee
    self.protocol_upfront_fee = _protocol_upfront_fee
    self.protocol_settlement_fee = _protocol_settlement_fee
    self.protocol_wallet = _protocol_wallet

    offer_sig_domain_separator = keccak256(
        _abi_encode(
            DOMAIN_TYPE_HASH,
            keccak256(ZHARTA_DOMAIN_NAME),
            keccak256(ZHARTA_DOMAIN_VERSION),
            chain.id,
            self
        )
    )



# Config functions


@external
def set_protocol_fee(protocol_upfront_fee: uint256, protocol_settlement_fee: uint256):

    """
    @notice Set the protocol fee
    @dev Sets the protocol fee to the given value and logs the event. Admin function.
    @param protocol_upfront_fee The new protocol upfront fee.
    @param protocol_settlement_fee The new protocol settlement fee.
    """

    assert msg.sender == self.owner, "not owner"
    assert protocol_upfront_fee <= max_protocol_upfront_fee, "upfront fee exceeds max"
    assert protocol_settlement_fee <= max_protocol_settlement_fee, "settlement fee exceeds max"

    log ProtocolFeeSet(self.protocol_upfront_fee, self.protocol_settlement_fee, protocol_upfront_fee, protocol_settlement_fee)
    self.protocol_upfront_fee = protocol_upfront_fee
    self.protocol_settlement_fee = protocol_settlement_fee


@external
def change_protocol_wallet(new_protocol_wallet: address):

    """
    @notice Change the protocol wallet
    @dev Changes the protocol wallet to the given address and logs the event. Admin function.
    @param new_protocol_wallet The new protocol wallet.
    """

    assert msg.sender == self.owner, "not owner"
    assert new_protocol_wallet != empty(address), "wallet is the zero address"

    log ProtocolWalletChanged(self.protocol_wallet, new_protocol_wallet)
    self.protocol_wallet = new_protocol_wallet


@external
def set_proxy_authorization(_proxy: address, _value: bool):

    """
    @notice Set authorization
    @dev Sets the authorization for the given proxy and logs the event. Admin function.
    @param _proxy The address of the proxy.
    @param _value The value of the authorization.
    """

    assert msg.sender == self.owner, "not owner"

    self.authorized_proxies[_proxy] = _value

    log ProxyAuthorizationChanged(_proxy, _value)


@external
def propose_owner(_address: address):

    """
    @notice Propose a new owner
    @dev Proposes a new owner and logs the event. Admin function.
    @param _address The address of the proposed owner.
    """

    assert msg.sender == self.owner, "not owner"
    assert _address != empty(address), "_address is zero"

    log OwnerProposed(self.owner, _address)
    self.proposed_owner = _address


@external
def claim_ownership():

    """
    @notice Claim the ownership of the contract
    @dev Claims the ownership of the contract and logs the event. Requires the caller to be the proposed owner.
    """

    assert msg.sender == self.proposed_owner, "not the proposed owner"

    log OwnershipTransferred(self.owner, self.proposed_owner)
    self.owner = msg.sender
    self.proposed_owner = empty(address)


@external
def change_whitelisted_collections(collections: DynArray[WhitelistRecord, WHITELIST_BATCH]):
    """
    @notice Set whitelisted collections
    @param collections array of WhitelistRecord
    """
    assert msg.sender == self.owner, "sender not owner"
    for c in collections:
        self.whitelisted[c.collection] = c.whitelisted

    log WhitelistChanged(collections)


# Core functions

@external
def create_loan(
    offer: SignedOffer,
    collateral_token_id: uint256,
    delegate: address,
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
) -> bytes32:

    """
    @notice Create a loan.
    @param offer The signed offer.
    @param collateral_token_id The ID of the collateral token.
    @param delegate The address of the delegate. If empty, no delegation is set.
    @param borrower_broker_upfront_fee_amount The upfront fee amount for the borrower broker.
    @param borrower_broker_settlement_fee_bps The settlement fee basis points relative to the interest for the borrower broker.
    @param borrower_broker The address of the borrower broker.
    @return The ID of the created loan.
    """


    assert self._is_offer_signed_by_lender(offer, offer.offer.lender), "offer not signed by lender"
    assert offer.offer.expiration > block.timestamp, "offer expired"
    assert offer.offer.payment_token == payment_token, "invalid payment token"
    assert offer.offer.origination_fee_amount <= offer.offer.principal, "origination fee gt principal"

    assert self.whitelisted[offer.offer.collateral_contract], "collateral not whitelisted"
    self._validate_token_ids(offer.offer, collateral_token_id)

    fees: DynArray[Fee, MAX_FEES] = self._get_loan_fees(offer.offer, borrower_broker_upfront_fee_amount, borrower_broker_settlement_fee_bps, borrower_broker)
    total_upfront_fees: uint256 = 0
    for fee in fees:
        total_upfront_fees += fee.upfront_amount

    loan: Loan = Loan({
        id: empty(bytes32),
        amount: offer.offer.principal,
        interest: offer.offer.interest,
        payment_token: offer.offer.payment_token,
        maturity: block.timestamp + offer.offer.duration,
        start_time: block.timestamp,
        borrower: msg.sender if not self.authorized_proxies[msg.sender] else tx.origin,
        lender: offer.offer.lender,
        collateral_contract: offer.offer.collateral_contract,
        collateral_token_id: collateral_token_id,
        fees: fees,
        pro_rata: offer.offer.pro_rata
    })
    loan.id = self._compute_loan_id(loan)

    assert self.loans[loan.id] == empty(bytes32), "loan already exists"
    self._check_and_update_offer_state(offer)
    self.loans[loan.id] = self._loan_state_hash(loan)

    self._store_collateral(loan.borrower, loan.collateral_contract, loan.collateral_token_id)
    self._transfer_funds(loan.lender, loan.borrower, loan.amount - total_upfront_fees + offer.offer.broker_upfront_fee_amount)

    for fee in fees:
        if fee.type != FeeType.ORIGINATION_FEE and fee.upfront_amount > 0:
            self._transfer_funds(loan.lender, fee.wallet, fee.upfront_amount)

    self._set_delegation(delegate, loan.collateral_contract, loan.collateral_token_id, delegate != empty(address))

    log LoanCreated(
        loan.id,
        loan.amount,
        loan.interest,
        loan.payment_token,
        loan.maturity,
        loan.start_time,
        loan.borrower,
        loan.lender,
        loan.collateral_contract,
        loan.collateral_token_id,
        loan.fees,
        loan.pro_rata,
        self._compute_signed_offer_id(offer)
    )
    return loan.id


@external
def settle_loan(loan: Loan):

    """
    @notice Settle a loan.
    @param loan The loan to be settled.
    """

    assert self._is_loan_valid(loan), "invalid loan"
    assert block.timestamp <= loan.maturity, "loan defaulted"
    assert self._check_user(loan.borrower), "not borrower"

    interest: uint256 = self._compute_settlement_interest(loan)
    settlement_fees_total: uint256 = 0
    settlement_fees: DynArray[FeeAmount, MAX_FEES] = []
    settlement_fees, settlement_fees_total = self._get_settlement_fees(loan, interest)

    self.loans[loan.id] = empty(bytes32)

    self._receive_funds(loan.borrower, loan.amount + interest)

    self._send_funds(loan.lender, loan.amount + interest - settlement_fees_total)
    for fee in settlement_fees:
        self._send_funds(fee.wallet, fee.amount)

    self._transfer_collateral(loan.borrower, loan.collateral_contract, loan.collateral_token_id)

    log LoanPaid(
        loan.id,
        loan.borrower,
        loan.lender,
        loan.payment_token,
        loan.amount,
        interest,
        settlement_fees
    )


@external
def claim_defaulted_loan_collateral(loan: Loan):

    """
    @notice Claim defaulted loan collateral.
    @param loan The loan whose collateral is to be claimed. The loan maturity must have been passed.
    """

    assert self._is_loan_valid(loan), "invalid loan"
    assert block.timestamp > loan.maturity, "loan not defaulted"
    assert self._check_user(loan.lender), "not lender"

    self.loans[loan.id] = empty(bytes32)

    self._transfer_collateral(loan.lender, loan.collateral_contract, loan.collateral_token_id)

    log LoanCollateralClaimed(
        loan.id,
        loan.borrower,
        loan.lender,
        loan.collateral_contract,
        loan.collateral_token_id
    )


@external
def replace_loan(
    loan: Loan,
    offer: SignedOffer,
    borrower_broker_upfront_fee_amount: uint256,
    borrower_broker_settlement_fee_bps: uint256,
    borrower_broker: address
) -> bytes32:

    """
    @notice Replace an existing loan by accepting a new offer over the same collateral. The current loan is settled and the new loan is created. Must be called by the borrower.
    @dev No collateral transfer is required and the delegation is not changed. The borrower must be the same as the borrower of the current loan.
    @param loan The loan to be replaced.
    @param offer The new signed offer.
    @param borrower_broker_upfront_fee_amount The upfront fee amount for the borrower broker.
    @param borrower_broker_settlement_fee_bps The settlement fee basis points relative to the interest for the borrower broker.
    @param borrower_broker The address of the borrower broker, if any.
    @return The ID of the new loan.
    """

    assert self._is_loan_valid(loan), "invalid loan"
    assert self._check_user(loan.borrower), "not borrower"
    assert block.timestamp <= loan.maturity, "loan defaulted"

    assert self._is_offer_signed_by_lender(offer, offer.offer.lender), "offer not signed by lender"
    assert offer.offer.expiration > block.timestamp, "offer expired"
    assert offer.offer.payment_token == payment_token, "invalid payment token"
    assert offer.offer.origination_fee_amount <= offer.offer.principal, "origination fee gt principal"

    assert self.whitelisted[offer.offer.collateral_contract], "collateral not whitelisted"

    self._validate_token_ids(offer.offer, loan.collateral_token_id)
    assert offer.offer.collateral_contract == loan.collateral_contract, "collateral contract mismatch"

    self._check_and_update_offer_state(offer)

    principal_delta: int256 = convert(offer.offer.principal, int256) - convert(loan.amount, int256)
    interest: uint256 = self._compute_settlement_interest(loan)

    settlement_fees_total: uint256 = 0
    settlement_fees: DynArray[FeeAmount, MAX_FEES] = []
    settlement_fees, settlement_fees_total = self._get_settlement_fees(loan, interest)

    new_loan_fees: DynArray[Fee, MAX_FEES] = self._get_loan_fees(offer.offer, borrower_broker_upfront_fee_amount, borrower_broker_settlement_fee_bps, borrower_broker)
    total_upfront_fees: uint256 = 0
    for fee in new_loan_fees:
        total_upfront_fees += fee.upfront_amount

    self.loans[loan.id] = empty(bytes32)

    borrower_delta: int256 = principal_delta - convert(total_upfront_fees, int256) + convert(offer.offer.broker_upfront_fee_amount, int256) - convert(interest, int256)
    current_lender_delta: uint256 = loan.amount + interest - settlement_fees_total
    new_lender_delta_abs: uint256 = offer.offer.principal - offer.offer.origination_fee_amount + offer.offer.broker_upfront_fee_amount

    if borrower_delta < 0:
        self._receive_funds(loan.borrower, convert(-1 * borrower_delta, uint256))

    if loan.lender != offer.offer.lender:
        self._receive_funds(offer.offer.lender, new_lender_delta_abs)
        self._send_funds(loan.lender, current_lender_delta)
    elif current_lender_delta > new_lender_delta_abs:
        self._send_funds(loan.lender, current_lender_delta - new_lender_delta_abs)
    elif current_lender_delta < new_lender_delta_abs:
        self._receive_funds(loan.lender, new_lender_delta_abs - current_lender_delta)

    if borrower_delta > 0:
        self._send_funds(loan.borrower, convert(borrower_delta, uint256))

    for fee in settlement_fees:
        self._send_funds(fee.wallet, fee.amount)

    for fee in new_loan_fees:
        if fee.type != FeeType.ORIGINATION_FEE and fee.upfront_amount > 0:
            self._send_funds(fee.wallet, fee.upfront_amount)

    new_loan: Loan = Loan({
        id: empty(bytes32),
        amount: offer.offer.principal,
        interest: offer.offer.interest,
        payment_token: offer.offer.payment_token,
        maturity: block.timestamp + offer.offer.duration,
        start_time: block.timestamp,
        borrower: loan.borrower,
        lender: offer.offer.lender,
        collateral_contract: offer.offer.collateral_contract,
        collateral_token_id: loan.collateral_token_id,
        fees: new_loan_fees,
        pro_rata: offer.offer.pro_rata
    })
    new_loan.id = self._compute_loan_id(new_loan)

    assert self.loans[new_loan.id] == empty(bytes32), "loan already exists"
    self.loans[new_loan.id] = self._loan_state_hash(new_loan)

    log LoanReplaced(
        new_loan.id,
        new_loan.amount,
        new_loan.interest,
        new_loan.payment_token,
        new_loan.maturity,
        new_loan.start_time,
        new_loan.collateral_contract,
        new_loan.collateral_token_id,
        new_loan.borrower,
        new_loan.lender,
        new_loan.fees,
        new_loan.pro_rata,
        loan.id,
        loan.amount,
        interest,
        settlement_fees,
        self._compute_signed_offer_id(offer)
    )

    return new_loan.id


@external
def replace_loan_lender(loan: Loan, offer: SignedOffer) -> bytes32:

    """
    @notice Replace a loan by the lender. The current loan is settled and the new loan is created. Must be called by the lender.
    @dev No collateral transfer is required and the delegation is not changed. The borrower must be the same as the borrower of the current loan. No funds are required from the borrower. Also no funds are required from the lender, except when the current and new lender are the same.
    @param loan The loan to be replaced.
    @param offer The new signed offer.
    @return The ID of the new loan.
    """

    assert self._is_loan_valid(loan), "invalid loan"
    assert self._check_user(loan.lender), "not lender"
    assert block.timestamp <= loan.maturity, "loan defaulted"

    assert self._is_offer_signed_by_lender(offer, offer.offer.lender), "offer not signed by lender"
    assert offer.offer.expiration > block.timestamp, "offer expired"
    assert offer.offer.payment_token == payment_token, "invalid payment token"
    assert offer.offer.origination_fee_amount <= offer.offer.principal, "origination fee gt principal"
    assert block.timestamp + offer.offer.duration >= loan.maturity, "maturity before loan maturity"

    assert self.whitelisted[offer.offer.collateral_contract], "collateral not whitelisted"

    self._validate_token_ids(offer.offer, loan.collateral_token_id)
    assert offer.offer.collateral_contract == loan.collateral_contract, "collateral contract mismatch"

    self._check_and_update_offer_state(offer)

    principal_delta: int256 = convert(offer.offer.principal, int256) - convert(loan.amount, int256)
    interest: uint256 = self._compute_settlement_interest(loan)

    settlement_fees_total: uint256 = 0
    settlement_fees: DynArray[FeeAmount, MAX_FEES] = []
    settlement_fees, settlement_fees_total = self._get_settlement_fees(loan, interest)

    new_loan_fees: DynArray[Fee, MAX_FEES] = self._get_loan_fees(offer.offer, 0, 0, empty(address))
    total_upfront_fees: uint256 = 0
    for fee in new_loan_fees:
        total_upfront_fees += fee.upfront_amount

    self.loans[loan.id] = empty(bytes32)

    max_interest_delta: uint256 = self._compute_max_interest_delta(loan, offer.offer, interest)
    borrower_compensation: uint256 = convert(max(convert(max_interest_delta, int256), convert(interest, int256) - principal_delta), uint256)

    borrower_delta: int256 = principal_delta - convert(interest, int256) + convert(borrower_compensation, int256)
    current_lender_delta: int256 = convert(loan.amount + interest + offer.offer.broker_upfront_fee_amount, int256) - convert(total_upfront_fees + settlement_fees_total + borrower_compensation, int256)
    new_lender_delta_abs: uint256 = offer.offer.principal - offer.offer.origination_fee_amount + offer.offer.broker_upfront_fee_amount

    assert borrower_delta >= 0, "borrower delta < 0"

    if loan.lender != offer.offer.lender:
        assert current_lender_delta >= 0, "lender delta < 0"
        self._receive_funds(offer.offer.lender, new_lender_delta_abs)
        if current_lender_delta > 0:
            self._send_funds(loan.lender, convert(current_lender_delta, uint256))
    else:
        lender_delta: int256 = current_lender_delta - convert(new_lender_delta_abs, int256)

        # cant have lender delta > 0 and borrower delta >= 0
        assert lender_delta <= 0, "lender delta > 0"

        if lender_delta < 0:
            self._receive_funds(loan.lender, convert(-1 * lender_delta, uint256))

    if borrower_delta > 0:
        self._send_funds(loan.borrower, convert(borrower_delta, uint256))

    for fee in settlement_fees:
        self._send_funds(fee.wallet, fee.amount)

    for fee in new_loan_fees:
        if fee.type != FeeType.ORIGINATION_FEE and fee.upfront_amount > 0:
            self._send_funds(fee.wallet, fee.upfront_amount)

    new_loan: Loan = Loan({
        id: empty(bytes32),
        amount: offer.offer.principal,
        interest: offer.offer.interest,
        payment_token: offer.offer.payment_token,
        maturity: block.timestamp + offer.offer.duration,
        start_time: block.timestamp,
        borrower: loan.borrower,
        lender: offer.offer.lender,
        collateral_contract: offer.offer.collateral_contract,
        collateral_token_id: loan.collateral_token_id,
        fees: new_loan_fees,
        pro_rata: offer.offer.pro_rata
    })
    new_loan.id = self._compute_loan_id(new_loan)

    assert self.loans[new_loan.id] == empty(bytes32), "loan already exists"
    self.loans[new_loan.id] = self._loan_state_hash(new_loan)

    log LoanReplacedByLender(
        new_loan.id,
        new_loan.amount,
        new_loan.interest,
        new_loan.payment_token,
        new_loan.maturity,
        new_loan.start_time,
        new_loan.collateral_contract,
        new_loan.collateral_token_id,
        new_loan.borrower,
        new_loan.lender,
        new_loan.fees,
        new_loan.pro_rata,
        loan.id,
        loan.amount,
        interest,
        settlement_fees,
        borrower_compensation,
        self._compute_signed_offer_id(offer)
    )

    return new_loan.id


@external
def revoke_offer(offer: SignedOffer):

    """
    @notice Revoke an offer.
    @param offer The signed offer to be revoked.
    """

    assert self._check_user(offer.offer.lender), "not lender"
    assert offer.offer.expiration > block.timestamp, "offer expired"
    assert self._is_offer_signed_by_lender(offer, offer.offer.lender), "offer not signed by lender"

    offer_id: bytes32 = self._compute_signed_offer_id(offer)
    assert not self.revoked_offers[offer_id], "offer already revoked"

    self.revoked_offers[offer_id] = True

    log OfferRevoked(
        offer_id,
        offer.offer.lender,
        offer.offer.collateral_contract,
        offer.offer.offer_type,
        offer.offer.token_ids
    )


@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:

    """
    @notice ERC721 token receiver callback.
    @dev Returns the ERC721 receiver callback selector.
    @param _operator The address which called `safeTransferFrom` function.
    @param _from The address which previously owned the token.
    @param _tokenId The NFT identifier which is being transferred.
    @param _data Additional data with no specified format.
    @return The ERC721 receiver callback selector.
    """

    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)



# Internal functions

@pure
@internal
def _compute_loan_id(loan: Loan) -> bytes32:
    return keccak256(concat(
        convert(loan.borrower, bytes32),
        convert(loan.lender, bytes32),
        convert(loan.start_time, bytes32),
        convert(loan.collateral_contract, bytes32),
        convert(loan.collateral_token_id, bytes32),
    ))

@pure
@internal
def _compute_signed_offer_id(offer: SignedOffer) -> bytes32:
    return keccak256(concat(
        convert(offer.signature.v, bytes32),
        convert(offer.signature.r, bytes32),
        convert(offer.signature.s, bytes32),
    ))

@internal
def _check_and_update_offer_state(offer: SignedOffer):
    offer_id: bytes32 = self._compute_signed_offer_id(offer)
    assert not self.revoked_offers[offer_id], "offer revoked"

    single_token_offer: bool = offer.offer.offer_type == OfferType.TOKEN and len(offer.offer.token_ids) == 1
    max_count: uint256 = 1 if single_token_offer else offer.offer.size

    count: uint256 = self.offer_count[offer_id]
    assert count < max_count, "offer fully utilized"
    self.offer_count[offer_id] = count + 1

@view
@internal
def _is_loan_valid(loan: Loan) -> bool:
    return self.loans[loan.id] == self._loan_state_hash(loan)

@pure
@internal
def _loan_state_hash(loan: Loan) -> bytes32:
    return keccak256(_abi_encode(loan))


@internal
def _is_offer_signed_by_lender(signed_offer: SignedOffer, lender: address) -> bool:
    return ecrecover(
        keccak256(
            concat(
                convert("\x19\x01", Bytes[2]),
                _abi_encode(
                    offer_sig_domain_separator,
                    keccak256(_abi_encode(
                        OFFER_TYPE_HASH,
                        signed_offer.offer.principal,
                        signed_offer.offer.interest,
                        signed_offer.offer.payment_token,
                        signed_offer.offer.duration,
                        signed_offer.offer.origination_fee_amount,
                        signed_offer.offer.broker_upfront_fee_amount,
                        signed_offer.offer.broker_settlement_fee_bps,
                        signed_offer.offer.broker_address,
                        signed_offer.offer.collateral_contract,
                        signed_offer.offer.offer_type,
                        keccak256(slice(
                            _abi_encode(signed_offer.offer.token_ids),
                            32*2,
                            32*len(signed_offer.offer.token_ids)
                        )),
                        signed_offer.offer.expiration,
                        signed_offer.offer.lender,
                        signed_offer.offer.pro_rata,
                        signed_offer.offer.size
                    ))
                )
            )
        ),
        signed_offer.signature.v,
        signed_offer.signature.r,
        signed_offer.signature.s
    ) == lender


@internal
def _get_loan_fees(offer: Offer, borrower_broker_upfront_fee_amount: uint256, borrower_broker_settlement_fee_bps: uint256, borrower_broker: address) -> DynArray[Fee, MAX_FEES]:
    fees: DynArray[Fee, MAX_FEES] = []
    if offer.origination_fee_amount > 0:
        assert offer.origination_fee_amount <= offer.principal, "origination fee gt principal"
    if offer.broker_settlement_fee_bps > 0 or offer.broker_upfront_fee_amount > 0:
        assert offer.broker_address != empty(address), "broker fee without address"
    if borrower_broker_upfront_fee_amount > 0 or borrower_broker_settlement_fee_bps > 0:
        assert borrower_broker != empty(address), "broker fee without address"
    assert offer.broker_settlement_fee_bps <= max_lender_broker_settlement_fee, "lender broker fee exceeds max"
    assert borrower_broker_settlement_fee_bps <= max_borrower_broker_settlement_fee, "borrower broker fee exceeds max"
    assert self.protocol_settlement_fee + offer.broker_settlement_fee_bps <= BPS, "settlement fees gt principal"

    fees.append(Fee({
        type: FeeType.PROTOCOL_FEE,
        upfront_amount: self.protocol_upfront_fee * offer.principal / BPS,
        interest_bps: self.protocol_settlement_fee,
        wallet: self.protocol_wallet
    }))
    fees.append(Fee({
        type: FeeType.ORIGINATION_FEE,
        upfront_amount: offer.origination_fee_amount,
        interest_bps: 0,
        wallet: offer.lender
    }))
    fees.append(Fee({
        type: FeeType.LENDER_BROKER_FEE,
        upfront_amount: offer.broker_upfront_fee_amount,
        interest_bps: offer.broker_settlement_fee_bps,
        wallet: offer.broker_address
    }))
    fees.append(Fee({
        type: FeeType.BORROWER_BROKER_FEE,
        upfront_amount: borrower_broker_upfront_fee_amount,
        interest_bps: borrower_broker_settlement_fee_bps,
        wallet: borrower_broker
    }))
    return fees

@internal
def _get_settlement_fees(loan: Loan, settlement_interest: uint256) -> (DynArray[FeeAmount, MAX_FEES], uint256):
    total: uint256 = 0
    settlement_fees: DynArray[FeeAmount, MAX_FEES] = []
    for fee in loan.fees:
        if fee.interest_bps > 0:
            fee_amount: uint256 = settlement_interest * fee.interest_bps / BPS
            settlement_fees.append(FeeAmount({type: fee.type, amount: fee_amount, wallet: fee.wallet}))
            total += fee_amount

    return (settlement_fees, total)


@internal
def _compute_settlement_interest(loan: Loan) -> uint256:
    if loan.pro_rata:
        return loan.interest * (block.timestamp - loan.start_time) / (loan.maturity - loan.start_time)
    else:
        return loan.interest


@internal
def _compute_max_interest_delta(loan: Loan, offer: Offer, interest: uint256) -> uint256:
    """
    Computes the maximum interest difference between the new offer and the current loan.
    That max difference can be reached either at the refinance timestamp or at the original loan maturity.
    The difference can never be negative because at the refinance timestamp the delta is just the offer interest.
    """
    delta_at_refinance: uint256 = 0 if offer.pro_rata else offer.interest
    loan_interest_delta_at_maturity: uint256 = loan.interest - interest
    offer_interest_at_loan_maturity: uint256 = offer.interest * (loan.maturity - block.timestamp) / offer.duration if offer.pro_rata else offer.interest

    return convert(max(
        convert(delta_at_refinance, int256),
        convert(offer_interest_at_loan_maturity, int256) - convert(loan_interest_delta_at_maturity, int256)
    ), uint256)


@internal
def _set_delegation(_wallet: address, _collateral_address: address, _token_id: uint256, _value: bool):
    delegation_registry.delegateERC721(_wallet, _collateral_address, _token_id, empty(bytes32), _value)


@internal
def _store_punk(_wallet: address, _collateralAddress: address, _tokenId: uint256):
    offer: PunkOffer = CryptoPunksMarket(_collateralAddress).punksOfferedForSale(_tokenId)

    assert offer.isForSale, "collateral not for sale"
    assert offer.punkIndex == _tokenId, "collateral with wrong punkIndex"
    assert offer.seller == _wallet, "collateral now owned by wallet"
    assert offer.minValue == 0, "collateral offer is not zero"
    assert offer.onlySellTo == empty(address) or offer.onlySellTo == self, "collateral buying not authorized"

    CryptoPunksMarket(_collateralAddress).buyPunk(_tokenId)


@internal
def _store_erc721(_wallet: address, _collateralAddress: address, _tokenId: uint256):
    IERC721(_collateralAddress).safeTransferFrom(_wallet, self, _tokenId, b"")


@internal
def _transfer_punk(_wallet: address, _collateralAddress: address, _tokenId: uint256):
    assert self._punk_owner(_collateralAddress, _tokenId) == self, "collateral not owned by vault"
    CryptoPunksMarket(_collateralAddress).transferPunk(_wallet, _tokenId)


@internal
def _transfer_erc721(_wallet: address, _collateralAddress: address, _tokenId: uint256):
    assert self._erc721_owner(_collateralAddress, _tokenId) == self, "collateral not owned by vault"
    IERC721(_collateralAddress).safeTransferFrom(self, _wallet, _tokenId, b"")


@internal
def _transfer_collateral(wallet: address, collateral_contract: address, token_id: uint256):
    if self._is_punk(collateral_contract):
        self._transfer_punk(wallet, collateral_contract, token_id)
    else:
        self._transfer_erc721(wallet, collateral_contract, token_id)


@internal
def _send_funds(_to: address, _amount: uint256):
    assert IERC20(payment_token).transfer(_to, _amount), "error sending funds"


@internal
def _receive_funds(_from: address, _amount: uint256):
    assert IERC20(payment_token).transferFrom(_from, self, _amount), "transferFrom failed"


@internal
def _transfer_funds(_from: address, _to: address, _amount: uint256):
    assert IERC20(payment_token).transferFrom(_from, _to, _amount), "transferFrom failed"

@pure
@internal
def _is_punk(_collateralAddress: address) -> bool:
    return _collateralAddress == cryptopunks.address


@view
@internal
def _punk_owner(_collateralAddress: address, _tokenId: uint256) -> address:
    return CryptoPunksMarket(_collateralAddress).punkIndexToAddress(_tokenId)


@view
@internal
def _erc721_owner(_collateralAddress: address, _tokenId: uint256) -> address:
    return IERC721(_collateralAddress).ownerOf(_tokenId)


@view
@internal
def _is_punk_approved_for_vault(_borrower: address, _collateralAddress: address, _tokenId: uint256) -> bool:
    offer: PunkOffer = cryptopunks.punksOfferedForSale(_tokenId)
    return (
        offer.isForSale and
        offer.punkIndex == _tokenId and
        offer.minValue == 0 and
        (offer.onlySellTo == empty(address) or offer.onlySellTo == self)
    )


@view
@internal
def _is_erc721_approved_for_vault(_borrower: address, _collateralAddress: address, _tokenId: uint256) -> bool:
    return IERC721(_collateralAddress).isApprovedForAll(_borrower, self) or IERC721(_collateralAddress).getApproved(_tokenId) == self


@internal
def _store_collateral(wallet: address, collateral_contract: address, token_id: uint256):

    assert wallet != empty(address), "addr is the zero addr"
    assert collateral_contract != empty(address), "collat addr is the zero addr"

    if self._is_punk(collateral_contract):
        assert self._punk_owner(collateral_contract, token_id) == wallet, "collateral not owned by wallet"
        assert self._is_punk_approved_for_vault(wallet, collateral_contract, token_id), "transfer is not approved"
        self._store_punk(wallet, collateral_contract, token_id)

    else:
        assert self._erc721_owner(collateral_contract, token_id) == wallet, "collateral not owned by wallet"
        assert self._is_erc721_approved_for_vault(wallet, collateral_contract, token_id), "transfer is not approved"
        self._store_erc721(wallet, collateral_contract, token_id)


@internal
def _check_user(user: address) -> bool:
    return msg.sender == user or (self.authorized_proxies[msg.sender] and user == tx.origin)

@internal
def _validate_token_ids(offer: Offer, collateral_token_id: uint256):
    if offer.offer_type == OfferType.TOKEN:
        for token_id in offer.token_ids:
            if token_id == collateral_token_id:
                return
        raise "token id not in offer"
    else:
        assert len(offer.token_ids) == 2, "invalid collection range"
        assert collateral_token_id >= offer.token_ids[0], "tokenid below offer range"
        assert collateral_token_id <= offer.token_ids[1], "tokenid above offer range"

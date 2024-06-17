# @version 0.3.10

"""
@title P2PLendingNfts
@author [Zharta](https://zharta.io/)
@notice TODO
"""

# Interfaces

from vyper.interfaces import ERC165 as IERC165
from vyper.interfaces import ERC721 as IERC721
from vyper.interfaces import ERC20 as IERC20


interface WETH:
    def deposit(): payable
    def withdraw(_amount: uint256): nonpayable

# Structs

struct Offer:
    # principal: uint256
    interest: uint256
    # ltv: uint256
    payment_token: address
    duration: uint256
    origination_fee_amount: uint256
    referral_fee_bps: uint256
    referral_address: address
    collaterals: DynArray[OfferCollateral, MAX_COLLATERALS]
    expiration: uint256
    lender: address
    pro_rata: bool

struct Signature:
    v: uint8
    r: bytes32
    s: bytes32

struct SignedOffer:
    offer: Offer
    signature: Signature

struct OfferCollateral:
    contract: address
    amount: uint256
    ltv: uint256

struct Collateral:
    contract: address
    amount: uint256

struct Loan:
    id: bytes32
    amount: uint256
    interest: uint256
    payment_token: address
    maturity: uint256
    start_time: uint256
    borrower: address
    lender: address
    origination_fee_amount: uint256
    referral_fee_bps: uint256
    referral_address: address
    protocol_fee_bps: uint256
    collaterals: DynArray[Collateral, MAX_COLLATERALS]
    pro_rata: bool


struct WhitelistLog:
    collection: address
    whitelisted: bool


# Events

event LoanCreated:
    id: bytes32
    amount: uint256
    interest: uint256
    payment_token: address
    maturity: uint256
    start_time: uint256
    borrower: address
    lender: address
    origination_fee_amount: uint256
    referral_fee_bps: uint256
    referral_address: address
    protocol_fee_bps: uint256
    collaterals: DynArray[OfferCollateral, MAX_COLLATERALS]
    pro_rata: bool

event LoanReplaced:
    id: bytes32
    amount: uint256
    interest: uint256
    payment_token: address
    maturity: uint256
    start_time: uint256
    borrower: address
    lender: address
    origination_fee_amount: uint256
    referral_fee_bps: uint256
    referral_address: address
    protocol_fee_bps: uint256
    collaterals: DynArray[OfferCollateral, MAX_COLLATERALS]
    pro_rata: bool
    original_loan_id: bytes32
    paid_principal: uint256
    paid_interest: uint256
    paid_protocol_fees: uint256
    paid_referral_fees: uint256

event LoanPaid:
    id: bytes32
    borrower: address
    lender: address
    payment_token: address
    paid_principal: uint256
    paid_interest: uint256
    paid_protocol_fees: uint256
    paid_referral_fees: uint256

event LoanCollateralClaimed:
    id: bytes32
    borrower: address
    lender: address
    collaterals: DynArray[Collateral, MAX_COLLATERALS]

event WhitelistChanged:
    changed: DynArray[WhitelistLog, WHITELIST_BATCH]


event OwnerProposed:
    owner: address
    proposed_owner: address

event OwnershipTransferred:
    old_owner: address
    new_owner: address

event ProtocolFeeSet:
    old_fee: uint256
    new_fee: uint256

event ProtocolWalletChanged:
    old_wallet: address
    new_wallet: address

# Variables

MAX_COLLATERALS: constant(uint256) = 100
WHITELIST_BATCH: constant(uint256) = 100

owner: public(address)
proposed_owner: public(address)

payment_token: public(immutable(address))
loans: public(HashMap[bytes32, bytes32])
max_protocol_fee: public(immutable(uint256))
weth9: public(immutable(WETH))

whitelisted_collections: public(HashMap[address, bool])
protocol_wallet: public(address)
protocol_fee: public(uint256)
revoked_offers: public(HashMap[bytes32, bool])

ZHARTA_DOMAIN_NAME: constant(String[6]) = "Zharta"
ZHARTA_DOMAIN_VERSION: constant(String[1]) = "1"

DOMAIN_TYPE_HASH: constant(bytes32) = keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
OFFER_TYPE_HASH: constant(bytes32) = keccak256("Offer(uint256 principal,uint256 interest,uint256 ltv,address payment_token,uint256 duration,uint256 origination_fee_amount,uint256 referral_fee_bps,address referral_address,DynArray[Collateral,100] collaterals,uint256 expiration,address lender,bool pro_rata)")

offer_sig_domain_separator: immutable(bytes32)

@external
def __init__(_payment_token: address, _max_protocol_fee: uint256, _weth9: address):
    self.owner = msg.sender
    payment_token = _payment_token
    max_protocol_fee = _max_protocol_fee
    weth9 = WETH(_weth9)

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
def change_whitelisted_collections(collections: DynArray[WhitelistLog, WHITELIST_BATCH]):
    """
    @notice Set whitelisted collections
    @param collections: array of WhitelistLog
    """
    assert msg.sender == self.owner, "sender not owner"
    for c in collections:
        self.whitelisted_collections[c.collection] = c.whitelisted

    log WhitelistChanged(collections)


@external
def set_protocol_fee(protocol_fee: uint256):

    """
    @notice Set the protocol fee
    @dev Sets the protocol fee to the given value and logs the event. Admin function.
    @param protocol_fee The new protocol fee.
    """

    assert msg.sender == self.owner, "not owner"
    assert protocol_fee <= max_protocol_fee, "protocol fee > max fee"

    log ProtocolFeeSet(self.protocol_fee, protocol_fee)
    self.protocol_fee = protocol_fee


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


# Core functions

@external
def create_loan(offer: SignedOffer) -> bytes32:
    """
    @notice Create a loan
    @param offer: Offer
    @return bytes32: loan id
    """
    assert self._is_offer_signed_by_lender(offer, offer.offer.lender), "offer not signed by lender"
    assert offer.offer.expiration > block.timestamp, "offer expired"
    assert offer.offer.payment_token == payment_token, "invalid payment token"

    self._check_and_update_offer_state(offer)

    principal: uint256 = 0
    for c in offer.offer.collaterals:
        assert self.whitelisted_collections[c.contract], "collection not whitelisted"
        principal += c.amount * c.ltv / 10000

    collaterals: DynArray[Collateral, MAX_COLLATERALS] = []
    for c in offer.offer.collaterals:
        collaterals.append(Collateral({
            contract: c.contract,
            amount: c.amount
        }))

    loan: Loan = Loan({
        id: empty(bytes32),
        amount: principal,
        interest: offer.offer.interest,
        payment_token: offer.offer.payment_token,
        maturity: block.timestamp + offer.offer.duration,
        start_time: block.timestamp,
        borrower: msg.sender,
        lender: offer.offer.lender,
        origination_fee_amount: offer.offer.origination_fee_amount,
        referral_fee_bps: offer.offer.referral_fee_bps,
        referral_address: offer.offer.referral_address,
        protocol_fee_bps: self.protocol_fee,
        collaterals: collaterals,
        pro_rata: offer.offer.pro_rata
    })
    loan.id = self._compute_loan_id(loan)

    assert self.loans[loan.id] == empty(bytes32), "loan already exists"
    self.loans[loan.id] = self._loan_state_hash(loan)

    for c in offer.offer.collaterals:
        self._store_collateral(msg.sender, c.contract, c.amount)
    self._receive_funds(loan.lender, loan.amount - loan.origination_fee_amount)
    self._send_funds(loan.borrower, loan.amount - loan.origination_fee_amount)

    log LoanCreated(
        loan.id,
        loan.amount,
        loan.interest,
        loan.payment_token,
        loan.maturity,
        loan.start_time,
        loan.borrower,
        loan.lender,
        loan.origination_fee_amount,
        loan.referral_fee_bps,
        loan.referral_address,
        loan.protocol_fee_bps,
        offer.offer.collaterals,
        loan.pro_rata
    )
    return loan.id


@external
@payable
def settle_loan(loan: Loan):
    """
    @notice Settle a loan
    @param loan: Loan
    """
    assert payment_token == empty(address) or msg.value == 0, "native payment not allowed"
    assert self._is_loan_valid(loan), "invalid loan"
    assert block.timestamp <= loan.maturity, "loan defaulted" # should this be allowed?

    interest: uint256 = self._compute_interest(loan)

    self.loans[loan.id] = empty(bytes32)

    protocol_fee_amount: uint256 = interest * loan.protocol_fee_bps / 10000
    referral_fee_amount: uint256 = interest * loan.referral_fee_bps / 10000

    self._receive_funds(loan.borrower, loan.amount + interest + protocol_fee_amount + referral_fee_amount)

    self._send_funds(loan.lender, loan.amount - protocol_fee_amount - referral_fee_amount)
    if protocol_fee_amount > 0:
        self._send_funds(self.protocol_wallet, protocol_fee_amount)
    if referral_fee_amount > 0:
        self._send_funds(loan.referral_address, referral_fee_amount)

    for c in loan.collaterals:
        self._transfer_collateral(loan.borrower, c.contract, c.amount)

    log LoanPaid(
        loan.id,
        loan.borrower,
        loan.lender,
        loan.payment_token,
        loan.amount,
        interest,
        protocol_fee_amount,
        referral_fee_amount
    )


@external
def claim_defaulted_loan_collateral(loan: Loan):
    """
    @notice Claim defaulted loan collateral
    @param loan: Loan
    """
    assert self._is_loan_valid(loan), "invalid loan"
    assert block.timestamp > loan.maturity, "loan not defaulted"
    assert loan.lender == msg.sender, "not lender"

    self.loans[loan.id] = empty(bytes32)

    for c in loan.collaterals:
        self._transfer_collateral(loan.borrower, c.contract, c.amount)

    log LoanCollateralClaimed(
        loan.id,
        loan.borrower,
        loan.lender,
        loan.collaterals,
    )


@external
@payable
def replace_loan(loan: Loan, offer: SignedOffer) -> bytes32:
    """
    @notice Replace a loan
    @param loan: Loan
    @param offer: Offer
    @return bytes32: loan id
    """

    assert payment_token == empty(address) or msg.value == 0, "native payment not allowed"
    assert self._is_loan_valid(loan), "invalid loan"
    assert block.timestamp <= loan.maturity, "loan defaulted"

    assert self._is_offer_signed_by_lender(offer, offer.offer.lender), "offer not signed by lender"
    assert offer.offer.expiration > block.timestamp, "offer expired"
    assert offer.offer.payment_token == payment_token, "invalid payment token"

    self._check_and_update_offer_state(offer)

    principal: uint256 = 0
    for c in offer.offer.collaterals:
        assert self.whitelisted_collections[c.contract], "collection not whitelisted"
        principal += c.amount * c.ltv / 10000

    interest: uint256 = self._compute_interest(loan)
    protocol_fee_amount: uint256 = interest * loan.protocol_fee_bps / 10000
    referral_fee_amount: uint256 = interest * loan.referral_fee_bps / 10000

    self.loans[loan.id] = empty(bytes32)

    self._receive_funds(loan.borrower, loan.amount + interest + protocol_fee_amount + referral_fee_amount)

    self._send_funds(loan.lender, loan.amount - protocol_fee_amount - referral_fee_amount)
    if protocol_fee_amount > 0:
        self._send_funds(self.protocol_wallet, protocol_fee_amount)
    if referral_fee_amount > 0:
        self._send_funds(loan.referral_address, referral_fee_amount)


    collaterals: DynArray[Collateral, MAX_COLLATERALS] = []
    for c in offer.offer.collaterals:
        collaterals.append(Collateral({
            contract: c.contract,
            amount: c.amount
        }))

    new_loan: Loan = Loan({
        id: empty(bytes32),
        amount: principal,
        interest: offer.offer.interest,
        payment_token: offer.offer.payment_token,
        maturity: block.timestamp + offer.offer.duration,
        start_time: block.timestamp,
        borrower: msg.sender,
        lender: offer.offer.lender,
        origination_fee_amount: offer.offer.origination_fee_amount,
        referral_fee_bps: offer.offer.referral_fee_bps,
        referral_address: offer.offer.referral_address,
        protocol_fee_bps: self.protocol_fee,
        collaterals: collaterals,
        pro_rata: offer.offer.pro_rata
    })
    new_loan.id = self._compute_loan_id(new_loan)

    assert self.loans[new_loan.id] == empty(bytes32), "loan already exists"
    self.loans[new_loan.id] = self._loan_state_hash(new_loan)

    self._receive_funds(loan.lender, loan.amount - loan.origination_fee_amount)
    self._send_funds(loan.borrower, loan.amount - loan.origination_fee_amount)

    log LoanReplaced(
        new_loan.id,
        new_loan.amount,
        new_loan.interest,
        new_loan.payment_token,
        new_loan.maturity,
        new_loan.start_time,
        new_loan.borrower,
        new_loan.lender,
        new_loan.origination_fee_amount,
        new_loan.referral_fee_bps,
        new_loan.referral_address,
        new_loan.protocol_fee_bps,
        offer.offer.collaterals,
        new_loan.pro_rata,
        loan.id,
        loan.amount,
        interest,
        protocol_fee_amount,
        referral_fee_amount
    )

    return new_loan.id


@external
def revoke_offer(offer: SignedOffer):
    """
    @notice Revoke an offer
    @param offer: SignedOffer
    """
    assert msg.sender == offer.offer.lender, "not lender"
    assert self._is_offer_signed_by_lender(offer, offer.offer.lender), "offer not signed by lender"

    offer_id: bytes32 = self._compute_signed_offer_id(offer)
    assert not self.revoked_offers[offer_id], "offer already revoked"

    self.revoked_offers[offer_id] = True


# Internal functions

@pure
@internal
def _compute_loan_id(loan: Loan) -> bytes32:
    return keccak256(concat(
        convert(loan.borrower, bytes32),
        convert(loan.lender, bytes32),
        convert(loan.start_time, bytes32),
        _abi_encode(loan.collaterals)
    ))

@pure
@internal
def _compute_signed_offer_id(offer: SignedOffer) -> bytes32:
    return keccak256(concat(
        convert(offer.signature.v, bytes32),
        offer.signature.r,
        offer.signature.s,
    ))

@internal
def _check_and_update_offer_state(offer: SignedOffer):
    offer_id: bytes32 = self._compute_signed_offer_id(offer)
    assert not self.revoked_offers[offer_id], "offer revoked"

    # max_count: uint256 = offer.offer.size if offer.offer.collateral_min_token_id != offer.offer.collateral_max_token_id else 1
    # count: uint256 = self.offer_count[offer_id]
    # assert count < max_count, "offer fully utilized"
    # self.offer_count[offer_id] = count + 1

@view
@internal
def _is_loan_valid(loan: Loan) -> bool:
    return self.loans[loan.id] == self._loan_state_hash(loan)

@pure
@internal
def _loan_state_hash(loan: Loan) -> bytes32:

    return keccak256(
        concat(
            loan.id,
            convert(loan.amount, bytes32),
            convert(loan.interest, bytes32),
            convert(loan.payment_token, bytes32),
            convert(loan.maturity, bytes32),
            convert(loan.start_time, bytes32),
            convert(loan.borrower, bytes32),
            convert(loan.lender, bytes32),
            convert(loan.origination_fee_amount, bytes32),
            convert(loan.referral_fee_bps, bytes32),
            convert(loan.referral_address, bytes32),
            convert(loan.protocol_fee_bps, bytes32),
            _abi_encode(loan.collaterals),
            convert(loan.pro_rata, bytes32),
        )
    )


@internal
def _is_offer_signed_by_lender(signed_offer: SignedOffer, lender: address) -> bool:
    return ecrecover(
        keccak256(
            concat(
                convert("\x19\x01", Bytes[2]),
                _abi_encode(
                    offer_sig_domain_separator,
                    keccak256(_abi_encode(OFFER_TYPE_HASH, signed_offer.offer))
                )
            )
        ),
        signed_offer.signature.v,
        signed_offer.signature.r,
        signed_offer.signature.s
    ) == lender


@internal
def _compute_interest(loan: Loan) -> uint256:
    if loan.pro_rata:
        return loan.interest * (block.timestamp - loan.start_time) / loan.maturity - loan.start_time
    else:
        return loan.interest


@internal
def _send_funds(_to: address, _amount: uint256):

    if payment_token == empty(address):
        weth9.withdraw(_amount)
        send(_to, _amount)

    else:
        if not IERC20(payment_token).transfer(_to, _amount):
            raise "error sending funds"


@internal
@payable
def _receive_funds(_from: address, _amount: uint256):

    if payment_token == empty(address):
        assert msg.value == _amount, "msg.value != _amount"
        weth9.deposit(value=_amount)

    else:
        assert IERC20(payment_token).transferFrom(_from, self, _amount), "transferFrom failed"


@internal
def _transfer_collateral(wallet: address, collateral_contract: address, amount: uint256):
    assert IERC20(collateral_contract).transferFrom(self, wallet, amount), "transferFrom failed"

@internal
def _store_collateral(wallet: address, collateral_contract: address, amount: uint256):
    assert IERC20(collateral_contract).transferFrom(wallet, self, amount), "transferFrom failed"


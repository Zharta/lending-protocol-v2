# @version 0.3.10

"""
@title P2PLendingControl
@author [Zharta](https://zharta.io/)
@notice This contract keeps some lending parameters for P2P lending contracts, namely the whitelisted collections and the broker pre-agreements.
"""

# Interfaces

from vyper.interfaces import ERC165 as IERC165
from vyper.interfaces import ERC721 as IERC721
from vyper.interfaces import ERC20 as IERC20

interface CryptoPunksMarket:
    def punkIndexToAddress(punkIndex: uint256) -> address: view

# Structs

struct BrokerLock:
    broker: address
    expiration: uint256

struct WhitelistRecord:
    collection: address
    whitelisted: bool

struct CollateralStatus:
    broker_lock: BrokerLock
    whitelisted: bool


# Events

event WhitelistChanged:
    changed: DynArray[WhitelistRecord, WHITELIST_BATCH]

event MaxBrokerLockDurationChanged:
    old_duration: uint256
    new_duration: uint256

event OwnerProposed:
    owner: address
    proposed_owner: address

event OwnershipTransferred:
    old_owner: address
    new_owner: address

event BrokerLockAdded:
    collateral_address: address
    collateral_token_id: uint256
    broker: address
    expiration: uint256

event BrokerLockRemoved:
    collateral_address: address
    collateral_token_id: uint256


# Global variables

WHITELIST_BATCH: constant(uint256) = 100

cryptopunks: public(immutable(CryptoPunksMarket))

owner: public(address)
proposed_owner: public(address)
max_broker_lock_duration: public(uint256)

whitelisted: public(HashMap[address, bool])
broker_locks: HashMap[bytes32, BrokerLock]



@external
def __init__(_cryptopunks: address, _max_broker_lock_duration: uint256):
    self.owner = msg.sender
    self.max_broker_lock_duration = _max_broker_lock_duration

    cryptopunks = CryptoPunksMarket(_cryptopunks)


@external
def propose_owner(_address: address):

    """
    @notice Propose a new owner
    @dev Proposes a new owner and logs the event. Admin function.
    @param _address The address of the proposed owner.
    """

    assert msg.sender == self.owner, "not owner"
    assert _address != empty(address), "address is zero"

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


@external
def set_max_broker_lock_duration(duration: uint256):
    """
    @notice Set the maximum broker lock duration
    @param duration duration in seconds
    """
    assert msg.sender == self.owner, "not owner"

    log MaxBrokerLockDurationChanged(self.max_broker_lock_duration, duration)

    self.max_broker_lock_duration = duration


@external
def add_broker_lock(collateral_address: address, collateral_token_id: uint256, broker: address, expiration: uint256):
    """
    @notice Add a broker lock
    @param collateral_address address of the collateral contract
    @param collateral_token_id token id of the collateral
    @param broker address of the broker
    @param expiration expiration time for the lock
    """
    assert msg.sender == self._get_collateral_owner(collateral_address, collateral_token_id), "not owner"
    lock_id: bytes32 = self._compute_lock_id(collateral_address, collateral_token_id)

    assert broker != empty(address), "broker is zero"
    assert self.broker_locks[lock_id].expiration < block.timestamp, "lock exists"
    assert expiration <= block.timestamp + self.max_broker_lock_duration, "expiration too far"
    assert expiration > block.timestamp, "expiration in the past"

    self.broker_locks[lock_id] = BrokerLock({
        broker: broker,
        expiration: expiration
    })

    log BrokerLockAdded(collateral_address, collateral_token_id, broker, expiration)


@external
def remove_broker_lock(collateral_address: address, collateral_token_id: uint256):
    """
    @notice Remove a broker lock
    @param collateral_address address of the collateral contract
    @param collateral_token_id token id of the collateral
    """
    lock_id: bytes32 = self._compute_lock_id(collateral_address, collateral_token_id)
    lock: BrokerLock = self.broker_locks[lock_id]

    assert msg.sender == lock.broker, "not broker"
    self.broker_locks[lock_id] = empty(BrokerLock)

    log BrokerLockRemoved(collateral_address, collateral_token_id)


@external
@view
def get_broker_lock(collateral_address: address, collateral_token_id: uint256) -> BrokerLock:
    """
    @notice Get the broker lock
    @param collateral_address address of the collateral contract
    @param collateral_token_id token id of the collateral
    @return lock expiration time and address of the broker
    """
    return self.broker_locks[self._compute_lock_id(collateral_address, collateral_token_id)]


@external
@view
def get_collateral_status(collateral_address: address, collateral_token_id: uint256) -> CollateralStatus:
    """
    @notice Get the collateral status
    @param collateral_address address of the collateral contract
    @param collateral_token_id token id of the collateral
    @return broker lock and whitelisted status
    """
    return CollateralStatus({
        broker_lock: self.broker_locks[self._compute_lock_id(collateral_address, collateral_token_id)],
        whitelisted: self.whitelisted[collateral_address]
    })

@pure
@internal
def _compute_lock_id(collateral_address: address, collateral_token_id: uint256) -> bytes32:
    """
    @notice Compute the lock id
    @param collateral_address address of the collateral contract
    @param collateral_token_id token id of the collateral
    @return lock_id
    """
    return keccak256(concat(
        convert(collateral_address, bytes32),
        convert(collateral_token_id, bytes32)
    ))


@internal
def _get_collateral_owner(contract: address, token_id: uint256) -> address:
    """
    @notice Get the owner of the collateral
    @param contract address of the collateral contract
    @param token_id token id of the collateral
    @return owner address of the owner
    """
    if self._is_punk(contract):
        return self._punk_owner(contract, token_id)
    else:
        return self._erc721_owner(contract, token_id)


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

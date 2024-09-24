# @version 0.3.10

"""
@title P2PLendingControl
@author [Zharta](https://zharta.io/)
@notice This contract keeps some lending parameters for P2P lending contracts, namely the contracts for the collections and the trait roots.
"""

# Interfaces

from vyper.interfaces import ERC165 as IERC165
from vyper.interfaces import ERC721 as IERC721
from vyper.interfaces import ERC20 as IERC20

# Structs

struct CollectionStatus:
    contract: address
    trait_root: bytes32

struct CollectionContract:
    collection_key_hash: bytes32
    contract: address

struct TraitRoot:
    collection_key_hash: bytes32
    root_hash: bytes32

# Events

event ContractsChanged:
    changed: DynArray[CollectionContract, CHANGE_BATCH]

event TraitRootChanged:
    changed: DynArray[TraitRoot, CHANGE_BATCH]

event OwnerProposed:
    owner: address
    proposed_owner: address

event OwnershipTransferred:
    old_owner: address
    new_owner: address

# Global variables

CHANGE_BATCH: constant(uint256) = 128

VERSION: constant(String[30]) = "P2PLendingControl.20240920"

owner: public(address)
proposed_owner: public(address)

contracts: public(HashMap[bytes32, address])

# leafs are calculated as keccak256(_abi_encode(collection_address, trait_hash, token_id))
# all valid (contract, trait, token_id) tuples are stored in the tree and the root 
# is stored in the contract for each collection.
# The collection key is hashed and must match the collection key hash in the offer.
trait_roots: public(HashMap[bytes32, bytes32])


@external
def __init__():
    self.owner = msg.sender


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
def change_collections_contracts(collections: DynArray[CollectionContract, CHANGE_BATCH]):
    """
    @notice Set the contracts for the collections
    @param collections array of CollectionContract
    """
    assert msg.sender == self.owner, "sender not owner"
    for c in collections:
        self.contracts[c.collection_key_hash] = c.contract

    log ContractsChanged(collections)


@external
def change_collections_trait_roots(roots: DynArray[TraitRoot, CHANGE_BATCH]):
    """
    @notice Set trait roots
    @param roots array of bytes32
    """
    assert msg.sender == self.owner, "sender not owner"
    for r in roots:
        self.trait_roots[r.collection_key_hash] = r.root_hash

    log TraitRootChanged(roots)


@external
@view
def get_collection_status(collection_key_hash: bytes32) -> CollectionStatus:
    """
    @notice Get the collection status
    @param collection_key_hash hash of the collection key
    @return the contract address and traits root
    """
    return CollectionStatus({
        contract: self.contracts[collection_key_hash],
        trait_root: self.trait_roots[collection_key_hash]
    })


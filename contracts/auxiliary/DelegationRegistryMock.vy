# @version 0.3.10


enum DelegationType:
    NONE_
    ALL
    CONTRACT
    ERC721
    ERC20
    ERC1155


struct Delegation:
    type: DelegationType
    to: address
    from_: address
    rights: bytes32
    contract: address
    tokenId: uint256
    amount: uint256


event DelegateAll:
    from_: address
    to_: address
    rights: bytes32
    enable: bool

event DelegateContract:
    from_: address
    to_: address
    contract: address
    rights: bytes32
    enable: bool

event DelegateERC20:
    from_: address
    to_: address
    contract: address
    rights: bytes32
    amount: uint256

event DelegateERC721:
    from_: address
    to_: address
    contract: address
    tokenId: uint256
    rights: bytes32
    enable: bool

event DelegateERC1155:
    from_: address
    to_: address
    contract: address
    tokenId: uint256
    rights: bytes32
    amount: uint256


# Global variables

DELEGATION_REVOKED: constant(address) = 0x000000000000000000000000000000000000dEaD

delegations: HashMap[bytes32, Delegation]
outgoingDelegationHashes: HashMap[address, DynArray[bytes32, 2**20]]  #  from -> delegationHash
incomingDelegationHashes: HashMap[address, DynArray[bytes32, 2**20]]  #  to -> delegationHash

# External functions

@external
def delegateAll(to: address, rights: bytes32, enable: bool) -> bytes32:
    hash: bytes32 = self._all_hash(msg.sender, rights, to)
    delegation: Delegation = self.delegations[hash]

    if enable:
        if delegation.from_ == empty(address):
            self.delegations[hash].from_ = msg.sender
            self.delegations[hash].to = to
            self.delegations[hash].rights = rights
            self._pushDelegationHashes(msg.sender, to, hash)
        elif delegation.from_ == DELEGATION_REVOKED:
            self.delegations[hash].from_ = msg.sender
    elif delegation.from_ == msg.sender:
        self.delegations[hash].from_ = DELEGATION_REVOKED

    log DelegateAll(msg.sender, to, rights, enable)
    return hash

@external
def delegateContract(to: address, contract_: address, rights: bytes32, enable: bool) -> bytes32:
    hash: bytes32 = self._contract_hash(msg.sender, rights, to, contract_)
    delegation: Delegation = self.delegations[hash]

    if enable:
        if delegation.from_ == empty(address):
            self.delegations[hash].from_ = msg.sender
            self.delegations[hash].to = to
            self.delegations[hash].contract = contract_
            self.delegations[hash].rights = rights
            self._pushDelegationHashes(msg.sender, to, hash)
        elif delegation.from_ == DELEGATION_REVOKED:
            self.delegations[hash].from_ = msg.sender
    elif delegation.from_ == msg.sender:
        self.delegations[hash].from_ = DELEGATION_REVOKED

    log DelegateContract(msg.sender, to, contract_, rights, enable)
    return hash

@external
def delegateERC721(to: address, contract_: address, tokenId: uint256, rights: bytes32, enable: bool) -> bytes32:
    hash: bytes32 = self._erc721_hash(msg.sender, rights, to, tokenId, contract_)
    delegation: Delegation = self.delegations[hash]

    if enable:
        if delegation.from_ == empty(address):
            self.delegations[hash].from_ = msg.sender
            self.delegations[hash].to = to
            self.delegations[hash].contract = contract_
            self.delegations[hash].tokenId = tokenId
            self.delegations[hash].rights = rights
            self._pushDelegationHashes(msg.sender, to, hash)
        elif delegation.from_ == DELEGATION_REVOKED:
            self.delegations[hash].from_ = msg.sender
    elif delegation.from_ == msg.sender:
        self.delegations[hash].from_ = DELEGATION_REVOKED

    log DelegateERC721(msg.sender, to, contract_, tokenId, rights, enable)
    return hash

@external
def delegateERC20(to: address, contract_: address, rights: bytes32, amount: uint256) -> bytes32:
    raise "Not implemented"

@external
def delegateERC1155(to: address, contract_: address, tokenId: uint256, rights: bytes32, amount: uint256) -> bytes32:
    raise "Not implemented"

@external
def checkDelegateForAll(to: address, from_: address, rights: bytes32) -> bool:
    if self._invalidFrom(from_):
        return False
    valid: bool = self.delegations[self._all_hash(from_, empty(bytes32), to)].from_ == from_
    if not valid and rights != empty(bytes32):
        valid = self.delegations[self._all_hash(from_, rights, to)].from_ == from_
    return valid

@external
def checkDelegateForContract(to: address, from_: address, contract_: address, rights: bytes32) -> bool:
    if self._invalidFrom(from_):
        return False
    valid: bool = self.delegations[self._all_hash(from_, empty(bytes32), to)].from_ == from_ or self.delegations[self._contract_hash(from_, empty(bytes32), to, contract_)].from_ == from_
    if not valid and rights != empty(bytes32):
        valid = self.delegations[self._all_hash(from_, rights, to)].from_ == from_ or self.delegations[self._contract_hash(from_, rights, to, contract_)].from_ == from_
    return valid


@external
def checkDelegateForERC721(to: address, from_: address, contract_: address, tokenId: uint256, rights: bytes32) -> bool:
    if self._invalidFrom(from_):
        return False
    valid: bool = self.delegations[self._all_hash(from_, empty(bytes32), to)].from_ == from_ or self.delegations[self._contract_hash(from_, empty(bytes32), to, contract_)].from_ == from_ or self.delegations[self._erc721_hash(from_, empty(bytes32), to, tokenId, contract_)].from_ == from_
    if not valid and rights != empty(bytes32):
        valid = self.delegations[self._all_hash(from_, rights, to)].from_ == from_ or self.delegations[self._contract_hash(from_, rights, to, contract_)].from_ == from_ or self.delegations[self._erc721_hash(from_, rights, to, tokenId, contract_)].from_ == from_
    return valid

@external
def checkDelegateForERC20(to: address, from_: address, contract_: address, rights: bytes32) -> uint256:
    return 0

@external
def checkDelegateForERC1155(to: address, from_: address, contract_: address, tokenId: uint256, rights: bytes32) -> uint256:
    return 0

@external
def getIncomingDelegations(to: address) -> DynArray[Delegation, 2**20]:
    return self._getValidDelegationsFromHashes(self.incomingDelegationHashes[to])

@external
def getOutgoingDelegations(from_: address) -> DynArray[Delegation, 2**20]:
    return self._getValidDelegationsFromHashes(self.outgoingDelegationHashes[from_])

@external
def getIncomingDelegationHashes(to: address) -> DynArray[bytes32, 2**20]:
    return self._getValidDelegationHashesFromHashes(self.incomingDelegationHashes[to])

@external
def getOutgoingDelegationHashes(from_: address) -> DynArray[bytes32, 2**20]:
    return self._getValidDelegationHashesFromHashes(self.outgoingDelegationHashes[from_])

@external
def getDelegationsFromHashes(hashes: DynArray[bytes32, 2**20]) -> DynArray[Delegation, 2**20]:
    delegations_: DynArray[Delegation, 2**20] = []
    for hash in hashes:
        delegation: Delegation = self.delegations[hash]
        if self._invalidFrom(delegation.from_):
            continue
        delegations_.append(delegation)
    return delegations_



# Internal functions

@internal
def _pushDelegationHashes(from_: address, to: address, delegationHash: bytes32):
    self.outgoingDelegationHashes[from_].append(delegationHash)
    self.incomingDelegationHashes[to].append(delegationHash)

@internal
def _invalidFrom(from_: address) -> bool:
    return from_ == empty(address) or from_ == DELEGATION_REVOKED


@internal
def _getValidDelegationsFromHashes(hashes: DynArray[bytes32, 2**20]) -> DynArray[Delegation, 2**20]:
    delegations_: DynArray[Delegation, 2**20] = []
    for hash in hashes:
        delegation: Delegation = self.delegations[hash]
        if self._invalidFrom(delegation.from_):
            continue
        delegations_.append(delegation)
    return delegations_


@internal
def _getValidDelegationHashesFromHashes(hashes: DynArray[bytes32, 2**20]) -> DynArray[bytes32, 2**20]:
    valid_hashes: DynArray[bytes32, 2**20] = []
    for hash in hashes:
        if self._invalidFrom(self.delegations[hash].from_):
            continue
        valid_hashes.append(hash)
    return valid_hashes


@internal
def _all_hash(_from: address, _rights: bytes32, _to: address) -> bytes32:
    return keccak256(
        concat(
            convert(_from, bytes32),
            convert(_to, bytes32),
            _rights
        )
    )

@internal
def _contract_hash(_from: address, _rights: bytes32, _to: address, _contract: address) -> bytes32:
    return keccak256(
        concat(
            convert(_from, bytes32),
            convert(_to, bytes32),
            convert(_contract, bytes32),
            _rights
        )
    )

@internal
def _erc721_hash(_from: address, _rights: bytes32, _to: address, _tokenId: uint256, _contract: address) -> bytes32:
    return keccak256(
        concat(
            convert(_from, bytes32),
            convert(_to, bytes32),
            convert(_contract, bytes32),
            convert(_tokenId, bytes32),
            _rights
        )
    )

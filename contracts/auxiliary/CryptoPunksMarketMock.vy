# @version 0.3.10

# Structs

struct Offer:
    isForSale: bool
    punkIndex: uint256
    seller: address
    minValue: uint256
    onlySellTo: address

struct Bid:
    hasBid: bool
    punkIndex: uint256
    bidder: address
    value: uint256

# Events

event Assign:
    toAddress: indexed(address)
    punkIndex: uint256

event Transfer:
    fromAddress: indexed(address)
    toAddress: indexed(address)
    value: uint256

event PunkTransfer:
    fromAddress: indexed(address)
    toAddress: indexed(address)
    punkIndex: uint256

event PunkOffered:
    punkIndex: indexed(uint256)
    minValue: uint256
    toAddress: indexed(address)

event PunkBidEntered:
    punkIndex: indexed(uint256)
    value: uint256
    fromAddress: indexed(address)

event PunkBidWithdrawn:
    punkIndex: indexed(uint256)
    value: uint256
    fromAddress: indexed(address)

event PunkBought:
    punkIndex: indexed(uint256)
    value: uint256
    fromAddress: indexed(address)
    toAddress: indexed(address)

event PunkNoLongerForSale:
    punkIndex: indexed(uint256)


# Global variables

owner: public(address)

standard: public(String[11])
name: public(String[11])
symbol: public(String[10])
decimals: public(uint8)
totalSupply: public(uint256)

nextPunkIndexToAssign: public(uint256)
allPunksAssigned: public(bool)
punksRemainingToAssign: public(uint256)

collateralsInLoans: public(HashMap[bytes32, HashMap[address, uint256]]) # given a collateral and a borrower, what is the loan id

punkIndexToAddress: public(HashMap[uint256, address])
balanceOf: public(HashMap[address, uint256])
punksOfferedForSale: public(HashMap[uint256, Offer])
punkBids: public(HashMap[uint256, Bid])
pendingWithdrawals: public(HashMap[address, uint256])

# aditional variables to make this enumerable
idToPositionInWallet: HashMap[uint256, uint256]
wallet: public(HashMap[address, DynArray[uint256, 2**16]])


# Internal functions

@internal
def punkNoLongerForSale(punkIndex: uint256):
    assert self.punkIndexToAddress[punkIndex] == msg.sender
    assert punkIndex < 10000
    self.punksOfferedForSale[punkIndex] = Offer({
        isForSale: False,
        punkIndex: punkIndex,
        seller: msg.sender,
        minValue: 0,
        onlySellTo: empty(address)
    })
    log PunkNoLongerForSale(punkIndex)


@internal
def _addTokenTo(toAddress: address, punkIndex: uint256):
    assert self.punkIndexToAddress[punkIndex] == ZERO_ADDRESS
    self.punkIndexToAddress[punkIndex] = toAddress
    self.balanceOf[toAddress] += 1
    self.idToPositionInWallet[punkIndex] = len(self.wallet[toAddress])
    self.wallet[toAddress].append(punkIndex)



@internal
def _removeTokenFrom(fromAddress: address, punkIndex: uint256):
    assert self.punkIndexToAddress[punkIndex] == fromAddress
    self.punkIndexToAddress[punkIndex] = ZERO_ADDRESS
    self.balanceOf[fromAddress] -= 1

    last: uint256 = self.wallet[fromAddress].pop()
    if last != punkIndex:
        self.wallet[fromAddress][self.idToPositionInWallet[punkIndex]] = last
        self.idToPositionInWallet[last] = self.idToPositionInWallet[punkIndex]
    self.idToPositionInWallet[punkIndex] = max_value(uint256)


# External functions

@external
def __init__():
    self.standard = 'CryptoPunks'
    self.owner = msg.sender
    self.totalSupply = 0
    self.punksRemainingToAssign = 10000
    self.allPunksAssigned = False
    self.name = "CRYPTOPUNKS"
    self.symbol = "C"
    self.decimals = 0


@external
def setInitialOwner(toAddress: address, punkIndex: uint256):
    pass # not implemented

@external
def setInitialOwners(addresses: DynArray[address, 10000], indices: DynArray[uint256, 10000]):
    pass # not implemented

@external
def allInitialOwnersAssigned():
    pass # not implemented

@external
def getPunk(punkIndex: uint256):
    assert self.punksRemainingToAssign > 0
    assert self.punkIndexToAddress[punkIndex] == empty(address)
    assert punkIndex < 10000

    self._addTokenTo(msg.sender, punkIndex)
    self.totalSupply += 1
    self.punksRemainingToAssign -= 1
    log Assign(msg.sender, punkIndex)


@external
def transferPunk(toAddress: address, punkIndex: uint256):
    assert self.punkIndexToAddress[punkIndex] == msg.sender
    assert punkIndex < 10000

    if self.punksOfferedForSale[punkIndex].isForSale:
        self.punkNoLongerForSale(punkIndex)

    self._removeTokenFrom(msg.sender, punkIndex)
    self._addTokenTo(toAddress, punkIndex)
    log Transfer(msg.sender, toAddress, 1)
    log PunkTransfer(msg.sender, toAddress, punkIndex)

    if self.punkBids[punkIndex].bidder == toAddress:
        self.pendingWithdrawals[toAddress] += self.punkBids[punkIndex].value
        self.punkBids[punkIndex] = Bid({
            hasBid: False,
            punkIndex: punkIndex,
            bidder: empty(address),
            value: 0
        })


@external
def offerPunkForSale(punkIndex: uint256, minSalePriceInWei: uint256):
    assert self.punkIndexToAddress[punkIndex] == msg.sender
    assert punkIndex < 10000
    self.punksOfferedForSale[punkIndex] = Offer({
        isForSale: True,
        punkIndex: punkIndex,
        seller: msg.sender,
        minValue: minSalePriceInWei,
        onlySellTo: empty(address)
    })
    log PunkOffered(punkIndex, minSalePriceInWei, empty(address))


@external
def offerPunkForSaleToAddress(punkIndex: uint256, minSalePriceInWei: uint256, toAddress: address):
    assert self.punkIndexToAddress[punkIndex] == msg.sender
    assert punkIndex < 10000
    self.punksOfferedForSale[punkIndex] = Offer({
        isForSale: True,
        punkIndex: punkIndex,
        seller: msg.sender,
        minValue: minSalePriceInWei,
        onlySellTo: toAddress
    })
    log PunkOffered(punkIndex, minSalePriceInWei, toAddress)


@payable
@external
def buyPunk(punkIndex: uint256):
    assert punkIndex < 10000
    offer: Offer = self.punksOfferedForSale[punkIndex]
    assert offer.isForSale
    assert offer.onlySellTo == empty(address) or offer.onlySellTo == msg.sender
    assert offer.seller == self.punkIndexToAddress[punkIndex]
    assert msg.value >= offer.minValue

    self._removeTokenFrom(offer.seller, punkIndex)
    self._addTokenTo(msg.sender, punkIndex)
    log Transfer(offer.seller, msg.sender, 1)

    self.punkNoLongerForSale(punkIndex)
    self.pendingWithdrawals[offer.seller] += msg.value
    log PunkBought(punkIndex, msg.value, offer.seller, msg.sender)

    bid: Bid = self.punkBids[punkIndex]
    if bid.bidder == msg.sender:
        self.pendingWithdrawals[msg.sender] += bid.value
        self.punkBids[punkIndex] = Bid({
            hasBid: False,
            punkIndex: punkIndex,
            bidder: empty(address),
            value: 0
        })


@external
def withdraw():
    amount: uint256 = self.pendingWithdrawals[msg.sender]
    self.pendingWithdrawals[msg.sender] = 0
    send(msg.sender, amount)


@payable
@external
def enterBidForPunk(punkIndex: uint256):
    assert punkIndex < 10000
    assert self.punkIndexToAddress[punkIndex] != msg.sender
    assert self.punkIndexToAddress[punkIndex] != empty(address)
    assert msg.value > 0

    existing: Bid = self.punkBids[punkIndex]
    assert msg.value > existing.value
    if existing.value > 0:
        self.pendingWithdrawals[existing.bidder] += existing.value
    self.punkBids[punkIndex] = Bid({
        hasBid: True,
        punkIndex: punkIndex,
        bidder: msg.sender,
        value: msg.value
    })
    log PunkBidEntered(punkIndex, msg.value, msg.sender)


@external
def acceptBidForPunk(punkIndex: uint256, minPrice: uint256):
    assert punkIndex < 10000
    assert self.punkIndexToAddress[punkIndex] == msg.sender

    bid: Bid = self.punkBids[punkIndex]
    assert bid.value > 0
    assert bid.value >= minPrice

    self._removeTokenFrom(msg.sender, punkIndex)
    self._addTokenTo(bid.bidder, punkIndex)
    log Transfer(msg.sender, bid.bidder, 1)

    self.punksOfferedForSale[punkIndex] = Offer({
        isForSale: False,
        punkIndex: punkIndex,
        seller: msg.sender,
        minValue: 0,
        onlySellTo: empty(address)
    })
    self.punkBids[punkIndex] = Bid({
        hasBid: False,
        punkIndex: punkIndex,
        bidder: empty(address),
        value: 0
    })
    self.pendingWithdrawals[msg.sender] += bid.value
    log PunkBought(punkIndex, bid.value, msg.sender, bid.bidder)


@external
def withdrawBidForPunk(punkIndex: uint256):
    assert punkIndex < 10000
    assert self.punkIndexToAddress[punkIndex] != msg.sender
    assert self.punkIndexToAddress[punkIndex] != empty(address)

    bid: Bid = self.punkBids[punkIndex]
    assert bid.bidder == msg.sender
    log PunkBidWithdrawn(punkIndex, bid.value, msg.sender)
    self.punkBids[punkIndex] = Bid({
        hasBid: False,
        punkIndex: punkIndex,
        bidder: empty(address),
        value: 0
    })
    send(msg.sender, bid.value)


# Aditional functions, not part of original contract


@external
def mint(toAddress: address, punkIndex: uint256) -> bool:
    assert msg.sender == self.owner
    assert toAddress != empty(address)
    assert self.punksRemainingToAssign > 0
    assert punkIndex < 10000
    assert self.punkIndexToAddress[punkIndex] == empty(address)

    self._addTokenTo(toAddress, punkIndex)
    self.totalSupply += 1
    self.punksRemainingToAssign -= 1

    log Assign(toAddress, punkIndex)
    return True


@view
@external
def walletOf(_wallet: address) -> DynArray[uint256, 2**16]:
    return self.wallet[_wallet]


@view
@external
def ownerOf(punkIndex: uint256) -> address:
    return self.punkIndexToAddress[punkIndex]

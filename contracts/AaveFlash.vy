# @version 0.4.1

from ethereum.ercs import IERC20


FLASH_LOAN_CALLBACK_SIZE: constant(uint256) = 1024

interface P2PLendingNfts:
    def payment_token() -> address: view


interface IFlashLoanSimpleReceiver:
    def executeOperation(asset: address, amount: uint256, premium: uint256, initiator: address, params: Bytes[FLASH_LOAN_CALLBACK_SIZE]) -> bool: nonpayable
    def ADDRESSES_PROVIDER() -> address: view
    def POOL() -> address: view


interface IPoolProvider:
    def getPool() -> address: view


interface IPool:
    def flashLoanSimple(
        receiverAddress: address,
        asset: address,
        amount: uint256,
        params: Bytes[FLASH_LOAN_CALLBACK_SIZE],
        referralCode: uint16
    ): nonpayable


implements: IFlashLoanSimpleReceiver


MAX_FEES: constant(uint256) = 4
BPS: constant(uint256) = 10000

p2p_lending_nfts: address
aave_pool_provider: address

@deploy
def __init__(_p2p_lending_nfts: address, _aave_pool_provider: address):
    self.p2p_lending_nfts = _p2p_lending_nfts
    self.aave_pool_provider = _aave_pool_provider



@external
def executeOperation(
    asset: address,
    amount: uint256,
    premium: uint256,
    initiator: address,
    params: Bytes[FLASH_LOAN_CALLBACK_SIZE]
) -> bool:
    # raw_call(0x0000000000000000000000000000000000011111, abi_encode(b"callback"))
    assert initiator == self, "who are you?"
    aave_pool: address = staticcall IPoolProvider(self.aave_pool_provider).getPool()
    payment_token: address = staticcall P2PLendingNfts(self.p2p_lending_nfts).payment_token()

    # assert premium == 0, "Premium not supported"

    assert (staticcall IERC20(payment_token).balanceOf(self)) >= amount + premium, "Insufficient balance"
    assert msg.sender == aave_pool, "Unauthorized"
    assert asset == payment_token, "Invalid asset"

# do stuff with the amount

    extcall IERC20(payment_token).approve(aave_pool, amount + premium)

    return True


@external
@view
def ADDRESSES_PROVIDER() -> address:
    return self.aave_pool_provider

@external
@view
def POOL() -> address:
    return staticcall IPoolProvider(self.aave_pool_provider).getPool()

@external
def flash_loan(amount: uint256):
    # raw_call(0x0000000000000000000000000000000000011111, abi_encode(b"flash loan"))
    aave_pool: address = staticcall IPoolProvider(self.aave_pool_provider).getPool()
    payment_token: address = staticcall P2PLendingNfts(self.p2p_lending_nfts).payment_token()
    extcall IERC20(payment_token).transferFrom(msg.sender, self, amount) # remove
    extcall IPool(aave_pool).flashLoanSimple(self, payment_token, amount, b"", 0)

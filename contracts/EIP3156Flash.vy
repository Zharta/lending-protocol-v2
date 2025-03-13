# @version 0.4.1

from ethereum.ercs import IERC20

FLASH_LOAN_CALLBACK_SIZE: constant(uint256) = 1024

interface P2PLendingNfts:
    def payment_token() -> address: view


# https://eips.ethereum.org/EIPS/eip-3156
interface IFlashLender:
    def maxFlashLoan(token: address) -> uint256: view
    def flashFee(token: address, amount: uint256) -> uint256: view
    def flashLoan(receiver: address, token: address, amount: uint256, data: Bytes[FLASH_LOAN_CALLBACK_SIZE]) -> bool: nonpayable


interface IERC3156FlashBorrower:
    def onFlashLoan(
        initiator: address,
        token: address,
        amount: uint256,
        fee: uint256,
        data: Bytes[FLASH_LOAN_CALLBACK_SIZE]
    ) -> bytes32: nonpayable


implements: IERC3156FlashBorrower


struct CallbackData:
    dummy: uint256

ERC3156_CALLBACK_OK: constant(bytes32) = keccak256("ERC3156FlashBorrower.onFlashLoan")

MAX_FEES: constant(uint256) = 4

p2p_lending_nfts: public(immutable(address))
flash_lender: public(immutable(address))

@deploy
def __init__(_p2p_lending_nfts: address, _flash_lender: address):
    p2p_lending_nfts = _p2p_lending_nfts
    flash_lender = _flash_lender


@external
def onFlashLoan(
    initiator: address,
    token: address,
    amount: uint256,
    fee: uint256,
    data: Bytes[FLASH_LOAN_CALLBACK_SIZE]
) -> bytes32:

    # raw_call(0x0000000000000000000000000000000000011111, abi_encode(b"callback"))
    assert msg.sender == flash_lender, "unauthorized"
    assert initiator == self, "unknown initiator"
    assert fee == 0, "fee not supported"

    callback_data: CallbackData = abi_decode(data, CallbackData)

    payment_token: address = staticcall P2PLendingNfts(p2p_lending_nfts).payment_token()
    assert token == payment_token, "Invalid asset"

    assert (staticcall IERC20(payment_token).balanceOf(self)) >= amount, "Insufficient balance"

    # do stuff with the flash loan

    extcall IERC20(payment_token).approve(flash_lender, amount + fee)
    return ERC3156_CALLBACK_OK


@external
def flash_loan(amount: uint256):
    # raw_call(0x0000000000000000000000000000000000011111, abi_encode(b"flash loan"))
    payment_token: address = staticcall P2PLendingNfts(p2p_lending_nfts).payment_token()
    callback_data: CallbackData = CallbackData(dummy = 42)
    assert extcall IFlashLender(flash_lender).flashLoan(self, payment_token, amount, abi_encode(callback_data)), "flash loan failed"

# @version 0.4.1

"""
Balancer Mock based implementing needed functions for testing
"""

from ethereum.ercs import IERC20
from ethereum.ercs import IERC20Detailed

FLASH_LOAN_MAX_TOKENS: constant(uint256) = 5
FLASH_LOAN_CALLBACK_SIZE: constant(uint256) = 10240

interface IFlashLender:
    def flashLoan(
        recepient: address,
        tokens: DynArray[address,FLASH_LOAN_MAX_TOKENS],
        amounts: DynArray[uint256,FLASH_LOAN_MAX_TOKENS],
        data: Bytes[FLASH_LOAN_CALLBACK_SIZE]
    ): nonpayable


interface IFlashLoanRecipient:
    def receiveFlashLoan(
        tokens: DynArray[address,FLASH_LOAN_MAX_TOKENS],
        amounts: DynArray[uint256,FLASH_LOAN_MAX_TOKENS],
        fee_amounts: DynArray[uint256,FLASH_LOAN_MAX_TOKENS],
        data: Bytes[FLASH_LOAN_CALLBACK_SIZE]
    ): nonpayable


implements: IFlashLender

deposits: HashMap[bytes32, uint256]

@deploy
def __init__():
    pass

@external
def flashLoan(
    recepient: address,
    tokens: DynArray[address,FLASH_LOAN_MAX_TOKENS],
    amounts: DynArray[uint256,FLASH_LOAN_MAX_TOKENS],
    data: Bytes[FLASH_LOAN_CALLBACK_SIZE]
):
    assert len(tokens) == len(amounts), "Mismatched input lengths"

    fee_amounts: DynArray[uint256,FLASH_LOAN_MAX_TOKENS] = []
    initial_balances: DynArray[uint256,FLASH_LOAN_MAX_TOKENS] = []

    for i: uint256 in range(len(tokens), bound=FLASH_LOAN_MAX_TOKENS):
        initial_balance: uint256 = staticcall IERC20(tokens[i]).balanceOf(self)
        if initial_balance < amounts[i]:
            raise "Insufficient liquidity for token"
        initial_balances.append(initial_balance)
        extcall IERC20(tokens[i]).transfer(recepient, amounts[i])
        fee_amounts.append(0)

    extcall IFlashLoanRecipient(recepient).receiveFlashLoan(
        tokens,
        amounts,
        fee_amounts,
        data
    )

    for i: uint256 in range(len(tokens), bound=FLASH_LOAN_MAX_TOKENS):
        if staticcall IERC20(tokens[i]).balanceOf(self) < initial_balances[i]:
            raise "Flash loan not repaid"




@external
def deposit(token: address, amount: uint256):
    key: bytes32 = self._account_key(msg.sender, token)
    extcall IERC20(token).transferFrom(msg.sender, self, amount)
    self.deposits[key] += amount

@external
def withdraw(token: address, amount: uint256):
    key: bytes32 = self._account_key(msg.sender, token)
    assert self.deposits[key] >= amount, "Insufficient balance"
    self.deposits[key] -= amount
    extcall IERC20(token).transfer(msg.sender, amount)


@external
@view
def balanceOf(wallet: address, token: address) -> uint256:
    return self.deposits[self._account_key(wallet, token)]


@internal
@view
def _account_key(wallet: address, token: address) -> bytes32:
    return keccak256(concat(convert(wallet, bytes32), convert(token, bytes32)))

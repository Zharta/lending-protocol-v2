# @version 0.4.1

"""
Arcade Mock based implementing needed functions for testing
"""

from ethereum.ercs import IERC20
from ethereum.ercs import IERC721
from ethereum.ercs import IERC20Detailed


interface Arcade:
    def repay(loan_id: uint256): nonpayable
    def getLoan(loan_id: uint256) -> LoanData: view
    def getInterestAmount(principal: uint256, proratedInterestRate: uint256) -> uint256: view

implements: Arcade

struct LoanData:
    state: LoanState
    startDate: uint160
    terms: LoanTerms
    feeSnapshot: FeeSnapshot

struct FeeSnapshot:
    lenderDefaultFee: uint16
    lenderInterestFee: uint16
    lenderPrincipalFee: uint16

struct LoanTerms:
    proratedInterestRate: uint256
    principal: uint256
    collateralAddress: address
    durationSecs: uint96
    collateralId: uint256
    payableCurrency: address
    deadline: uint96
    affiliateCode: bytes32

flag LoanState:
    DUMMY_DO_NOT_USE
    ACTIVE
    REPAID
    DEFAULTED


event LoanStarted:
    loanId: uint256
    lender: address
    borrower: address

event LoanRepaid:
    loanId: uint256


BPS : constant(uint256) = 10000

loans: public(HashMap[uint256, LoanData])
lenders: public(HashMap[uint256, address])
borrowers: public(HashMap[uint256, address])
loan_counter: public(uint256)


@deploy
def __init__():
    self.loan_counter = 0

@external
def startLoan(lender: address, loan_terms: LoanTerms) -> uint256:
    loan_id: uint256 = self.loan_counter
    self.loans[loan_id] = LoanData(
        state=LoanState.ACTIVE,
        startDate=convert(block.timestamp, uint160),
        terms=loan_terms,
        feeSnapshot=FeeSnapshot(
            lenderDefaultFee=0,
            lenderInterestFee=0,
            lenderPrincipalFee=0
        )
    )
    self.lenders[loan_id] = lender
    self.borrowers[loan_id] = msg.sender
    self.loan_counter += 1
    extcall IERC20(loan_terms.payableCurrency).transferFrom(lender, msg.sender, loan_terms.principal)
    extcall IERC721(loan_terms.collateralAddress).transferFrom(msg.sender, self, loan_terms.collateralId)
    log LoanStarted(loanId=loan_id, lender=lender, borrower=msg.sender)
    return loan_id

@external
def repay(loan_id: uint256):
    assert self.loans[loan_id].state == LoanState.ACTIVE, "Loan not active"
    loan: LoanData = self.loans[loan_id]
    interest: uint256 = self._get_interest_amount(loan.terms.principal, loan.terms.proratedInterestRate)
    total_repayment: uint256 = loan.terms.principal + interest
    extcall IERC20(loan.terms.payableCurrency).transferFrom(msg.sender, self.lenders[loan_id], total_repayment)
    self.loans[loan_id].state = LoanState.REPAID
    extcall IERC721(loan.terms.collateralAddress).transferFrom(self, self.borrowers[loan_id], loan.terms.collateralId)
    log LoanRepaid(loanId=loan_id)

@external
@view
def getLoan(loan_id: uint256) -> LoanData:
    return self.loans[loan_id]

@external
@view
def getInterestAmount(principal: uint256, proratedInterestRate: uint256) -> uint256:
    return self._get_interest_amount(principal, proratedInterestRate)

@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)

@internal
@pure
def _get_interest_amount(principal: uint256, proratedInterestRate: uint256) -> uint256:
    return (principal * proratedInterestRate) // 10**18 // BPS

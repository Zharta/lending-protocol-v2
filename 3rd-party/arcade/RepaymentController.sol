// SPDX-License-Identifier: MIT

pragma solidity 0.8.18;

import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

import "./interfaces/IRepaymentController.sol";
import "./interfaces/IPromissoryNote.sol";
import "./interfaces/ILoanCore.sol";
import "./interfaces/IFeeController.sol";

import "./libraries/InterestCalculator.sol";
import "./libraries/FeeLookups.sol";
import "./libraries/LoanLibrary.sol";

import {
    RC_ZeroAddress,
    RC_CannotDereference,
    RC_InvalidState,
    RC_OnlyLender
} from "./errors/Lending.sol";

/**
 * @title RepaymentController
 * @author Non-Fungible Technologies, Inc.
 *
 * The Repayment Controller is the entry point for all loan lifecycle
 * operations in the Arcade.xyz lending protocol once a loan has begun.
 * This contract allows a caller to calculate an amount due on a loan,
 * repay an open loan, and claim collateral on a defaulted loan. It
 * is this contract's responsibility to verify loan conditions before
 * calling LoanCore.
 */
contract RepaymentController is IRepaymentController, InterestCalculator, FeeLookups {
    using SafeERC20 for IERC20;

    // ============================================ STATE ===============================================

    ILoanCore private immutable loanCore;
    IPromissoryNote private immutable lenderNote;
    IFeeController private immutable feeController;

    // ========================================= CONSTRUCTOR ============================================

    /**
     * @notice Creates a new repayment controller contract.
     *
     * @dev For this controller to work, it needs to be granted the REPAYER_ROLE
     *      in loan core after deployment.
     *
     * @param _loanCore                     The address of the loan core logic of the protocol.
     * @param _feeController                The address of the fee logic of the protocol.
     */
    constructor(address _loanCore, address _feeController) {
        if (_loanCore == address(0)) revert RC_ZeroAddress("loanCore");
        if (_feeController == address(0)) revert RC_ZeroAddress("feeController");

        loanCore = ILoanCore(_loanCore);
        lenderNote = loanCore.lenderNote();
        feeController = IFeeController(_feeController);
    }

    // ==================================== LIFECYCLE OPERATIONS ========================================

    /**
     * @notice Repay an active loan, referenced by borrower note ID (equivalent to loan ID). The interest for a loan
     *         is calculated, and the principal plus interest is withdrawn from the caller.
     *         Anyone can repay a loan. Control is passed to LoanCore to complete repayment.
     *
     * @param  loanId               The ID of the loan.
     */
    function repay(uint256 loanId) external override {
        (uint256 amountFromBorrower, uint256 amountToLender) = _prepareRepay(loanId);

        // call repay function in loan core -  msg.sender will pay the amountFromBorrower
        loanCore.repay(loanId, msg.sender, amountFromBorrower, amountToLender);
    }

    /**
     * @notice Repay an active loan, referenced by borrower note ID (equivalent to loan ID). The interest for a loan
     *         is calculated, and the principal plus interest is withdrawn from the caller. Anyone can repay a loan.
     *         Using forceRepay will not send funds to the lender: instead, those funds will be made
     *         available for withdrawal in LoanCore. Can be used in cases where a borrower has funds to repay
     *         but the lender is not able to receive those tokens (e.g. token blacklist).
     *
     * @param  loanId               The ID of the loan.
     */
    function forceRepay(uint256 loanId) external override {
        (uint256 amountFromBorrower, uint256 amountToLender) = _prepareRepay(loanId);

        // call repay function in loan core -  msg.sender will pay the amountFromBorrower
        loanCore.forceRepay(loanId, msg.sender, amountFromBorrower, amountToLender);
    }

    /**
     * @notice Claim collateral on an active loan, referenced by lender note ID (equivalent to loan ID).
     *         The loan must be past the due date. No funds are collected
     *         from the borrower.
     *
     * @param  loanId               The ID of the loan.
     */
    function claim(uint256 loanId) external override {
        LoanLibrary.LoanData memory data = loanCore.getLoan(loanId);
        if (data.state == LoanLibrary.LoanState.DUMMY_DO_NOT_USE) revert RC_CannotDereference(loanId);

        // make sure that caller owns lender note
        // Implicitly checks if loan is active - if inactive, note will not exist
        address lender = lenderNote.ownerOf(loanId);
        if (lender != msg.sender) revert RC_OnlyLender(lender, msg.sender);

        LoanLibrary.LoanTerms memory terms = data.terms;
        uint256 interest = getInterestAmount(terms.principal, terms.proratedInterestRate);
        uint256 totalOwed = terms.principal + interest;

        uint256 claimFee = (totalOwed * data.feeSnapshot.lenderDefaultFee) / BASIS_POINTS_DENOMINATOR;

        loanCore.claim(loanId, claimFee);
    }

    /**
     * @notice Redeem a lender note for a completed return in return for funds repaid in an earlier
     *         transaction via forceRepay. The lender note must be owned by the caller.
     *
     * @param loanId                    The ID of the lender note to redeem.
     */
    function redeemNote(uint256 loanId, address to) external override {
        if (to == address(0)) revert RC_ZeroAddress("to");

        LoanLibrary.LoanData memory data = loanCore.getLoan(loanId);
        (, uint256 amountOwed) = loanCore.getNoteReceipt(loanId);

        if (data.state != LoanLibrary.LoanState.Repaid) revert RC_InvalidState(data.state);
        address lender = lenderNote.ownerOf(loanId);
        if (lender != msg.sender) revert RC_OnlyLender(lender, msg.sender);

        uint256 redeemFee = (amountOwed * feeController.getLendingFee(FL_08)) / BASIS_POINTS_DENOMINATOR;

        loanCore.redeemNote(loanId, redeemFee, to);
    }

    // =========================================== HELPERS ==============================================

    /**
     * @dev Shared logic to perform validation and calculations for repay and forceRepay.
     *
     * @param loanId               The ID of the loan.
     *
     * @return amountFromBorrower   The amount to collect from the borrower.
     * @return amountToLender       The amount owed to the lender.
     */
    function _prepareRepay(uint256 loanId) internal view returns (uint256 amountFromBorrower, uint256 amountToLender) {
        LoanLibrary.LoanData memory data = loanCore.getLoan(loanId);
        if (data.state == LoanLibrary.LoanState.DUMMY_DO_NOT_USE) revert RC_CannotDereference(loanId);
        if (data.state != LoanLibrary.LoanState.Active) revert RC_InvalidState(data.state);

        LoanLibrary.LoanTerms memory terms = data.terms;

        uint256 interest = getInterestAmount(terms.principal, terms.proratedInterestRate);

        uint256 interestFee = (interest * data.feeSnapshot.lenderInterestFee) / BASIS_POINTS_DENOMINATOR;
        uint256 principalFee = (terms.principal * data.feeSnapshot.lenderPrincipalFee) / BASIS_POINTS_DENOMINATOR;

        amountFromBorrower = terms.principal + interest;
        amountToLender = amountFromBorrower - interestFee - principalFee;
    }
}

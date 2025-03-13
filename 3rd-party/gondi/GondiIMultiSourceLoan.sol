// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.21;

import "./IBaseLoan.sol";

/// @title Multi Source Loan Interface
/// @author Florida St
/// @notice A multi source loan is one with multiple tranches.
interface IMultiSourceLoan {
    /// @notice Borrowers receive offers that are then validated.
    /// @dev Setting the nftCollateralTokenId to 0 triggers validation through `validators`.
    /// @param offerId Offer ID. Used for canceling/setting as executed.
    /// @param lender Lender of the offer.
    /// @param fee Origination fee.
    /// @param capacity Capacity of the offer.
    /// @param nftCollateralAddress Address of the NFT collateral.
    /// @param nftCollateralTokenId NFT collateral token ID.
    /// @param principalAddress Address of the principal.
    /// @param principalAmount Principal amount of the loan.
    /// @param aprBps APR in BPS.
    /// @param expirationTime Expiration time of the offer.
    /// @param duration Duration of the loan in seconds.
    /// @param maxSeniorRepayment Max amount of senior capital ahead (principal + interest).
    /// @param validators Arbitrary contract to validate offers implementing `IBaseOfferValidator`.
    struct LoanOffer {
        uint256 offerId;
        address lender;
        uint256 fee;
        uint256 capacity;
        address nftCollateralAddress;
        uint256 nftCollateralTokenId;
        address principalAddress;
        uint256 principalAmount;
        uint256 aprBps;
        uint256 expirationTime;
        uint256 duration;
        uint256 maxSeniorRepayment;
        IBaseLoan.OfferValidator[] validators;
    }

    /// @notice Offer + how much will be filled (always <= principalAmount).
    /// @param offer Offer.
    /// @param amount Amount to be filled.
    struct OfferExecution {
        LoanOffer offer;
        uint256 amount;
        bytes lenderOfferSignature;
    }

    /// @notice Offer + necessary fields to execute a specific loan. This has a separate expirationTime to avoid
    /// someone holding an offer and executing much later, without the borrower's awareness.
    /// @dev It's advised that borrowers only set an expirationTime close to the actual time they will execute the loan
    ///      to avoid replays.
    /// @param offerExecution List of offers to be filled and amount for each.
    /// @param tokenId NFT collateral token ID.
    /// @param amount The amount the borrower is willing to take (must be <= _loanOffer principalAmount)
    /// @param expirationTime Expiration time of the signed offer by the borrower.
    /// @param callbackData Data to pass to the callback.
    struct ExecutionData {
        OfferExecution[] offerExecution;
        uint256 tokenId;
        uint256 duration;
        uint256 expirationTime;
        address principalReceiver;
        bytes callbackData;
    }

    /// @param executionData Execution data.
    /// @param borrower Address that owns the NFT and will take over the loan.
    /// @param borrowerOfferSignature Signature of the offer (signed by borrower).
    /// @param callbackData Whether to call the afterPrincipalTransfer callback
    struct LoanExecutionData {
        ExecutionData executionData;
        address borrower;
        bytes borrowerOfferSignature;
    }

    /// @param loanId Loan ID.
    /// @param callbackData Whether to call the afterNFTTransfer callback
    /// @param shouldDelegate Whether to delegate ownership of the NFT (avoid seaport flags).
    struct SignableRepaymentData {
        uint256 loanId;
        bytes callbackData;
        bool shouldDelegate;
    }

    /// @param loan Loan.
    /// @param borrowerLoanSignature Signature of the loan (signed by borrower).
    struct LoanRepaymentData {
        SignableRepaymentData data;
        Loan loan;
        bytes borrowerSignature;
    }

    /// @notice Tranches have different seniority levels.
    /// @param loanId Loan ID.
    /// @param floor Amount of principal more senior to this tranche.
    /// @param principalAmount Total principal in this tranche.
    /// @param lender Lender for this given tranche.
    /// @param accruedInterest Accrued Interest.
    /// @param startTime Start Time. Either the time at which the loan initiated / was refinanced.
    /// @param aprBps APR in basis points.
    struct Tranche {
        uint256 loanId;
        uint256 floor;
        uint256 principalAmount;
        address lender;
        uint256 accruedInterest;
        uint256 startTime;
        uint256 aprBps;
    }

    /// @dev Principal Amount is equal to the sum of all tranches principalAmount.
    /// We keep it for caching purposes. Since we are not saving this on chain but the hash,
    /// it does not have a huge impact on gas.
    /// @param borrower Borrower.
    /// @param nftCollateralTokenId NFT Collateral Token ID.
    /// @param nftCollateralAddress NFT Collateral Address.
    /// @param principalAddress Principal Address.
    /// @param principalAmount Principal Amount.
    /// @param startTime Start Time.
    /// @param duration Duration.
    /// @param tranche Tranches.
    /// @param protocolFee Protocol Fee.
    struct Loan {
        address borrower;
        uint256 nftCollateralTokenId;
        address nftCollateralAddress;
        address principalAddress;
        uint256 principalAmount;
        uint256 startTime;
        uint256 duration;
        Tranche[] tranche;
        uint256 protocolFee;
    }

    /// @notice Renegotiation offer.
    /// @param renegotiationId Renegotiation ID.
    /// @param loanId Loan ID.
    /// @param lender Lender.
    /// @param fee Fee.
    /// @param trancheIndex Tranche Indexes to be refinanced.
    /// @param principalAmount Principal Amount. If more than one tranche, it must be the sum.
    /// @param aprBps APR in basis points.
    /// @param expirationTime Expiration Time.
    /// @param duration Duration.
    struct RenegotiationOffer {
        uint256 renegotiationId;
        uint256 loanId;
        address lender;
        uint256 fee;
        uint256[] trancheIndex;
        uint256 principalAmount;
        uint256 aprBps;
        uint256 expirationTime;
        uint256 duration;
    }

    event LoanLiquidated(uint256 loanId);
    event LoanEmitted(uint256 loanId, uint256[] offerId, Loan loan, uint256 fee);
    event LoanRefinanced(uint256 renegotiationId, uint256 oldLoanId, uint256 newLoanId, Loan loan, uint256 fee);
    event LoanRepaid(uint256 loanId, uint256 totalRepayment, uint256 fee);
    event LoanRefinancedFromNewOffers(
        uint256 loanId, uint256 newLoanId, Loan loan, uint256[] offerIds, uint256 totalFee
    );
    event Delegated(uint256 loanId, address delegate, bytes32 _rights, bool value);
    event FlashActionContractUpdated(address newFlashActionContract);
    event FlashActionExecuted(uint256 loanId, address target, bytes data);
    event RevokeDelegate(address delegate, address collection, uint256 tokenId, bytes32 _rights);
    event MinLockPeriodUpdated(uint256 minLockPeriod);

    /// @notice Call by the borrower when emiting a new loan.
    /// @param _loanExecutionData Loan execution data.
    /// @return loanId Loan ID.
    /// @return loan Loan.
    function emitLoan(LoanExecutionData calldata _loanExecutionData) external returns (uint256, Loan memory);

    /// @notice Refinance whole loan (leaving just one tranche).
    /// @param _renegotiationOffer Offer to refinance a loan.
    /// @param _loan Current loan.
    /// @param _renegotiationOfferSignature Signature of the offer.
    /// @return loanId New Loan Id, New Loan.
    function refinanceFull(
        RenegotiationOffer calldata _renegotiationOffer,
        Loan memory _loan,
        bytes calldata _renegotiationOfferSignature
    ) external returns (uint256, Loan memory);

    /// @notice Add a new tranche to a loan.
    /// @param _renegotiationOffer Offer for new tranche.
    /// @param _loan Current loan.
    /// @param _renegotiationOfferSignature Signature of the offer.
    /// @return loanId New Loan Id
    /// @return loan New Loan.
    function addNewTranche(
        RenegotiationOffer calldata _renegotiationOffer,
        Loan memory _loan,
        bytes calldata _renegotiationOfferSignature
    ) external returns (uint256, Loan memory);

    /// @notice Refinance a loan partially. It can only be called by the new lender
    /// (they are always a strict improvement on apr).
    /// @param _renegotiationOffer Offer to refinance a loan partially.
    /// @param _loan Current loan.
    /// @return loanId New Loan Id, New Loan.
    /// @return loan New Loan.
    function refinancePartial(RenegotiationOffer calldata _renegotiationOffer, Loan memory _loan)
        external
        returns (uint256, Loan memory);

    /// @notice Refinance a loan from LoanExecutionData. We let borrowers use outstanding offers for new loans
    ///         to refinance their current loan.
    /// @param _loanId Loan ID.
    /// @param _loan Current loan.
    /// @param _loanExecutionData Loan Execution Data.
    /// @return loanId New Loan Id.
    /// @return loan New Loan.
    function refinanceFromLoanExecutionData(
        uint256 _loanId,
        Loan calldata _loan,
        LoanExecutionData calldata _loanExecutionData
    ) external returns (uint256, Loan memory);

    /// @notice Repay loan. Interest is calculated pro-rata based on time. Lender is defined by nft ownership.
    /// @param _repaymentData Repayment data.
    function repayLoan(LoanRepaymentData calldata _repaymentData) external;

    /// @notice Call when a loan is past its due date.
    /// @param _loanId Loan ID.
    /// @param _loan Loan.
    /// @return Liquidation Struct of the liquidation.
    function liquidateLoan(uint256 _loanId, Loan calldata _loan) external returns (bytes memory);

    /// @return getMaxTranches Maximum number of tranches per loan.
    function getMaxTranches() external view returns (uint256);

    /// @notice Set min lock period (in BPS).
    /// @param _minLockPeriod Min lock period.
    function setMinLockPeriod(uint256 _minLockPeriod) external;

    /// @notice Get min lock period (in BPS).
    /// @return minLockPeriod Min lock period.
    function getMinLockPeriod() external view returns (uint256);

    /// @notice Get delegation registry.
    /// @return delegateRegistry Delegate registry.
    function getDelegateRegistry() external view returns (address);

    /// @notice Delegate ownership.
    /// @param _loanId Loan ID.
    /// @param _loan Loan.
    /// @param _rights Delegation Rights. Empty for all.
    /// @param _delegate Delegate address.
    /// @param _value True if delegate, false if undelegate.
    function delegate(uint256 _loanId, Loan calldata _loan, address _delegate, bytes32 _rights, bool _value) external;

    /// @notice Anyone can reveke a delegation on an NFT that's no longer in escrow.
    /// @param _delegate Delegate address.
    /// @param _collection Collection address.
    /// @param _tokenId Token ID.
    /// @param _rights Delegation Rights. Empty for all.
    function revokeDelegate(address _delegate, address _collection, uint256 _tokenId, bytes32 _rights) external;

    /// @notice Get Flash Action Contract.
    /// @return flashActionContract Flash Action Contract.
    function getFlashActionContract() external view returns (address);

    /// @notice Update Flash Action Contract.
    /// @param _newFlashActionContract Flash Action Contract.
    function setFlashActionContract(address _newFlashActionContract) external;

    /// @notice Get Loan Hash.
    /// @param _loanId Loan ID.
    /// @return loanHash Loan Hash.
    function getLoanHash(uint256 _loanId) external view returns (bytes32);

    /// @notice Transfer NFT to the flash action contract (expected use cases here are for airdrops and similar scenarios).
    /// The flash action contract would implement specific interactions with given contracts.
    /// Only the the borrower can call this function for a given loan. By the end of the transaction, the NFT must have
    /// been returned to escrow.
    /// @param _loanId Loan ID.
    /// @param _loan Loan.
    /// @param _target Target address for the flash action contract to interact with.
    /// @param _data Data to be passed to be passed to the ultimate contract.
    function executeFlashAction(uint256 _loanId, Loan calldata _loan, address _target, bytes calldata _data) external;

    /// @notice Called by the liquidator for accounting purposes.
    /// @param _loanId The id of the loan.
    /// @param _loan The loan object.
    function loanLiquidated(uint256 _loanId, Loan calldata _loan) external;
}

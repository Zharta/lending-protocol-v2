// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.21;

import "@delegate/IDelegateRegistry.sol";
import "@openzeppelin/utils/cryptography/ECDSA.sol";
import "@solmate/tokens/ERC20.sol";
import "@solmate/tokens/ERC721.sol";
import "@solmate/utils/FixedPointMathLib.sol";
import "@solmate/utils/ReentrancyGuard.sol";
import "@solmate/utils/SafeTransferLib.sol";

import "../../interfaces/validators/IOfferValidator.sol";
import "../../interfaces/INFTFlashAction.sol";
import "../../interfaces/loans/ILoanManager.sol";
import "../../interfaces/loans/ILoanManagerRegistry.sol";
import "../../interfaces/loans/IMultiSourceLoan.sol";
import "../utils/Hash.sol";
import "../utils/Interest.sol";
import "../Multicall.sol";
import "./BaseLoan.sol";

/// @title MultiSourceLoan (v3)
/// @author Florida St
/// @notice Loan contract that allows for multiple tranches with different
///         seniorities. Each loan is collateralized by an NFT. Loans have a duration,
///         principal, and APR. Loans can be refinanced automatically by lenders (if terms
///         are improved). Borrowers can also get renegotiation offers which they can then
///         accept. If a loan is not repaid by its end time, it's considered to have defaulted.
///         If it had only one lender behind it, then the lender (unless it's a pool), can claim
///         the collateral. If there are multiple lenders or the sole lender is a pool, then there's
///         a liquidation process (run by an instance of `ILoanLiquidator`).
contract MultiSourceLoan is IMultiSourceLoan, Multicall, ReentrancyGuard, BaseLoan {
    using FixedPointMathLib for uint256;
    using Hash for ExecutionData;
    using Hash for Loan;
    using Hash for LoanOffer;
    using Hash for SignableRepaymentData;
    using Hash for RenegotiationOffer;
    using InputChecker for address;
    using Interest for uint256;
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;
    using SafeTransferLib for ERC20;

    /// @notice Loan Id to hash
    mapping(uint256 loanId => bytes32 loanHash) private _loans;

    /// This is used in _getMinTranchePrincipal.
    uint256 private constant _MAX_RATIO_TRANCHE_MIN_PRINCIPAL = 2;

    /// @notice Maximum number of tranches per loan
    uint256 public immutable getMaxTranches;

    /// @notice delegate registry
    address public immutable getDelegateRegistry;

    /// @notice Contract to execute flash actions.
    address public getFlashActionContract;

    /// @notice Loan manager registry (we currently have Gondi's pools)
    ILoanManagerRegistry public immutable getLoanManagerRegistry;

    /// @notice Min lock period for a tranche
    uint256 private _minLockPeriod;

    error InvalidParametersError();
    error MismatchError();
    error InvalidCollateralIdError();
    error InvalidMethodError();
    error InvalidAddressesError();
    error InvalidCallerError();
    error InvalidTrancheError();
    error InvalidRenegotiationOfferError();
    error TooManyTranchesError();
    error LoanExpiredError();
    error NFTNotReturnedError();
    error TrancheCannotBeRefinancedError(uint256 minTimestamp);
    error LoanLockedError();

    /// @param loanLiquidator Address of the liquidator contract.
    /// @param protocolFee Protocol fee charged on gains.
    /// @param currencyManager Address of the currency manager.
    /// @param collectionManager Address of the collection manager.
    /// @param maxTranches Maximum number of tranches per loan.
    /// @param minLockPeriod Minimum lock period for a tranche/loan.
    /// @param delegateRegistry Address of the delegate registry (Delegate.xyz).
    /// @param loanManagerRegistry Address of the loan manager registry.
    /// @param flashActionContract Address of the flash action contract.
    /// @param minWaitTime The time to wait before a new owner can be set.
    constructor(
        address loanLiquidator,
        ProtocolFee memory protocolFee,
        address currencyManager,
        address collectionManager,
        uint256 maxTranches,
        uint256 minLockPeriod,
        address delegateRegistry,
        address loanManagerRegistry,
        address flashActionContract,
        uint256 minWaitTime
    )
        BaseLoan(
            "GONDI_MULTI_SOURCE_LOAN",
            currencyManager,
            collectionManager,
            protocolFee,
            loanLiquidator,
            tx.origin,
            minWaitTime
        )
    {
        loanLiquidator.checkNotZero();

        _minLockPeriod = minLockPeriod;
        getMaxTranches = maxTranches;
        getDelegateRegistry = delegateRegistry;
        getFlashActionContract = flashActionContract;
        getLoanManagerRegistry = ILoanManagerRegistry(loanManagerRegistry);
    }

    /// @inheritdoc IMultiSourceLoan
    function emitLoan(LoanExecutionData calldata _loanExecutionData)
        external
        nonReentrant
        returns (uint256, Loan memory)
    {
        address borrower = _loanExecutionData.borrower;
        ExecutionData calldata executionData = _loanExecutionData.executionData;
        (address principalAddress, address nftCollateralAddress) = _getAddressesFromExecutionData(executionData);

        OfferExecution[] calldata offerExecution = executionData.offerExecution;

        _validateExecutionData(_loanExecutionData, borrower);
        _checkWhitelists(principalAddress, nftCollateralAddress);

        (uint256 loanId, uint256[] memory offerIds, Loan memory loan, uint256 totalFee) =
        _processOffersFromExecutionData(
            borrower,
            executionData.principalReceiver,
            principalAddress,
            nftCollateralAddress,
            executionData.tokenId,
            executionData.duration,
            offerExecution
        );

        if (_hasCallback(executionData.callbackData)) {
            handleAfterPrincipalTransferCallback(loan, msg.sender, executionData.callbackData, totalFee);
        }

        ERC721(nftCollateralAddress).transferFrom(borrower, address(this), executionData.tokenId);

        _loans[loanId] = loan.hash();
        emit LoanEmitted(loanId, offerIds, loan, totalFee);

        return (loanId, loan);
    }

    /// @inheritdoc IMultiSourceLoan
    function refinanceFull(
        RenegotiationOffer calldata _renegotiationOffer,
        Loan memory _loan,
        bytes calldata _renegotiationOfferSignature
    ) external nonReentrant returns (uint256, Loan memory) {
        _baseLoanChecks(_renegotiationOffer.loanId, _loan);
        _baseRenegotiationChecks(_renegotiationOffer, _loan);

        if (_renegotiationOffer.trancheIndex.length != _loan.tranche.length) {
            revert InvalidRenegotiationOfferError();
        }

        bool lenderInitiated = msg.sender == _renegotiationOffer.lender;
        uint256 netNewLender = _renegotiationOffer.principalAmount - _renegotiationOffer.fee;
        uint256 totalAccruedInterest;
        uint256 totalAnnualInterest;

        /// @dev If it's lender initiated, needs to be strictly better.
        if (lenderInitiated) {
            (totalAccruedInterest, totalAnnualInterest,) =
                _processOldTranchesFull(_renegotiationOffer, _loan, lenderInitiated, 0);
            if (_isLoanLocked(_loan.startTime, _loan.duration)) {
                revert LoanLockedError();
            }
            _checkStrictlyBetter(
                _renegotiationOffer.principalAmount,
                _loan.principalAmount,
                _renegotiationOffer.duration + block.timestamp,
                _loan.duration + _loan.startTime,
                _renegotiationOffer.aprBps,
                totalAnnualInterest / _loan.principalAmount,
                _renegotiationOffer.fee
            );
            if (_renegotiationOffer.principalAmount > _loan.principalAmount) {
                ERC20(_loan.principalAddress).safeTransferFrom(
                    _renegotiationOffer.lender,
                    _loan.borrower,
                    _renegotiationOffer.principalAmount - _loan.principalAmount
                );
            }
        } else if (msg.sender != _loan.borrower) {
            revert InvalidCallerError();
        } else {
            (totalAccruedInterest, totalAnnualInterest, netNewLender) =
                _processOldTranchesFull(_renegotiationOffer, _loan, lenderInitiated, netNewLender);
            /// @notice Borrowers clears interest
            _checkSignature(_renegotiationOffer.lender, _renegotiationOffer.hash(), _renegotiationOfferSignature);
            if (netNewLender > 0) {
                ERC20(_loan.principalAddress).safeTransferFrom(_renegotiationOffer.lender, _loan.borrower, netNewLender);
            }
            totalAccruedInterest = 0;
        }
        uint256 newLoanId = _getAndSetNewLoanId();
        Tranche[] memory newTranche = new Tranche[](1);
        newTranche[0] = Tranche(
            newLoanId,
            0,
            _renegotiationOffer.principalAmount,
            _renegotiationOffer.lender,
            totalAccruedInterest,
            block.timestamp,
            _renegotiationOffer.aprBps
        );
        _loan.tranche = newTranche;
        _loan.startTime = block.timestamp;
        _loan.duration = _renegotiationOffer.duration;
        _loan.principalAmount = _renegotiationOffer.principalAmount;

        _loans[newLoanId] = _loan.hash();
        delete _loans[_renegotiationOffer.loanId];

        emit LoanRefinanced(
            _renegotiationOffer.renegotiationId, _renegotiationOffer.loanId, newLoanId, _loan, _renegotiationOffer.fee
        );

        return (newLoanId, _loan);
    }

    /// @inheritdoc IMultiSourceLoan
    function refinancePartial(RenegotiationOffer calldata _renegotiationOffer, Loan memory _loan)
        external
        nonReentrant
        returns (uint256, Loan memory)
    {
        if (msg.sender != _renegotiationOffer.lender) {
            revert InvalidCallerError();
        }

        if (_isLoanLocked(_loan.startTime, _loan.duration)) {
            revert LoanLockedError();
        }
        if (_renegotiationOffer.trancheIndex.length == 0) {
            revert InvalidRenegotiationOfferError();
        }

        uint256 loanId = _renegotiationOffer.loanId;
        _baseLoanChecks(loanId, _loan);
        _baseRenegotiationChecks(_renegotiationOffer, _loan);

        uint256 newLoanId = _getAndSetNewLoanId();
        uint256 totalProtocolFee;
        uint256 totalAnnualInterest;
        uint256 totalRefinanced;
        /// @dev bring to mem
        uint256 minImprovementApr = _minImprovementApr;
        /// @dev We iterate over all tranches to execute repayments.
        uint256 totalTranchesRenegotiated = _renegotiationOffer.trancheIndex.length;
        for (uint256 i; i < totalTranchesRenegotiated;) {
            uint256 index = _renegotiationOffer.trancheIndex[i];
            if (index >= _loan.tranche.length) {
                revert InvalidRenegotiationOfferError();
            }
            Tranche memory tranche = _loan.tranche[index];
            _checkTrancheStrictly(true, tranche.aprBps, _renegotiationOffer.aprBps, minImprovementApr);
            (uint256 accruedInterest, uint256 thisProtocolFee,) = _processOldTranche(
                _renegotiationOffer.lender,
                _loan.borrower,
                _loan.principalAddress,
                tranche,
                _loan.startTime + _loan.duration,
                _loan.protocolFee,
                type(uint256).max
            );
            unchecked {
                totalRefinanced += tranche.principalAmount;
                totalAnnualInterest += tranche.principalAmount * tranche.aprBps;
                totalProtocolFee += thisProtocolFee;
            }

            tranche.loanId = newLoanId;
            tranche.lender = _renegotiationOffer.lender;
            tranche.accruedInterest = accruedInterest;
            tranche.startTime = block.timestamp;
            tranche.aprBps = _renegotiationOffer.aprBps;
            unchecked {
                ++i;
            }
        }

        if (_renegotiationOffer.principalAmount != totalRefinanced) {
            revert InvalidRenegotiationOfferError();
        }
        _handleProtocolFeeForFee(
            _loan.principalAddress, _renegotiationOffer.lender, totalProtocolFee, _protocolFee.recipient
        );

        _loans[newLoanId] = _loan.hash();
        delete _loans[loanId];

        /// @dev Here reneg fee is always 0
        emit LoanRefinanced(_renegotiationOffer.renegotiationId, loanId, newLoanId, _loan, 0);

        return (newLoanId, _loan);
    }

    /// @inheritdoc IMultiSourceLoan
    function refinanceFromLoanExecutionData(
        uint256 _loanId,
        Loan calldata _loan,
        LoanExecutionData calldata _loanExecutionData
    ) external nonReentrant returns (uint256, Loan memory) {
        if (msg.sender != _loan.borrower) {
            revert InvalidCallerError();
        }
        _baseLoanChecks(_loanId, _loan);

        ExecutionData calldata executionData = _loanExecutionData.executionData;
        /// @dev We ignore the borrower in executionData, and used existing one.
        address borrower = _loan.borrower;
        (address principalAddress, address nftCollateralAddress) = _getAddressesFromExecutionData(executionData);

        OfferExecution[] calldata offerExecution = executionData.offerExecution;

        _validateExecutionData(_loanExecutionData, borrower);
        _checkWhitelists(principalAddress, nftCollateralAddress);

        if (_loan.principalAddress != principalAddress || _loan.nftCollateralAddress != nftCollateralAddress) {
            revert InvalidAddressesError();
        }
        if (_loan.nftCollateralTokenId != executionData.tokenId) {
            revert InvalidCollateralIdError();
        }

        /// @dev We first process the incoming offers so borrower gets the capital. After that, we process repayments.
        ///      NFT doesn't need to be transfered (it was already in escrow)
        (uint256 newLoanId, uint256[] memory offerIds, Loan memory loan, uint256 totalFee) =
        _processOffersFromExecutionData(
            borrower,
            executionData.principalReceiver,
            principalAddress,
            nftCollateralAddress,
            executionData.tokenId,
            executionData.duration,
            offerExecution
        );
        _processRepayments(_loan);

        emit LoanRefinancedFromNewOffers(_loanId, newLoanId, loan, offerIds, totalFee);

        _loans[newLoanId] = loan.hash();
        delete _loans[_loanId];

        return (newLoanId, loan);
    }

    /// @inheritdoc IMultiSourceLoan
    function addNewTranche(
        RenegotiationOffer calldata _renegotiationOffer,
        Loan memory _loan,
        bytes calldata _renegotiationOfferSignature
    ) external nonReentrant returns (uint256, Loan memory) {
        if (msg.sender != _loan.borrower) {
            revert InvalidCallerError();
        }
        uint256 loanId = _renegotiationOffer.loanId;

        _baseLoanChecks(loanId, _loan);
        _baseRenegotiationChecks(_renegotiationOffer, _loan);
        _checkSignature(_renegotiationOffer.lender, _renegotiationOffer.hash(), _renegotiationOfferSignature);

        if (_renegotiationOffer.trancheIndex.length != 1 || _renegotiationOffer.trancheIndex[0] != _loan.tranche.length)
        {
            revert InvalidRenegotiationOfferError();
        }

        if (_loan.tranche.length == getMaxTranches) {
            revert TooManyTranchesError();
        }

        uint256 newLoanId = _getAndSetNewLoanId();
        Loan memory loanWithTranche = _addNewTranche(newLoanId, _loan, _renegotiationOffer);
        _loans[newLoanId] = loanWithTranche.hash();
        delete _loans[loanId];

        ERC20(_loan.principalAddress).safeTransferFrom(
            _renegotiationOffer.lender, _loan.borrower, _renegotiationOffer.principalAmount - _renegotiationOffer.fee
        );
        if (_renegotiationOffer.fee != 0) {
            /// @dev Cached
            ERC20(_loan.principalAddress).safeTransferFrom(
                _renegotiationOffer.lender,
                _protocolFee.recipient,
                _renegotiationOffer.fee.mulDivUp(_loan.protocolFee, _PRECISION)
            );
        }

        emit LoanRefinanced(
            _renegotiationOffer.renegotiationId, loanId, newLoanId, loanWithTranche, _renegotiationOffer.fee
        );

        return (newLoanId, loanWithTranche);
    }

    /// @inheritdoc IMultiSourceLoan
    function repayLoan(LoanRepaymentData calldata _repaymentData) external override nonReentrant {
        uint256 loanId = _repaymentData.data.loanId;
        Loan calldata loan = _repaymentData.loan;
        /// @dev If the caller is not the borrower itself, check the signature to avoid someone else forcing an unwanted repayment.
        if (msg.sender != loan.borrower) {
            _checkSignature(loan.borrower, _repaymentData.data.hash(), _repaymentData.borrowerSignature);
        }

        _baseLoanChecks(loanId, loan);

        /// @dev Unlikely this is used outside of the callback with a seaport sell, but leaving here in case that's not correct.
        if (_repaymentData.data.shouldDelegate) {
            IDelegateRegistry(getDelegateRegistry).delegateERC721(
                loan.borrower, loan.nftCollateralAddress, loan.nftCollateralTokenId, bytes32(""), true
            );
        }

        ERC721(loan.nftCollateralAddress).transferFrom(address(this), loan.borrower, loan.nftCollateralTokenId);
        /// @dev After returning the NFT to the borrower, check if there's an action to be taken (eg: sell it to cover repayment).
        if (_hasCallback(_repaymentData.data.callbackData)) {
            handleAfterNFTTransferCallback(loan, msg.sender, _repaymentData.data.callbackData);
        }

        (uint256 totalRepayment, uint256 totalProtocolFee) = _processRepayments(loan);

        emit LoanRepaid(loanId, totalRepayment, totalProtocolFee);

        /// @dev Reclaim space.
        delete _loans[loanId];
    }

    /// @inheritdoc IMultiSourceLoan
    function liquidateLoan(uint256 _loanId, Loan calldata _loan)
        external
        override
        nonReentrant
        returns (bytes memory)
    {
        if (_loan.hash() != _loans[_loanId]) {
            revert InvalidLoanError(_loanId);
        }
        (bool liquidated, bytes memory liquidation) = _liquidateLoan(
            _loanId, _loan, _loan.tranche.length == 1 && !getLoanManagerRegistry.isLoanManager(_loan.tranche[0].lender)
        );
        if (liquidated) {
            delete _loans[_loanId];
        }
        return liquidation;
    }

    /// @inheritdoc IMultiSourceLoan
    function loanLiquidated(uint256 _loanId, Loan calldata _loan) external override onlyLiquidator {
        if (_loan.hash() != _loans[_loanId]) {
            revert InvalidLoanError(_loanId);
        }

        emit LoanLiquidated(_loanId);

        /// @dev Reclaim space.
        delete _loans[_loanId];
    }

    /// @inheritdoc IMultiSourceLoan
    function delegate(uint256 _loanId, Loan calldata loan, address _delegate, bytes32 _rights, bool _value) external {
        if (loan.hash() != _loans[_loanId]) {
            revert InvalidLoanError(_loanId);
        }
        if (msg.sender != loan.borrower) {
            revert InvalidCallerError();
        }
        IDelegateRegistry(getDelegateRegistry).delegateERC721(
            _delegate, loan.nftCollateralAddress, loan.nftCollateralTokenId, _rights, _value
        );

        emit Delegated(_loanId, _delegate, _rights, _value);
    }

    /// @inheritdoc IMultiSourceLoan
    function revokeDelegate(address _delegate, address _collection, uint256 _tokenId, bytes32 _rights) external {
        if (ERC721(_collection).ownerOf(_tokenId) == address(this)) {
            revert InvalidMethodError();
        }

        IDelegateRegistry(getDelegateRegistry).delegateERC721(_delegate, _collection, _tokenId, _rights, false);

        emit RevokeDelegate(_delegate, _collection, _tokenId, _rights);
    }

    /// @inheritdoc IMultiSourceLoan
    function getMinLockPeriod() external view returns (uint256) {
        return _minLockPeriod;
    }

    /// @inheritdoc IMultiSourceLoan
    function setMinLockPeriod(uint256 __minLockPeriod) external onlyOwner {
        _minLockPeriod = __minLockPeriod;

        emit MinLockPeriodUpdated(__minLockPeriod);
    }

    /// @inheritdoc IMultiSourceLoan
    function getLoanHash(uint256 _loanId) external view returns (bytes32) {
        return _loans[_loanId];
    }

    /// @inheritdoc IMultiSourceLoan
    function executeFlashAction(uint256 _loanId, Loan calldata _loan, address _target, bytes calldata _data)
        external
        nonReentrant
    {
        if (_loan.hash() != _loans[_loanId]) {
            revert InvalidLoanError(_loanId);
        }
        if (msg.sender != _loan.borrower) {
            revert InvalidCallerError();
        }
        address flashActionContract = getFlashActionContract;
        ERC721(_loan.nftCollateralAddress).transferFrom(address(this), flashActionContract, _loan.nftCollateralTokenId);
        INFTFlashAction(flashActionContract).execute(
            _loan.nftCollateralAddress, _loan.nftCollateralTokenId, _target, _data
        );

        if (ERC721(_loan.nftCollateralAddress).ownerOf(_loan.nftCollateralTokenId) != address(this)) {
            revert NFTNotReturnedError();
        }

        emit FlashActionExecuted(_loanId, _target, _data);
    }

    /// @inheritdoc IMultiSourceLoan
    function setFlashActionContract(address _newFlashActionContract) external onlyOwner {
        getFlashActionContract = _newFlashActionContract;

        emit FlashActionContractUpdated(_newFlashActionContract);
    }

    /// @notice Process repayments for tranches upon a full renegotiation.
    /// @param _renegotiationOffer The renegotiation offer.
    /// @param _loan The loan to be processed.
    /// @param _isStrictlyBetter Whether the new tranche needs to be strictly better than all previous ones.
    /// @param _remainingNewLender Amount left for new lender to pay
    function _processOldTranchesFull(
        RenegotiationOffer calldata _renegotiationOffer,
        Loan memory _loan,
        bool _isStrictlyBetter,
        uint256 _remainingNewLender
    ) private returns (uint256 totalAccruedInterest, uint256 totalAnnualInterest, uint256 remainingNewLender) {
        uint256 totalProtocolFee = _renegotiationOffer.fee.mulDivUp(_loan.protocolFee, _PRECISION);
        unchecked {
            _remainingNewLender += totalProtocolFee;

            /// @dev bring to mem
            uint256 minImprovementApr = _minImprovementApr;
            remainingNewLender = _isStrictlyBetter ? type(uint256).max : _remainingNewLender;
            // We iterate first for the new lender and then for the rest.
            // This way if he is owed some principal,
            // it's discounted before transfering to the other lenders
            for (uint256 i = 0; i < _loan.tranche.length << 1;) {
                Tranche memory tranche = _loan.tranche[i % _loan.tranche.length];
                bool onlyNewLenderPass = i < _loan.tranche.length;
                bool isNewLender = tranche.lender == _renegotiationOffer.lender;
                ++i;
                if (onlyNewLenderPass != isNewLender) continue;
                uint256 accruedInterest;
                uint256 thisProtocolFee;
                (accruedInterest, thisProtocolFee, remainingNewLender) = _processOldTranche(
                    _renegotiationOffer.lender,
                    _loan.borrower,
                    _loan.principalAddress,
                    tranche,
                    _loan.startTime + _loan.duration,
                    _loan.protocolFee,
                    remainingNewLender
                );
                _checkTrancheStrictly(_isStrictlyBetter, tranche.aprBps, _renegotiationOffer.aprBps, minImprovementApr);

                totalAnnualInterest += tranche.principalAmount * tranche.aprBps;
                totalAccruedInterest += accruedInterest;
                totalProtocolFee += thisProtocolFee;
            }
            uint256 lenderFee = remainingNewLender > totalProtocolFee ? totalProtocolFee : remainingNewLender;
            uint256 borrowerFee = totalProtocolFee - lenderFee;
            _handleProtocolFeeForFee(
                _loan.principalAddress, _renegotiationOffer.lender, lenderFee, _protocolFee.recipient
            );
            _handleProtocolFeeForFee(_loan.principalAddress, _loan.borrower, borrowerFee, _protocolFee.recipient);
            remainingNewLender -= lenderFee;
        }
    }

    /// @notice Process the current source tranche during a renegotiation.
    /// @param _lender The new lender.
    /// @param _borrower The borrower of the loan.
    /// @param _principalAddress The principal address of the loan.
    /// @param _tranche The tranche to be processed.
    /// @param _endTime The end time of the loan.
    /// @param _protocolFeeFraction The protocol fee fraction.
    /// @param _remainingNewLender The amount left for the new lender to pay.
    /// @return accruedInterest The accrued interest paid.
    /// @return thisProtocolFee The protocol fee paid for this tranche.
    /// @return remainingNewLender The amount left for the new lender to pay.
    function _processOldTranche(
        address _lender,
        address _borrower,
        address _principalAddress,
        Tranche memory _tranche,
        uint256 _endTime,
        uint256 _protocolFeeFraction,
        uint256 _remainingNewLender
    ) private returns (uint256 accruedInterest, uint256 thisProtocolFee, uint256 remainingNewLender) {
        uint256 unlockTime = _getUnlockedTime(_tranche.startTime, _endTime);
        if (unlockTime > block.timestamp) {
            revert TrancheCannotBeRefinancedError(unlockTime);
        }
        unchecked {
            accruedInterest =
                _tranche.principalAmount.getInterest(_tranche.aprBps, block.timestamp - _tranche.startTime);
            thisProtocolFee = accruedInterest.mulDivUp(_protocolFeeFraction, _PRECISION);
            accruedInterest += _tranche.accruedInterest;
        }

        if (getLoanManagerRegistry.isLoanManager(_tranche.lender)) {
            ILoanManager(_tranche.lender).loanRepayment(
                _tranche.loanId,
                _tranche.principalAmount,
                _tranche.aprBps,
                _tranche.accruedInterest,
                _protocolFeeFraction,
                _tranche.startTime
            );
        }

        uint256 oldLenderDebt;
        unchecked {
            oldLenderDebt = _tranche.principalAmount + accruedInterest - thisProtocolFee;
        }
        ERC20 asset = ERC20(_principalAddress);
        if (oldLenderDebt > _remainingNewLender) {
            /// @dev already checked in the condition
            asset.safeTransferFrom(_borrower, _tranche.lender, oldLenderDebt - _remainingNewLender);
            oldLenderDebt = _remainingNewLender;
        }
        if (oldLenderDebt > 0) {
            if (_lender != _tranche.lender) {
                asset.safeTransferFrom(_lender, _tranche.lender, oldLenderDebt);
            }
            /// @dev oldLenderDebt < _remainingNewLender because it would enter previous condition if not and set to _remainingNewLender
            unchecked {
                _remainingNewLender -= oldLenderDebt;
            }
        }
        remainingNewLender = _remainingNewLender;
    }

    /// @notice Basic loan checks (check if the hash is correct) + whether loan is still active.
    /// @param _loanId The loan ID.
    /// @param _loan The loan to be checked.
    function _baseLoanChecks(uint256 _loanId, Loan memory _loan) private view {
        if (_loan.hash() != _loans[_loanId]) {
            revert InvalidLoanError(_loanId);
        }
        if (_loan.startTime + _loan.duration <= block.timestamp) {
            revert LoanExpiredError();
        }
    }

    /// @notice Basic renegotiation checks. Check basic parameters + expiration + whether the offer is active.
    function _baseRenegotiationChecks(RenegotiationOffer calldata _renegotiationOffer, Loan memory _loan)
        private
        view
    {
        if (
            (_renegotiationOffer.principalAmount == 0)
                || (_loan.tranche.length < _renegotiationOffer.trancheIndex.length)
        ) {
            revert InvalidRenegotiationOfferError();
        }
        if (block.timestamp > _renegotiationOffer.expirationTime) {
            revert ExpiredOfferError(_renegotiationOffer.expirationTime);
        }
        uint256 renegotiationId = _renegotiationOffer.renegotiationId;
        address lender = _renegotiationOffer.lender;
        if (isRenegotiationOfferCancelled[lender][renegotiationId]) {
            revert CancelledOrExecutedOfferError(lender, renegotiationId);
        }
    }

    /// @notice Protocol fee for fees charged on offers/renegotationOffers.
    /// @param _principalAddress The principal address of the loan.
    /// @param _lender The lender of the loan.
    /// @param _fee The fee to be charged.
    /// @param _feeRecipient The protocol fee recipient.
    function _handleProtocolFeeForFee(address _principalAddress, address _lender, uint256 _fee, address _feeRecipient)
        private
    {
        if (_fee != 0) {
            ERC20(_principalAddress).safeTransferFrom(_lender, _feeRecipient, _fee);
        }
    }

    /// @notice Check condition for strictly better tranches
    /// @param _isStrictlyBetter Whether the new tranche needs to be strictly better than the old one.
    /// @param _currentAprBps The current apr of the tranche.
    /// @param _targetAprBps The target apr of the tranche.
    /// @param __minImprovementApr The minimum improvement in APR.
    function _checkTrancheStrictly(
        bool _isStrictlyBetter,
        uint256 _currentAprBps,
        uint256 _targetAprBps,
        uint256 __minImprovementApr
    ) private pure {
        /// @dev If _isStrictlyBetter is set, and the new apr is higher, then it'll underflow.
        if (
            _isStrictlyBetter
                && ((_currentAprBps - _targetAprBps).mulDivDown(_PRECISION, _currentAprBps) < __minImprovementApr)
        ) {
            revert InvalidRenegotiationOfferError();
        }
    }

    /// @dev Tranches are locked from any refi after they are initiated for some time.
    function _getUnlockedTime(uint256 _trancheStartTime, uint256 _loanEndTime) private view returns (uint256) {
        uint256 delta;
        unchecked {
            delta = _loanEndTime - _trancheStartTime;
        }
        return _trancheStartTime + delta.mulDivUp(_minLockPeriod, _PRECISION);
    }

    /// @dev Loans are locked from lender initiated refis in the end.
    function _isLoanLocked(uint256 _loanStartTime, uint256 _loanDuration) private view returns (bool) {
        unchecked {
            /// @dev doesn't overflow because _minLockPeriod should be < 1
            return block.timestamp > _loanStartTime + _loanDuration - _loanDuration.mulDivUp(_minLockPeriod, _PRECISION);
        }
    }

    /// @notice Base ExecutionData Checks
    /// @dev Note that we do not validate fee < principalAmount since this is done in the child class in this case.
    /// @param _offerExecution The offer execution.
    /// @param _tokenId The token ID.
    /// @param _lender The lender.
    /// @param _duration The duration.
    /// @param _lenderOfferSignature The signature of the lender of LoanOffer.
    /// @param _feeFraction The protocol fee fraction.
    /// @param _totalAmount The total amount ahead.
    function _validateOfferExecution(
        OfferExecution calldata _offerExecution,
        uint256 _tokenId,
        address _lender,
        uint256 _duration,
        bytes calldata _lenderOfferSignature,
        uint256 _feeFraction,
        uint256 _totalAmount
    ) private {
        LoanOffer calldata offer = _offerExecution.offer;
        address lender = offer.lender;
        uint256 offerId = offer.offerId;
        uint256 totalAmountAfterExecution = _offerExecution.amount + _totalAmount;

        if (lender.code.length != 0 && getLoanManagerRegistry.isLoanManager(lender)) {
            ILoanManager(lender).validateOffer(_tokenId, abi.encode(_offerExecution), _feeFraction);
        } else {
            _checkSignature(lender, offer.hash(), _lenderOfferSignature);
        }

        if (block.timestamp > offer.expirationTime) {
            revert ExpiredOfferError(offer.expirationTime);
        }

        if (isOfferCancelled[_lender][offerId] || (offerId <= minOfferId[_lender])) {
            revert CancelledOrExecutedOfferError(_lender, offerId);
        }

        if (totalAmountAfterExecution > offer.principalAmount) {
            revert InvalidAmountError(totalAmountAfterExecution, offer.principalAmount);
        }

        if (offer.duration == 0 || _duration > offer.duration) {
            revert InvalidDurationError();
        }
        if (offer.aprBps == 0) {
            revert ZeroInterestError();
        }
        if ((offer.capacity != 0) && (_used[_lender][offer.offerId] + _offerExecution.amount > offer.capacity)) {
            revert MaxCapacityExceededError();
        }

        _checkValidators(_offerExecution.offer, _tokenId);
    }

    /// @notice Basic checks (expiration / signature if diff than borrower) for execution data.
    function _validateExecutionData(LoanExecutionData calldata _executionData, address _borrower) private view {
        if (msg.sender != _borrower) {
            _checkSignature(_borrower, _executionData.executionData.hash(), _executionData.borrowerOfferSignature);
        }
        if (block.timestamp > _executionData.executionData.expirationTime) {
            revert ExpiredOfferError(_executionData.executionData.expirationTime);
        }
        if (_executionData.executionData.offerExecution.length > getMaxTranches) {
            revert TooManyTranchesError();
        }
    }

    /// @notice Extract addresses from first offer. Used for validations.
    /// @param _executionData Execution data.
    /// @return principalAddress Address of the principal token.
    /// @return nftCollateralAddress Address of the NFT collateral.
    function _getAddressesFromExecutionData(ExecutionData calldata _executionData)
        private
        pure
        returns (address, address)
    {
        LoanOffer calldata one = _executionData.offerExecution[0].offer;
        return (one.principalAddress, one.nftCollateralAddress);
    }

    /// @notice Check addresses are whitelisted.
    /// @param _principalAddress Address of the principal token.
    /// @param _nftCollateralAddress Address of the NFT collateral.
    function _checkWhitelists(address _principalAddress, address _nftCollateralAddress) private view {
        if (!_currencyManager.isWhitelisted(_principalAddress)) {
            revert CurrencyNotWhitelistedError();
        }
        if (!_collectionManager.isWhitelisted(_nftCollateralAddress)) {
            revert CollectionNotWhitelistedError();
        }
    }

    /// @notice Check principal/collateral addresses match.
    /// @param _offer The offer to check.
    /// @param _principalAddress Address of the principal token.
    /// @param _nftCollateralAddress Address of the NFT collateral.
    /// @param _amountWithInterestAhead Amount of more senior principal + max accrued interest ahead.
    function _checkOffer(
        LoanOffer calldata _offer,
        address _principalAddress,
        address _nftCollateralAddress,
        uint256 _amountWithInterestAhead
    ) private pure {
        if (_offer.principalAddress != _principalAddress || _offer.nftCollateralAddress != _nftCollateralAddress) {
            revert InvalidAddressesError();
        }
        if (_amountWithInterestAhead > _offer.maxSeniorRepayment) {
            revert InvalidTrancheError();
        }
    }

    /// @notice Check generic offer validators for a given offer or
    ///         an exact match if no validators are given. The validators
    ///         check is performed only if tokenId is set to 0.
    ///         Having one empty validator is used for collection offers (all IDs match).
    /// @param _loanOffer The loan offer to check.
    /// @param _tokenId The token ID to check.
    function _checkValidators(LoanOffer calldata _loanOffer, uint256 _tokenId) private view {
        uint256 offerTokenId = _loanOffer.nftCollateralTokenId;
        if (_loanOffer.nftCollateralTokenId != 0) {
            if (offerTokenId != _tokenId) {
                revert InvalidCollateralIdError();
            }
        } else {
            uint256 totalValidators = _loanOffer.validators.length;
            if (totalValidators == 0 && _tokenId != 0) {
                revert InvalidCollateralIdError();
            } else if ((totalValidators == 1) && _loanOffer.validators[0].validator == address(0)) {
                return;
            }
            for (uint256 i = 0; i < totalValidators;) {
                IBaseLoan.OfferValidator memory thisValidator = _loanOffer.validators[i];
                IOfferValidator(thisValidator.validator).validateOffer(_loanOffer, _tokenId, thisValidator.arguments);
                unchecked {
                    ++i;
                }
            }
        }
    }

    /// @dev Check new trnches are at least this big.
    function _getMinTranchePrincipal(uint256 _loanPrincipal) private view returns (uint256) {
        return _loanPrincipal / (_MAX_RATIO_TRANCHE_MIN_PRINCIPAL * getMaxTranches);
    }

    function _hasCallback(bytes calldata _callbackData) private pure returns (bool) {
        return _callbackData.length != 0;
    }

    function _processRepayments(Loan calldata loan) private returns (uint256, uint256) {
        bool withProtocolFee = loan.protocolFee != 0;
        uint256 totalRepayment = 0;
        uint256 totalProtocolFee = 0;

        ERC20 asset = ERC20(loan.principalAddress);
        uint256 totalTranches = loan.tranche.length;
        for (uint256 i; i < totalTranches;) {
            Tranche memory tranche = loan.tranche[i];
            uint256 newInterest =
                tranche.principalAmount.getInterest(tranche.aprBps, block.timestamp - tranche.startTime);
            uint256 thisProtocolFee = 0;
            if (withProtocolFee) {
                thisProtocolFee = newInterest.mulDivUp(loan.protocolFee, _PRECISION);
                unchecked {
                    totalProtocolFee += thisProtocolFee;
                }
            }
            uint256 repayment = tranche.principalAmount + tranche.accruedInterest + newInterest - thisProtocolFee;
            asset.safeTransferFrom(loan.borrower, tranche.lender, repayment);
            unchecked {
                totalRepayment += repayment;
            }
            if (getLoanManagerRegistry.isLoanManager(tranche.lender)) {
                ILoanManager(tranche.lender).loanRepayment(
                    tranche.loanId,
                    tranche.principalAmount,
                    tranche.aprBps,
                    tranche.accruedInterest,
                    loan.protocolFee,
                    tranche.startTime
                );
            }
            unchecked {
                ++i;
            }
        }

        if (withProtocolFee) {
            asset.safeTransferFrom(loan.borrower, _protocolFee.recipient, totalProtocolFee);
        }
        return (totalRepayment, totalProtocolFee);
    }

    /// @notice Process a series of offers and return the loan ID, offer IDs, loan (built from such offers) and total fee.
    /// @param _borrower The borrower of the loan.
    /// @param _principalReceiver The receiver of the principal.
    /// @param _principalAddress The principal address of the loan.
    /// @param _nftCollateralAddress The NFT collateral address of the loan.
    /// @param _tokenId The token ID of the loan.
    /// @param _duration The duration of the loan.
    /// @param _offerExecution The offer execution.
    /// @return loanId The loan ID.
    /// @return offerIds The offer IDs.
    /// @return loan The loan.
    /// @return totalFee The total fee.
    function _processOffersFromExecutionData(
        address _borrower,
        address _principalReceiver,
        address _principalAddress,
        address _nftCollateralAddress,
        uint256 _tokenId,
        uint256 _duration,
        OfferExecution[] calldata _offerExecution
    ) private returns (uint256, uint256[] memory, Loan memory, uint256) {
        Tranche[] memory tranche = new Tranche[](_offerExecution.length);
        uint256[] memory offerIds = new uint256[](_offerExecution.length);
        uint256 totalAmount;
        uint256 loanId = _getAndSetNewLoanId();

        ProtocolFee memory protocolFee = _protocolFee;
        LoanOffer calldata offer;
        uint256 totalFee;
        uint256 totalAmountWithMaxInterest;
        uint256 minAmount = type(uint256).max;
        uint256 totalOffers = _offerExecution.length;
        for (uint256 i = 0; i < totalOffers;) {
            OfferExecution calldata thisOfferExecution = _offerExecution[i];
            offer = thisOfferExecution.offer;
            _validateOfferExecution(
                thisOfferExecution,
                _tokenId,
                offer.lender,
                _duration,
                thisOfferExecution.lenderOfferSignature,
                protocolFee.fraction,
                totalAmount
            );
            uint256 amount = thisOfferExecution.amount;
            if (amount < minAmount) {
                minAmount = amount;
            }
            address lender = offer.lender;
            _checkOffer(offer, _principalAddress, _nftCollateralAddress, totalAmountWithMaxInterest);
            /// @dev Please note that we can now have many tranches with same `loanId`.
            tranche[i] = Tranche(loanId, totalAmount, amount, lender, 0, block.timestamp, offer.aprBps);
            unchecked {
                totalAmount += amount;
                totalAmountWithMaxInterest += amount + amount.getInterest(offer.aprBps, _duration);
            }

            uint256 fee;
            unchecked {
                fee = offer.fee.mulDivUp(amount, offer.principalAmount);
                totalFee += fee;
            }
            _handleProtocolFeeForFee(
                offer.principalAddress, lender, fee.mulDivUp(protocolFee.fraction, _PRECISION), protocolFee.recipient
            );

            ERC20(offer.principalAddress).safeTransferFrom(lender, _principalReceiver, amount - fee);
            if (offer.capacity != 0) {
                unchecked {
                    _used[lender][offer.offerId] += amount;
                }
            } else {
                isOfferCancelled[lender][offer.offerId] = true;
            }

            offerIds[i] = offer.offerId;
            unchecked {
                ++i;
            }
        }
        if (minAmount < _getMinTranchePrincipal(totalAmount)) {
            revert InvalidTrancheError();
        }
        Loan memory loan = Loan(
            _borrower,
            _tokenId,
            _nftCollateralAddress,
            _principalAddress,
            totalAmount,
            block.timestamp,
            _duration,
            tranche,
            protocolFee.fraction
        );

        return (loanId, offerIds, loan, totalFee);
    }

    function _addNewTranche(
        uint256 _newLoanId,
        IMultiSourceLoan.Loan memory _loan,
        IMultiSourceLoan.RenegotiationOffer calldata _renegotiationOffer
    ) private view returns (IMultiSourceLoan.Loan memory) {
        if (_renegotiationOffer.principalAmount < _getMinTranchePrincipal(_loan.principalAmount)) {
            revert InvalidTrancheError();
        }
        uint256 newTrancheIndex = _loan.tranche.length;
        IMultiSourceLoan.Tranche[] memory tranches = new IMultiSourceLoan.Tranche[](newTrancheIndex + 1);

        /// @dev Copy old tranches
        for (uint256 i = 0; i < newTrancheIndex;) {
            tranches[i] = _loan.tranche[i];
            unchecked {
                ++i;
            }
        }

        tranches[newTrancheIndex] = IMultiSourceLoan.Tranche(
            _newLoanId,
            _loan.principalAmount,
            _renegotiationOffer.principalAmount,
            _renegotiationOffer.lender,
            0,
            block.timestamp,
            _renegotiationOffer.aprBps
        );
        _loan.tranche = tranches;
        unchecked {
            _loan.principalAmount += _renegotiationOffer.principalAmount;
        }
        return _loan;
    }

    /// @notice Check a signature is valid given a hash and signer.
    /// @dev Comply with IERC1271 and EIP-712.
    function _checkSignature(address _signer, bytes32 _hash, bytes calldata _signature) private view {
        bytes32 typedDataHash = DOMAIN_SEPARATOR().toTypedDataHash(_hash);

        if (_signer.code.length != 0) {
            if (IERC1271(_signer).isValidSignature(typedDataHash, _signature) != MAGICVALUE_1271) {
                revert InvalidSignatureError();
            }
        } else {
            address recovered = typedDataHash.recover(_signature);
            if (_signer != recovered) {
                revert InvalidSignatureError();
            }
        }
    }

    /// @dev Check whether an offer is strictly better than a tranche
    function _checkStrictlyBetter(
        uint256 _offerPrincipalAmount,
        uint256 _loanPrincipalAmount,
        uint256 _offerEndTime,
        uint256 _loanEndTime,
        uint256 _offerAprBps,
        uint256 _loanAprBps,
        uint256 _offerFee
    ) internal view {
        uint256 minImprovementApr = _minImprovementApr;

        /// @dev If principal is increased, then we need to check net daily interest is better.
        /// interestDelta = (_loanAprBps * _loanPrincipalAmount - _offerAprBps * _offerPrincipalAmount)
        /// We already checked that all tranches are strictly better.
        /// We check that the duration is not decreased or the offer charges a fee.
        if (
            (
                (_offerPrincipalAmount - _loanPrincipalAmount != 0)
                    && (
                        (_loanAprBps * _loanPrincipalAmount - _offerAprBps * _offerPrincipalAmount).mulDivDown(
                            _PRECISION, _loanAprBps * _loanPrincipalAmount
                        ) < minImprovementApr
                    )
            ) || (_offerFee != 0) || (_offerEndTime < _loanEndTime)
        ) {
            revert NotStrictlyImprovedError();
        }
    }
}

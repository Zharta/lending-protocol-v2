// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.21;

import "@openzeppelin/utils/cryptography/MessageHashUtils.sol";
import "@openzeppelin/interfaces/IERC1271.sol";

import "@solmate/auth/Owned.sol";
import "@solmate/tokens/ERC721.sol";
import "@solmate/utils/FixedPointMathLib.sol";

import "../../interfaces/loans/IBaseLoan.sol";
import "../utils/Hash.sol";
import "../AddressManager.sol";
import "../LiquidationHandler.sol";

/// @title BaseLoan
/// @author Florida St
/// @notice Base implementation that we expect all loans to share. Offers can either be
///         for new loans or renegotiating existing ones.
///         Offers are signed off-chain.
///         Offers have a nonce associated that is used for cancelling and
///         marking as executed.
abstract contract BaseLoan is ERC721TokenReceiver, IBaseLoan, LiquidationHandler {
    using FixedPointMathLib for uint256;
    using InputChecker for address;
    using MessageHashUtils for bytes32;

    /// @notice Used in compliance with EIP712
    uint256 internal immutable INITIAL_CHAIN_ID;
    bytes32 public immutable INITIAL_DOMAIN_SEPARATOR;

    bytes4 internal constant MAGICVALUE_1271 = 0x1626ba7e;

    /// @notice Precision used for calculating interests.
    uint256 internal constant _PRECISION = 10000;

    bytes public constant VERSION = "3";

    /// @notice Minimum improvement (in BPS) required for a strict improvement.
    uint256 internal _minImprovementApr = 1000;

    string public name;

    /// @notice Total number of loans issued. Given it's a serial value, we use it
    ///         as loan id.
    uint256 public override getTotalLoansIssued;

    /// @notice Offer capacity
    mapping(address user => mapping(uint256 offerId => uint256 used)) internal _used;

    /// @notice Used for validate off chain maker offers / canceling one
    mapping(address user => mapping(uint256 offerId => bool notActive)) public isOfferCancelled;
    /// @notice Used for validating off chain maker offers / canceling all
    mapping(address user => uint256 minOfferId) public minOfferId;

    /// @notice Used in a similar way as `isOfferCancelled` to handle renegotiations.
    mapping(address user => mapping(uint256 renegotiationIf => bool notActive)) public isRenegotiationOfferCancelled;

    /// @notice Loans are only denominated in whitelisted addresses. Within each struct,
    ///         we save those as their `uint` representation.
    AddressManager internal immutable _currencyManager;

    /// @notice Only whilteslited collections are accepted as collateral. Within each struct,
    ///         we save those as their `uint` representation.
    AddressManager internal immutable _collectionManager;

    event OfferCancelled(address lender, uint256 offerId);

    event AllOffersCancelled(address lender, uint256 minOfferId);

    event RenegotiationOfferCancelled(address lender, uint256 renegotiationId);

    event MinAprImprovementUpdated(uint256 _minimum);

    error CancelledOrExecutedOfferError(address _lender, uint256 _offerId);

    error ExpiredOfferError(uint256 _expirationTime);

    error LowOfferIdError(address _lender, uint256 _newMinOfferId, uint256 _minOfferId);

    error LowRenegotiationOfferIdError(address _lender, uint256 _newMinRenegotiationOfferId, uint256 _minOfferId);

    error ZeroInterestError();

    error InvalidSignatureError();

    error CurrencyNotWhitelistedError();

    error CollectionNotWhitelistedError();

    error MaxCapacityExceededError();

    error InvalidLoanError(uint256 _loanId);

    error NotStrictlyImprovedError();

    error InvalidAmountError(uint256 _amount, uint256 _principalAmount);

    /// @notice Constructor
    /// @param _name The name of the loan contract
    /// @param currencyManager The address of the currency manager
    /// @param collectionManager The address of the collection manager
    /// @param protocolFee The protocol fee
    /// @param loanLiquidator The liquidator contract
    /// @param owner The owner of the contract
    /// @param minWaitTime The time to wait before a new owner can be set
    constructor(
        string memory _name,
        address currencyManager,
        address collectionManager,
        ProtocolFee memory protocolFee,
        address loanLiquidator,
        address owner,
        uint256 minWaitTime
    ) LiquidationHandler(owner, minWaitTime, loanLiquidator, protocolFee) {
        name = _name;
        currencyManager.checkNotZero();
        collectionManager.checkNotZero();

        _currencyManager = AddressManager(currencyManager);
        _collectionManager = AddressManager(collectionManager);

        INITIAL_CHAIN_ID = block.chainid;
        INITIAL_DOMAIN_SEPARATOR = _computeDomainSeparator();
    }

    /// @return The minimum improvement for a loan to be considered strictly better.
    function getMinImprovementApr() external view returns (uint256) {
        return _minImprovementApr;
    }

    /// @notice Updates the minimum improvement for a loan to be considered strictly better.
    ///         Only the owner can call this function.
    /// @param _newMinimum The new minimum improvement.
    function updateMinImprovementApr(uint256 _newMinimum) external onlyOwner {
        _minImprovementApr = _newMinimum;

        emit MinAprImprovementUpdated(_minImprovementApr);
    }

    /// @return Address of the currency manager.
    function getCurrencyManager() external view returns (address) {
        return address(_currencyManager);
    }

    /// @return Address of the collection manager.
    function getCollectionManager() external view returns (address) {
        return address(_collectionManager);
    }

    /// @inheritdoc IBaseLoan
    function cancelOffer(uint256 _offerId) external {
        address user = msg.sender;
        isOfferCancelled[user][_offerId] = true;

        emit OfferCancelled(user, _offerId);
    }

    /// @inheritdoc IBaseLoan
    function cancelAllOffers(uint256 _minOfferId) external virtual {
        address user = msg.sender;
        uint256 currentMinOfferId = minOfferId[user];
        if (currentMinOfferId >= _minOfferId) {
            revert LowOfferIdError(user, _minOfferId, currentMinOfferId);
        }
        minOfferId[user] = _minOfferId;

        emit AllOffersCancelled(user, _minOfferId);
    }

    /// @inheritdoc IBaseLoan
    function cancelRenegotiationOffer(uint256 _renegotiationId) external virtual {
        address lender = msg.sender;
        isRenegotiationOfferCancelled[lender][_renegotiationId] = true;

        emit RenegotiationOfferCancelled(lender, _renegotiationId);
    }

    /// @notice Returns the remaining capacity for a given loan offer.
    /// @param _lender The address of the lender.
    /// @param _offerId The id of the offer.
    /// @return The amount lent out.
    function getUsedCapacity(address _lender, uint256 _offerId) external view returns (uint256) {
        return _used[_lender][_offerId];
    }

    /// @notice Get the domain separator requried to comply with EIP-712.
    function DOMAIN_SEPARATOR() public view returns (bytes32) {
        return block.chainid == INITIAL_CHAIN_ID ? INITIAL_DOMAIN_SEPARATOR : _computeDomainSeparator();
    }

    /// @notice Call when issuing a new loan to get/set a unique serial id.
    /// @dev This id should never be 0.
    /// @return The new loan id.
    function _getAndSetNewLoanId() internal returns (uint256) {
        unchecked {
            return ++getTotalLoansIssued;
        }
    }

    /// @notice Compute domain separator for EIP-712.
    /// @return The domain separator.
    function _computeDomainSeparator() private view returns (bytes32) {
        return keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256(bytes(name)),
                keccak256(VERSION),
                block.chainid,
                address(this)
            )
        );
    }
}

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple

import boa
import pytest
from eth_abi import encode
from eth_account import Account
from eth_account.messages import HexBytes, SignableMessage, encode_structured_data
from eth_utils import keccak
from hypothesis import given, settings
from hypothesis import strategies as st
from web3 import Web3

from ..conftest_base import ZERO_ADDRESS, ZERO_BYTES32, CollectionContract, Offer, get_last_event, sign_offer

BPS = 10000
DAY = 86400
YEAR = 365 * DAY


class OfferValidator(NamedTuple):
    validator: str
    arguments: bytes


class LoanOffer(NamedTuple):
    offerId: int
    lender: str
    fee: int
    capacity: int
    nftCollateralAddress: str
    nftCollateralTokenId: int
    principalAddress: str
    principalAmount: int
    aprBps: int
    expirationTime: int
    duration: int
    maxSeniorRepayment: int
    validators: list[OfferValidator]


class OfferExecution(NamedTuple):
    offer: LoanOffer
    amount: int
    lenderOfferSignature: bytes


class ExecutionData(NamedTuple):
    offerExecution: list[OfferExecution]
    tokenId: int
    duration: int
    expirationTime: int
    principalReceiver: str
    callbackData: bytes


class LoanExecutionData(NamedTuple):
    executionData: ExecutionData
    borrower: str
    borrowerOfferSignature: bytes


class Tranche(NamedTuple):
    loanId: int
    floor: int
    principalAmount: int
    lender: str
    accruedInterest: int
    startTime: int
    aprBps: int


class GondiLoan(NamedTuple):
    borrower: str
    nftCollateralTokenId: int
    nftCollateralAddress: str
    principalAddress: str
    principalAmount: int
    startTime: int
    duration: int
    tranche: list[Tranche]
    protocolFee: int

    @classmethod
    def from_tuple(cls, t):
        (
            borrower,
            nftCollateralTokenId,
            nftCollateralAddress,
            principalAddress,
            principalAmount,
            startTime,
            duration,
            tranche,
            protocolFee,
        ) = t
        return cls(
            borrower,
            nftCollateralTokenId,
            nftCollateralAddress,
            principalAddress,
            principalAmount,
            startTime,
            duration,
            [Tranche(*t) for t in tranche],
            protocolFee,
        )


class SignableRepaymentData(NamedTuple):
    loanId: int
    callbackData: bytes
    shouldDelegate: bool


class LoanRepaymentData(NamedTuple):
    data: SignableRepaymentData
    loan: GondiLoan
    borrowerSignature: bytes


@pytest.fixture
def p2p_control(p2p_lending_control_contract_def, owner, cryptopunks, bayc, bayc_key_hash, punks_key_hash):
    p2p_control = p2p_lending_control_contract_def.deploy()
    p2p_control.change_collections_contracts([CollectionContract(bayc_key_hash, bayc.address)])
    return p2p_control


@pytest.fixture
def p2p_nfts_usdc(p2p_lending_nfts_contract_def, usdc, delegation_registry, cryptopunks, owner, p2p_control):
    return p2p_lending_nfts_contract_def.deploy(
        usdc, p2p_control, delegation_registry, cryptopunks, 0, 0, owner, 10000, 10000, 10000, 10000
    )


@pytest.fixture
def gondi_proxy(gondi_proxy_contract_def, p2p_nfts_usdc):
    aave_pool_address_provider = "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e"
    proxy = gondi_proxy_contract_def.deploy(p2p_nfts_usdc.address, aave_pool_address_provider)
    p2p_nfts_usdc.set_proxy_authorization(proxy, True, sender=p2p_nfts_usdc.owner())
    return proxy


@pytest.fixture
def aave(boa_env):
    return boa.load_abi("contracts/auxiliary/AavePoolv3_abi.json", name="AavePoolv3").at(
        "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    )


@pytest.fixture
def gondi(boa_env):
    return boa.load_abi("contracts/auxiliary/GondiMultiSourceLoan_abi.json", name="MultiSourceLoan").at(
        "0xf65B99CE6DC5F6c556172BCC0Ff27D3665a7d9A8"
    )


def test_initial_state(aave, gondi_proxy, usdc, p2p_nfts_usdc, borrower):
    assert gondi_proxy.POOL() == aave.address
    assert gondi_proxy.ADDRESSES_PROVIDER() == aave.ADDRESSES_PROVIDER()


def _create_gondi_loan(gondi, wpunk, token_id, borrower) -> GondiLoan:
    offer = LoanOffer(
        offerId=148,
        lender="0x08fA1D231580FF854DB5513ae8F877A25ddA9576",
        fee=800000000,
        capacity=0,
        nftCollateralAddress="0xb7F7F6C52F2e2fdb1963Eab30438024864c313F6",
        nftCollateralTokenId=0,
        principalAddress="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        principalAmount=45000000000,
        aprBps=1500,
        expirationTime=1733347599,
        duration=7776000,
        maxSeniorRepayment=0,
        validators=[
            OfferValidator(
                validator="0x0000000000000000000000000000000000000000",
                arguments=HexBytes(
                    "0x0000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000000"
                ),
            )
        ],
    )
    execution_data = ExecutionData(
        offerExecution=[
            OfferExecution(
                offer=offer,
                amount=45000000000,
                lenderOfferSignature=HexBytes(
                    "0x5b8fc44bb68dce40df16d939da4392e7e406423368452a79b1d598892a63302f51672d3bc271ef966538352dd7f387c1b4569bafa2760a712dd11f019cd4472e1c"
                ),
            )
        ],
        tokenId=token_id,
        duration=7776000,
        expirationTime=1733366815,
        principalReceiver=borrower,
        callbackData=b"",
    )

    loan_execution_data = LoanExecutionData(executionData=execution_data, borrower=borrower, borrowerOfferSignature=b"")

    wpunk.setApprovalForAll(gondi.address, True, sender=borrower)
    assert wpunk.isApprovedForAll(borrower, gondi.address)
    assert wpunk.ownerOf(6501) == borrower

    assert gondi.getLoanHash(891) == ZERO_BYTES32
    loan_id, loan = gondi.emitLoan(loan_execution_data, sender=borrower)
    return loan_id, GondiLoan.from_tuple(loan)


def _sign_repayment_data(data: SignableRepaymentData, signer_key: str, verifying_contract: str) -> bytes:
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "SignableRepaymentData": [
                {"name": "loanId", "type": "uint256"},
                {"name": "callbackData", "type": "bytes"},
                {"name": "shouldDelegate", "type": "bool"},
            ],
        },
        "primaryType": "SignableRepaymentData",
        "domain": {
            "name": "GONDI_MULTI_SOURCE_LOAN",
            "version": "3",
            "chainId": boa.eval("chain.id"),
            "verifyingContract": verifying_contract,
        },
        "message": data._asdict(),
    }
    signable_msg = encode_structured_data(typed_data)
    signed_msg = Account.from_key(signer_key).sign_message(signable_msg)
    return signed_msg.signature


def _test_pay_loan(gondi, gondi_proxy, usdc, borrower, owner, wpunk, now, borrower_key):
    repayment_data = SignableRepaymentData(loanId=459, callbackData=b"", shouldDelegate=False)
    loan_tranche = Tranche(
        loanId=459,
        floor=0,
        principalAmount=20000000000000000000,
        lender="0xb9b8Dc9ECaC8708A16F9c442063C2bFD74EaB78A",
        accruedInterest=0,
        startTime=1730864735,
        aprBps=1500,
    )

    gondi_loan = GondiLoan(
        borrower="0xD79b937791724e47F193f67162B92cDFbF7ABDFd",
        nftCollateralTokenId=4134,
        nftCollateralAddress=wpunk.address,
        principalAddress=usdc.address,
        principalAmount=20000000000000000000,
        startTime=1730864735,
        duration=2592000,
        tranche=[loan_tranche],
        protocolFee=0,
    )

    loan_repayment_data = LoanRepaymentData(data=repayment_data, loan=gondi_loan, borrowerSignature=b"")
    print(loan_repayment_data)


def test_pay_loan(gondi, gondi_proxy, usdc, borrower, owner, wpunk, now, borrower_key):
    token_id = 6501
    wpunk_owner = wpunk.ownerOf(token_id)
    wpunk.transferFrom(wpunk_owner, borrower, token_id, sender=wpunk_owner)

    loan_id, gondi_loan = _create_gondi_loan(gondi, wpunk, token_id, borrower)
    repayment_data = SignableRepaymentData(loanId=loan_id, callbackData=b"", shouldDelegate=False)

    loan_repayment_data = LoanRepaymentData(
        data=repayment_data,
        loan=gondi_loan,
        borrowerSignature=_sign_repayment_data(repayment_data, borrower_key, gondi.address),
    )

    actual_duration = now - gondi_loan.startTime
    interest = sum(
        tranche.accruedInterest + tranche.principalAmount * tranche.aprBps * actual_duration // (BPS * YEAR)
        for tranche in gondi_loan.tranche
    )
    borrower = gondi_loan.borrower
    amount = gondi_loan.principalAmount + interest
    # approved = gondi.address

    # usdc.transfer(gondi_proxy.address, amount, sender=owner)
    usdc.transfer(borrower, amount, sender=owner)
    usdc.approve(gondi.address, amount, sender=borrower)
    gondi_proxy.pay_gondi_loan(gondi.address, loan_repayment_data, gondi.address, usdc.address, amount, sender=borrower)

    assert wpunk.ownerOf(token_id) == borrower


def test_refinance(
    aave,
    borrower,
    borrower_key,
    debug_precompile,
    gondi,
    gondi_proxy,
    lender,
    lender_key,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    wpunk,
    wpunk_key_hash,
):
    token_id = 6501
    wpunk_owner = wpunk.ownerOf(token_id)
    wpunk.transferFrom(wpunk_owner, borrower, token_id, sender=wpunk_owner)

    loan_id, gondi_loan = _create_gondi_loan(gondi, wpunk, token_id, borrower)
    usdc.transfer(owner, usdc.balanceOf(borrower), sender=borrower)  # borrower spends loan amount

    repayment_data = SignableRepaymentData(loanId=loan_id, callbackData=b"", shouldDelegate=False)

    loan_repayment_data = LoanRepaymentData(
        data=repayment_data,
        loan=gondi_loan,
        borrowerSignature=_sign_repayment_data(repayment_data, borrower_key, gondi.address),
    )

    actual_duration = now - gondi_loan.startTime
    interest = sum(
        tranche.accruedInterest + tranche.principalAmount * tranche.aprBps * actual_duration // (BPS * YEAR)
        for tranche in gondi_loan.tranche
    )
    borrower = gondi_loan.borrower
    amount = gondi_loan.principalAmount + interest
    approved = gondi.address
    flash_loan_fee = amount * 5 // BPS  # TODO: change provider

    offer = Offer(
        principal=amount,
        interest=amount // 100,
        payment_token=usdc.address,
        duration=30 * 86400,
        collection_key_hash=wpunk_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=True,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    usdc.transfer(borrower, flash_loan_fee, sender=owner)
    usdc.transfer(lender, offer.principal, sender=owner)

    assert usdc.balanceOf(borrower) >= flash_loan_fee
    assert usdc.balanceOf(lender) >= offer.principal

    usdc.approve(gondi_proxy.address, amount + flash_loan_fee, sender=borrower)
    usdc.approve(gondi.address, amount, sender=borrower)
    usdc.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    wpunk.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(wpunk_key_hash, wpunk.address)])

    gondi_proxy.refinance_loan(gondi.address, approved, loan_repayment_data, amount, signed_offer, token_id, sender=borrower)

    assert wpunk.ownerOf(token_id) == p2p_nfts_usdc.address
    assert usdc.balanceOf(borrower) == 0

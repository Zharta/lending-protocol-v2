from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    CollateralStatus,
    Loan,
    Offer,
    Signature,
    SignedOffer,
    compute_loan_hash,
    compute_signed_offer_id,
    deploy_reverts,
    get_last_event,
    sign_offer,
)


@pytest.fixture
def broker():
    return boa.env.generate_address()


@pytest.fixture
def protocol_fee(p2p_nfts_eth):
    fee = p2p_nfts_eth.max_protocol_fee()
    p2p_nfts_eth.set_protocol_fee(fee, sender=p2p_nfts_eth.owner())
    return fee


@pytest.fixture
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_eth):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=10,
        broker_fee_bps=2000,
        broker_address=broker,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1
    )
    return sign_offer(offer, lender_key, p2p_nfts_eth.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_eth, offer_bayc, weth, borrower, lender, bayc, now, protocol_fee):

    offer = offer_bayc.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(offer_bayc, token_id, borrower, sender=borrower)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan

@pytest.fixture
def offer_punk(now, lender, lender_key, cryptopunks, broker, p2p_nfts_eth):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=10,
        broker_fee_bps=2000,
        broker_address=broker,
        collateral_contract=cryptopunks.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1
    )
    return sign_offer(offer, lender_key, p2p_nfts_eth.address)


@pytest.fixture
def ongoing_loan_punk(p2p_nfts_eth, offer_punk, weth, borrower, lender, cryptopunks, now, protocol_fee):
    offer = offer_punk.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    cryptopunks.mint(borrower, token_id)
    cryptopunks.offerPunkForSaleToAddress(token_id, 0, p2p_nfts_eth.address, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(offer_punk, token_id, borrower, sender=borrower)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=cryptopunks.address,
        collateral_token_id=token_id,
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan

# @external
# def claim_defaulted_loan_collateral(loan: Loan):
#     """
#     @notice Claim defaulted loan collateral
#     @param loan Loan
#     """
#     assert self._is_loan_valid(loan), "invalid loan"
#     assert block.timestamp > loan.maturity, "loan not defaulted"
#     assert loan.lender == msg.sender, "not lender"

#     self.loans[loan.id] = empty(bytes32)

#     self._transfer_collateral(loan.lender, loan.collateral_contract, loan.collateral_token_id)

#     log LoanCollateralClaimed(
#         loan.id,
#         loan.borrower,
#         loan.lender,
#         loan.collateral_contract,
#         loan.collateral_token_id
#     )


def test_claim_defaulted_reverts_if_loan_invalid(p2p_nfts_eth, ongoing_loan_bayc):
    invalid_loans = [
        Loan(**ongoing_loan_bayc._asdict() | {"id": ZERO_BYTES32}),
        Loan(**ongoing_loan_bayc._asdict() | {"amount": ongoing_loan_bayc.amount + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"interest": ongoing_loan_bayc.interest + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"payment_token": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"maturity": ongoing_loan_bayc.maturity - 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"start_time": ongoing_loan_bayc.start_time - 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"borrower": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"lender": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"collateral_contract": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"collateral_token_id": ongoing_loan_bayc.collateral_token_id + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"origination_fee_amount": ongoing_loan_bayc.origination_fee_amount + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"broker_fee_bps": ongoing_loan_bayc.broker_fee_bps + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"broker_address": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"protocol_fee_bps": ongoing_loan_bayc.protocol_fee_bps + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"pro_rata": not ongoing_loan_bayc.pro_rata})
    ]

    for loan in invalid_loans:
        print(f"{loan=}")
        with boa.reverts("invalid loan"):
            p2p_nfts_eth.claim_defaulted_loan_collateral(loan, sender=ongoing_loan_bayc.borrower)


def test_claim_defaulted_reverts_if_loan_not_defaulted(p2p_nfts_eth, ongoing_loan_bayc, now):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default - 1)

    with boa.reverts("loan not defaulted"):
        p2p_nfts_eth.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)


def test_claim_defaulted_reverts_if_not_lender(p2p_nfts_eth, ongoing_loan_bayc, now):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("not lender"):
        p2p_nfts_eth.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)


def test_claim_defaulted(p2p_nfts_eth, ongoing_loan_bayc, now, weth):
    time_to_default = ongoing_loan_bayc.maturity - now

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_eth.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)

    assert p2p_nfts_eth.loans(ongoing_loan_bayc.id) == ZERO_BYTES32
    assert boa.env.get_balance(p2p_nfts_eth.address) == 0


def test_claim_defaulted_logs_event(p2p_nfts_eth, ongoing_loan_bayc, now, weth):
    time_to_default = ongoing_loan_bayc.maturity - now

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_eth.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)

    event = get_last_event(p2p_nfts_eth, "LoanCollateralClaimed")
    assert event.id == ongoing_loan_bayc.id
    assert event.borrower == ongoing_loan_bayc.borrower
    assert event.lender == ongoing_loan_bayc.lender
    assert event.collateral_contract == ongoing_loan_bayc.collateral_contract
    assert event.collateral_token_id == ongoing_loan_bayc.collateral_token_id


def test_claim_defaulted_transfers_collateral_to_lender(p2p_nfts_eth, ongoing_loan_bayc, now, weth, bayc):
    time_to_default = ongoing_loan_bayc.maturity - now
    collateral_token_id = ongoing_loan_bayc.collateral_token_id

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_eth.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)

    assert bayc.ownerOf(collateral_token_id) == ongoing_loan_bayc.lender


def test_claim_defaulted_transfers_collateral_to_lender_punk(p2p_nfts_eth, ongoing_loan_punk, now, weth, cryptopunks):
    time_to_default = ongoing_loan_punk.maturity - now
    collateral_token_id = ongoing_loan_punk.collateral_token_id

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_eth.claim_defaulted_loan_collateral(ongoing_loan_punk, sender=ongoing_loan_punk.lender)

    assert cryptopunks.ownerOf(collateral_token_id) == ongoing_loan_punk.lender

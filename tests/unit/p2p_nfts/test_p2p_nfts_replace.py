import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    Fee,
    FeeAmount,
    FeeType,
    Loan,
    Offer,
    OfferType,
    SignedOffer,
    compute_loan_hash,
    compute_signed_offer_id,
    get_last_event,
    get_loan_mutations,
    replace_namedtuple_field,
    sign_offer,
)


@pytest.fixture(autouse=True)
def lender_funds(lender, usdc):
    usdc.mint(lender, 10**12)


@pytest.fixture(autouse=True)
def lender2_funds(lender2, usdc):
    usdc.mint(lender2, 10**12)


@pytest.fixture(autouse=True)
def borrower_funds(borrower, usdc):
    usdc.mint(borrower, 10**12)


@pytest.fixture
def broker():
    return boa.env.generate_address()


@pytest.fixture
def borrower_broker():
    return boa.env.generate_address()


@pytest.fixture
def borrower_broker_fee(borrower_broker):
    return Fee.borrower_broker(borrower_broker, upfront_amount=15, settlement_bps=300)


@pytest.fixture
def protocol_fee(p2p_nfts_usdc):
    settlement_fee = 1000
    upfront_fee = 11
    p2p_nfts_usdc.set_protocol_fee(upfront_fee, settlement_fee, sender=p2p_nfts_usdc.owner())
    p2p_nfts_usdc.change_protocol_wallet(p2p_nfts_usdc.owner(), sender=p2p_nfts_usdc.owner())
    return Fee.protocol(p2p_nfts_usdc, upfront_fee)


@pytest.fixture
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_usdc, usdc, bayc_key_hash):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=10,
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=2000,
        broker_address=broker,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
        tracing_id=b"offer_bayc".zfill(32),
    )
    return sign_offer(offer, lender_key, p2p_nfts_usdc.address)


@pytest.fixture
def offer_bayc2(now, lender2, lender2_key, bayc, broker, p2p_nfts_usdc, usdc, bayc_key_hash):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=150,
        origination_fee_amount=10,
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=2000,
        broker_address=broker,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender2,
        pro_rata=False,
        size=1,
        tracing_id=b"offer_bayc2".zfill(32),
    )
    return sign_offer(offer, lender2_key, p2p_nfts_usdc.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_usdc, offer_bayc, usdc, borrower, lender, bayc, now, borrower_broker_fee, protocol_fee):
    offer = offer_bayc.offer
    token_id = offer.token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    usdc.approve(p2p_nfts_usdc.address, lender_approval, sender=lender)

    loan_id = p2p_nfts_usdc.create_loan(
        offer_bayc,
        token_id,
        [],
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(offer_bayc),
        offer_tracing_id=offer.tracing_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        fees=[Fee.protocol(p2p_nfts_usdc, principal), Fee.origination(offer), Fee.lender_broker(offer), borrower_broker_fee],
        pro_rata=offer.pro_rata,
        delegate=borrower,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_prorata(
    p2p_nfts_usdc, offer_bayc, usdc, borrower, lender, bayc, now, lender_key, borrower_broker_fee, protocol_fee
):
    offer = Offer(**offer_bayc.offer._asdict() | {"pro_rata": True, "tracing_id": b"offer_prorata".zfill(32)})
    token_id = offer.token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    usdc.approve(p2p_nfts_usdc.address, lender_approval, sender=lender)

    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)
    loan_id = p2p_nfts_usdc.create_loan(
        signed_offer,
        token_id,
        [],
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(signed_offer),
        offer_tracing_id=offer.tracing_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        fees=[Fee.protocol(p2p_nfts_usdc, principal), Fee.origination(offer), Fee.lender_broker(offer), borrower_broker_fee],
        pro_rata=offer.pro_rata,
        delegate=borrower,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


def test_replace_loan_reverts_if_loan_invalid(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2):
    for loan in get_loan_mutations(ongoing_loan_bayc):
        print(f"{loan=}")
        with boa.reverts("invalid loan"):
            p2p_nfts_usdc.replace_loan(loan, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_loan_defaulted(p2p_nfts_usdc, ongoing_loan_bayc, now, offer_bayc2):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("loan defaulted"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_loan_already_settled(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, usdc, now):
    loan = ongoing_loan_bayc
    interest = loan.interest
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + interest + borrower_broker_fee

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    with boa.reverts("invalid loan"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_not_signed_by_lender(p2p_nfts_usdc, borrower_key, ongoing_loan_bayc, offer_bayc2):
    signed_offer = sign_offer(offer_bayc2.offer, borrower_key, p2p_nfts_usdc.address)

    with boa.reverts("offer not signed by lender"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_has_invalid_signature(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, lender_key):
    offer = offer_bayc2.offer
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    invalid_offers = [
        replace_namedtuple_field(offer, principal=offer.principal + 1),
        replace_namedtuple_field(offer, interest=offer.interest + 1),
        replace_namedtuple_field(offer, payment_token=boa.env.generate_address("random")),
        replace_namedtuple_field(offer, duration=offer.duration + 1),
        replace_namedtuple_field(offer, origination_fee_amount=offer.origination_fee_amount + 1),
        replace_namedtuple_field(offer, broker_upfront_fee_amount=offer.broker_upfront_fee_amount + 1),
        replace_namedtuple_field(offer, broker_settlement_fee_bps=offer.broker_settlement_fee_bps + 1),
        replace_namedtuple_field(offer, broker_address=boa.env.generate_address("random")),
        replace_namedtuple_field(offer, collection_key_hash=b"1" * 32),
        replace_namedtuple_field(offer, token_id=offer.token_id + 1),
        replace_namedtuple_field(offer, expiration=offer.expiration + 1),
        replace_namedtuple_field(offer, lender=boa.env.generate_address("random")),
        replace_namedtuple_field(offer, pro_rata=not offer.pro_rata),
        replace_namedtuple_field(offer, size=offer.size + 1),
    ]

    for invalid_offer in invalid_offers:
        print(f"{invalid_offer=}")
        with boa.reverts("offer not signed by lender"):
            signed_offer = SignedOffer(invalid_offer, signed_offer.signature)
            p2p_nfts_usdc.replace_loan(
                ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower
            )


def test_replace_loan_reverts_if_offer_expired(
    p2p_nfts_usdc, now, lender, lender_key, bayc, ongoing_loan_bayc, usdc, bayc_key_hash
):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("offer expired"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_payment_token_invalid(
    p2p_nfts_usdc, ongoing_loan_bayc, now, lender, lender_key, bayc, bayc_key_hash
):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=boa.env.generate_address("random"),
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("invalid payment token"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_collateral_not_whitelisted(
    p2p_nfts_usdc, p2p_control, ongoing_loan_bayc, offer_bayc2, bayc, bayc_key_hash
):
    p2p_control.change_collections_contracts([(bayc_key_hash, ZERO_ADDRESS)], sender=p2p_nfts_usdc.owner())

    with boa.reverts("collateral not whitelisted"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_token_id_below_offer_range(
    p2p_nfts_usdc, now, ongoing_loan_bayc, lender, lender_key, bayc, usdc, bayc_key_hash
):
    token_id = ongoing_loan_bayc.collateral_token_id
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        offer_type=OfferType.COLLECTION,
        token_range_min=token_id + 1,
        token_range_max=token_id + 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("tokenid below offer range"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_token_id_above_offer_range(
    p2p_nfts_usdc, now, ongoing_loan_bayc, lender, lender_key, bayc, usdc, bayc_key_hash
):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        offer_type=OfferType.COLLECTION,
        token_range_min=token_id - 1,
        token_range_max=token_id - 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("tokenid above offer range"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_token_id_not_in_list(
    p2p_nfts_usdc, now, ongoing_loan_bayc, lender, lender_key, bayc, usdc, bayc_key_hash
):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        offer_type=OfferType.TOKEN,
        token_id=token_id - 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("token id not in offer"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_is_revoked(p2p_nfts_usdc, borrower, now, ongoing_loan_bayc, offer_bayc2):
    p2p_nfts_usdc.revoke_offer(offer_bayc2, sender=offer_bayc2.offer.lender)

    with boa.reverts("offer revoked"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_exceeds_count(
    p2p_nfts_usdc, ongoing_loan_bayc, now, lender, lender_key, bayc, usdc, bayc_key_hash
):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        offer_type=OfferType.COLLECTION,
        token_range_min=token_id,
        token_range_max=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=0,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("offer fully utilized"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_origination_fee_exceeds_principal(
    p2p_nfts_usdc, ongoing_loan_bayc, now, lender, lender_key, bayc, usdc, bayc_key_hash
):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=1001,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("origination fee gt principal"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_broker_fee_without_address(
    p2p_nfts_usdc, ongoing_loan_bayc, now, lender, lender_key, bayc, usdc, bayc_key_hash
):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=100,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    with boa.reverts("broker fee without address"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_collateral_contract_mismatch(
    p2p_nfts_usdc, ongoing_loan_bayc, now, lender, lender_key, usdc, bayc_key_hash, p2p_control
):
    token_id = 1
    principal = 1000
    dummy_contract = boa.env.generate_address("random")
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    p2p_control.change_collections_contracts([(bayc_key_hash, dummy_contract)], sender=p2p_nfts_usdc.owner())

    with boa.reverts("collateral contract mismatch"):
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, signed_offer, [], 0, 0, ZERO_ADDRESS, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_lender_funds_not_approved(
    p2p_nfts_usdc, borrower, now, lender, lender_key, bayc, usdc, bayc_key_hash
):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)

    with boa.reverts():
        p2p_nfts_usdc.create_loan(signed_offer, token_id, [], ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_replace_loan_reverts_if_funds_not_sent(p2p_nfts_usdc, ongoing_loan_bayc, usdc, offer_bayc2):
    offer = offer_bayc2.offer
    new_lender = offer.lender
    borrower = ongoing_loan_bayc.borrower
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest - (offer.principal - offer.origination_fee_amount)
    usdc.approve(p2p_nfts_usdc.address, principal, sender=new_lender)

    with boa.reverts():
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle - 1, sender=borrower)
        p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)


def test_replace_loan(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, now, bayc, usdc):
    offer = offer_bayc2.offer
    lender = offer.lender
    borrower = ongoing_loan_bayc.borrower
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    loan_id = p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(offer_bayc2),
        offer_tracing_id=offer.tracing_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=ongoing_loan_bayc.borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=ongoing_loan_bayc.collateral_token_id,
        fees=[
            Fee.protocol(p2p_nfts_usdc, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            Fee.borrower_broker(ZERO_ADDRESS),
        ],
        pro_rata=offer.pro_rata,
        delegate=ongoing_loan_bayc.borrower,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)


def test_replace_loan_logs_event(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, now, bayc, usdc):
    token_id = 1
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    protocol_fee_amount = ongoing_loan_bayc.get_protocol_fee().settlement_bps * ongoing_loan_bayc.interest // 10000
    broker_fee_amount = ongoing_loan_bayc.get_lender_broker_fee().settlement_bps * ongoing_loan_bayc.interest // 10000
    borrower_broker_fee_amount = (
        ongoing_loan_bayc.get_borrower_broker_fee().settlement_bps * ongoing_loan_bayc.interest // 10000
    )
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    loan_id = p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    event = get_last_event(p2p_nfts_usdc, "LoanReplaced")
    assert event.id == loan_id
    assert event.offer_id == compute_signed_offer_id(offer_bayc2)
    assert event.offer_tracing_id == offer.tracing_id
    assert event.amount == offer.principal
    assert event.interest == offer.interest
    assert event.payment_token == offer.payment_token
    assert event.maturity == now + offer.duration
    assert event.start_time == now
    assert event.borrower == ongoing_loan_bayc.borrower
    assert event.lender == lender
    assert event.collateral_contract == bayc.address
    assert event.collateral_token_id == token_id
    assert event.pro_rata == offer.pro_rata
    assert event.original_loan_id == ongoing_loan_bayc.id
    assert event.paid_principal == ongoing_loan_bayc.amount
    assert event.paid_interest == ongoing_loan_bayc.interest
    assert event.paid_settlement_fees == [
        FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_usdc.protocol_wallet()),
        FeeAmount(FeeType.LENDER_BROKER, broker_fee_amount, offer.broker_address),
        FeeAmount(FeeType.BORROWER_BROKER, borrower_broker_fee_amount, ongoing_loan_bayc.get_borrower_broker_fee().wallet),
    ]
    assert event.fees == [
        Fee.protocol(p2p_nfts_usdc, principal),
        Fee.origination(offer),
        Fee.lender_broker(offer),
        Fee.borrower_broker(ZERO_ADDRESS),
    ]


def test_replace_loan_decreases_offer_count(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, now, bayc, usdc):
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    offer_count_before = p2p_nfts_usdc.offer_count(ongoing_loan_bayc.offer_tracing_id)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert p2p_nfts_usdc.offer_count(ongoing_loan_bayc.offer_tracing_id) == offer_count_before - 1


def test_replace_loan_keeps_delegation(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, bayc, delegation_registry, usdc):
    token_id = 1
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    delegate = ongoing_loan_bayc.borrower
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    assert delegation_registry.checkDelegateForERC721(delegate, p2p_nfts_usdc.address, bayc.address, token_id, b"")

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert delegation_registry.checkDelegateForERC721(delegate, p2p_nfts_usdc.address, bayc.address, token_id, b"")


def test_replace_loan_keeps_collateral_to_escrow(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, bayc, usdc):
    token_id = 1
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    assert bayc.ownerOf(token_id) == p2p_nfts_usdc.address

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert bayc.ownerOf(token_id) == p2p_nfts_usdc.address


def test_replace_loan_transfers_principal_to_borrower(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, usdc, now):
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer.lender
    principal = offer.principal
    borrower_broker_fee = ongoing_loan_bayc.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest + borrower_broker_fee
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=new_lender
    )

    protocol_upfront_fee_amount = p2p_nfts_usdc.protocol_upfront_fee() * offer.principal // 10000
    upfront_fees = offer.origination_fee_amount + protocol_upfront_fee_amount + offer.broker_upfront_fee_amount
    initial_borrower_balance = usdc.balanceOf(borrower)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert (
        usdc.balanceOf(borrower)
        == initial_borrower_balance - amount_to_settle + principal - upfront_fees + offer.broker_upfront_fee_amount
    )


def test_replace_loan_transfers_origination_fee_to_lender(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, usdc):
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer.lender
    principal = offer.principal
    origination_fee = offer.origination_fee_amount
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest

    initial_lender_balance = usdc.balanceOf(new_lender)
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=new_lender
    )

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert usdc.balanceOf(new_lender) == initial_lender_balance - principal + origination_fee - offer.broker_upfront_fee_amount


def test_replace_loan_updates_offer_usage_count(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, usdc):
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    principal = offer.principal

    assert p2p_nfts_usdc.offer_count(offer.tracing_id) == 0

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert p2p_nfts_usdc.offer_count(offer.tracing_id) == 1


def test_replace_loan_pays_lender(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, usdc):
    loan = ongoing_loan_bayc
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = ongoing_loan_bayc.lender
    new_lender = offer.lender
    principal = offer.principal
    interest = loan.interest
    protocol_fee_amount = interest * ongoing_loan_bayc.get_protocol_fee().settlement_bps // 10000
    lender_fee_amount = interest * ongoing_loan_bayc.get_lender_broker_fee().settlement_bps // 10000
    broker_fee_amount = interest * ongoing_loan_bayc.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest + broker_fee_amount
    amount_to_receive = loan.amount + interest - protocol_fee_amount - lender_fee_amount

    initial_lender_balance = usdc.balanceOf(lender)

    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=new_lender
    )

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert usdc.balanceOf(loan.lender) == initial_lender_balance + amount_to_receive


def test_replace_loan_pays_borrower_if_amount_to_settle_negative(
    p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc, usdc, lender_key, now
):
    loan = ongoing_loan_bayc
    offer = Offer(
        **offer_bayc.offer._asdict()
        | {
            "principal": loan.amount * 2,
            "tracing_id": b"random".zfill(32),
        }
    )
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer.lender
    principal = offer.principal
    protocol_upfront_fee_amount = offer.principal * p2p_nfts_usdc.protocol_upfront_fee() // 10000
    upfront_fees = offer.origination_fee_amount + protocol_upfront_fee_amount
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = (
        ongoing_loan_bayc.amount + ongoing_loan_bayc.interest + borrower_broker_fee - (offer.principal - upfront_fees)
    )

    initial_borrower_balance = usdc.balanceOf(borrower)

    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=new_lender
    )

    p2p_nfts_usdc.replace_loan(
        ongoing_loan_bayc, sign_offer(offer, lender_key, p2p_nfts_usdc.address), [], 0, 0, ZERO_ADDRESS, sender=borrower
    )

    assert amount_to_settle < 0
    assert usdc.balanceOf(loan.borrower) == initial_borrower_balance - amount_to_settle


def test_replace_loan_pays_broker_fees(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, usdc, now):
    loan = ongoing_loan_bayc
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer_bayc2.offer.lender
    new_principal = offer_bayc2.offer.principal
    interest = loan.interest
    broker_fee_amount = interest * ongoing_loan_bayc.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest + borrower_broker_fee
    broker_address = ongoing_loan_bayc.get_lender_broker_fee().wallet
    initial_broker_balance = usdc.balanceOf(broker_address)

    usdc.approve(
        p2p_nfts_usdc.address,
        new_principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount,
        sender=new_lender,
    )

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert (
        usdc.balanceOf(broker_address)
        == initial_broker_balance + broker_fee_amount + offer_bayc2.offer.broker_upfront_fee_amount
    )


def test_replace_loan_pays_protocol_fees(p2p_nfts_usdc, ongoing_loan_bayc, usdc, offer_bayc2):
    loan = ongoing_loan_bayc
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer_bayc2.offer.lender
    new_principal = offer_bayc2.offer.principal
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    initial_protocol_wallet_balance = usdc.balanceOf(p2p_nfts_usdc.protocol_wallet())

    usdc.approve(
        p2p_nfts_usdc.address,
        new_principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount,
        sender=new_lender,
    )

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    protocol_upfront_fee_amount = ongoing_loan_bayc.amount * p2p_nfts_usdc.protocol_upfront_fee() // 10000
    assert (
        usdc.balanceOf(p2p_nfts_usdc.protocol_wallet())
        == initial_protocol_wallet_balance + protocol_fee_amount + protocol_upfront_fee_amount
    )


def test_replace_loan_transfer_failures_keeps_pending_transfer(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, usdc):
    loan = ongoing_loan_bayc
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = ongoing_loan_bayc.lender
    new_lender = offer.lender
    principal = offer.principal
    interest = loan.interest
    protocol_fee_amount = interest * ongoing_loan_bayc.get_protocol_fee().settlement_bps // 10000
    lender_fee_amount = interest * ongoing_loan_bayc.get_lender_broker_fee().settlement_bps // 10000
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    amount_to_receive = loan.amount + interest - protocol_fee_amount - lender_fee_amount

    initial_lender_balance = usdc.balanceOf(lender)

    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=new_lender
    )

    usdc.blacklist(lender, True)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert usdc.balanceOf(loan.lender) == initial_lender_balance

    assert p2p_nfts_usdc.pending_transfers(loan.lender) == amount_to_receive

    usdc.blacklist(lender, False)
    p2p_nfts_usdc.claim_pending_transfers(sender=loan.lender)

    assert p2p_nfts_usdc.pending_transfers(loan.lender) == 0
    assert usdc.balanceOf(loan.lender) == initial_lender_balance + amount_to_receive


def test_replace_loan_prorata_reverts_if_funds_not_approved(p2p_nfts_usdc, ongoing_loan_prorata, usdc):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    amount_to_settle = amount + interest

    boa.env.time_travel(seconds=actual_duration)
    with boa.reverts():
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle - 1, sender=loan.borrower)
        p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)


def test_replace_loan_prorata_logs_event(p2p_nfts_usdc, ongoing_loan_prorata, usdc, now, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = amount + interest

    usdc.approve(
        p2p_nfts_usdc.address,
        new_principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount,
        sender=new_lender,
    )

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    loan_id = p2p_nfts_usdc.replace_loan(loan, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    event = get_last_event(p2p_nfts_usdc, "LoanReplaced")
    assert event.id == loan_id
    assert event.amount == offer.principal
    assert event.interest == offer.interest
    assert event.payment_token == offer.payment_token
    assert event.maturity == now + actual_duration + offer.duration
    assert event.start_time == now + actual_duration
    assert event.borrower == loan.borrower
    assert event.lender == new_lender
    assert event.collateral_contract == loan.collateral_contract
    assert event.collateral_token_id == loan.collateral_token_id
    assert event.pro_rata == offer.pro_rata
    assert event.original_loan_id == loan.id
    assert event.paid_principal == loan.amount
    assert event.paid_interest == interest
    assert event.paid_settlement_fees == [
        FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_usdc.protocol_wallet()),
        FeeAmount(FeeType.LENDER_BROKER, broker_fee_amount, offer.broker_address),
        FeeAmount(FeeType.BORROWER_BROKER, borrower_broker_fee_amount, loan.get_borrower_broker_fee().wallet),
    ]
    assert event.fees == [
        Fee.protocol(p2p_nfts_usdc, new_principal),
        Fee.origination(offer),
        Fee.lender_broker(offer),
        Fee.borrower_broker(ZERO_ADDRESS),
    ]


def test_replace_loan_prorata_pays_lender(p2p_nfts_usdc, ongoing_loan_prorata, usdc, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = amount + interest + borrower_broker_fee_amount
    amount_to_receive = amount + interest - protocol_fee_amount - broker_fee_amount
    initial_lender_balance = usdc.balanceOf(loan.lender)

    usdc.approve(
        p2p_nfts_usdc.address,
        new_principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount,
        sender=new_lender,
    )

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(loan, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert usdc.balanceOf(loan.lender) == initial_lender_balance + amount_to_receive


def test_replace_loan_prorata_pays_broker_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    amount_to_settle = amount + interest
    broker_address = loan.get_lender_broker_fee().wallet
    initial_broker_balance = usdc.balanceOf(broker_address)

    usdc.approve(
        p2p_nfts_usdc.address,
        new_principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount,
        sender=new_lender,
    )

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(loan, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    assert usdc.balanceOf(broker_address) == initial_broker_balance + broker_fee_amount + offer.broker_upfront_fee_amount


def test_replace_loan_prorata_pays_protocol_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    amount_to_settle = amount + interest
    initial_protocol_wallet_balance = usdc.balanceOf(p2p_nfts_usdc.protocol_wallet())

    usdc.approve(
        p2p_nfts_usdc.address,
        new_principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount,
        sender=new_lender,
    )

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(loan, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    protocol_upfront_fee_amount = p2p_nfts_usdc.protocol_upfront_fee() * amount // 10000
    assert (
        usdc.balanceOf(p2p_nfts_usdc.protocol_wallet())
        == initial_protocol_wallet_balance + protocol_fee_amount + protocol_upfront_fee_amount
    )


def test_replace_loan_for_token_offer_revokes_offer(p2p_nfts_usdc, ongoing_loan_bayc, offer_bayc2, now, bayc, usdc):
    offer = offer_bayc2.offer
    lender = offer.lender
    borrower = ongoing_loan_bayc.borrower
    principal = offer.principal
    offer_id = compute_signed_offer_id(offer_bayc2)
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    usdc.approve(
        p2p_nfts_usdc.address, principal - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=borrower)
    p2p_nfts_usdc.replace_loan(ongoing_loan_bayc, offer_bayc2, [], 0, 0, ZERO_ADDRESS, sender=borrower)

    event = get_last_event(p2p_nfts_usdc, "OfferRevoked")
    assert event.offer_id == offer_id
    assert event.lender == offer.lender
    assert event.collection_key_hash == offer.collection_key_hash
    assert event.offer_type == OfferType.TOKEN

    assert p2p_nfts_usdc.revoked_offers(offer_id)


@pytest.mark.slow
@pytest.mark.parametrize("pro_rata", [True, False])
@pytest.mark.parametrize("same_lender", [True, False])
@pytest.mark.parametrize("principal_loan1", [100000, 200000])
@pytest.mark.parametrize("principal_loan2", [100000, 200000])
@pytest.mark.parametrize("protocol_upfront_fee", [0, 3])
@pytest.mark.parametrize("protocol_settlement_fee", [0, 100])
@pytest.mark.parametrize("borrower_broker_upfront_fee", [0, 5])
@pytest.mark.parametrize("borrower_broker_settlement_fee", [0, 200])
@pytest.mark.parametrize("origination_fee", [0, 10])
@pytest.mark.parametrize("lender_broker_upfront_fee", [0, 7])
@pytest.mark.parametrize("lender_broker_settlement_fee", [0, 300])
def test_replace_loan_settles_amounts(  # noqa: PLR0914
    p2p_nfts_usdc,
    offer_bayc,
    bayc,
    usdc,
    borrower,
    lender,
    lender_key,
    lender2,
    lender2_key,
    now,
    pro_rata,
    same_lender,
    principal_loan1,
    principal_loan2,
    protocol_upfront_fee,
    protocol_settlement_fee,
    borrower_broker_upfront_fee,
    borrower_broker_settlement_fee,
    origination_fee,
    lender_broker_upfront_fee,
    lender_broker_settlement_fee,
):
    p2p_nfts_usdc.set_protocol_fee(protocol_upfront_fee, protocol_settlement_fee, sender=p2p_nfts_usdc.owner())
    borrower_broker = (
        boa.env.generate_address("borrower_broker")
        if borrower_broker_upfront_fee or borrower_broker_settlement_fee
        else ZERO_ADDRESS
    )
    offer = replace_namedtuple_field(
        offer_bayc.offer,
        principal=principal_loan1,
        interest=principal_loan1 // 10,
        pro_rata=pro_rata,
        lender=lender,
        origination_fee_amount=origination_fee,
        broker_upfront_fee_amount=lender_broker_upfront_fee,
        broker_settlement_fee_bps=lender_broker_settlement_fee,
        tracing_id=b"offer1".zfill(32),
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)
    token_id = offer.token_id
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    usdc.approve(
        p2p_nfts_usdc.address, principal_loan1 - offer.origination_fee_amount + offer.broker_upfront_fee_amount, sender=lender
    )

    loan_id = p2p_nfts_usdc.create_loan(
        signed_offer,
        token_id,
        [],
        borrower,
        borrower_broker_upfront_fee,
        borrower_broker_settlement_fee,
        borrower_broker,
        sender=borrower,
    )

    loan1 = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(signed_offer),
        offer_tracing_id=offer.tracing_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        fees=[
            Fee.protocol(p2p_nfts_usdc, offer.principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            Fee.borrower_broker(borrower_broker, borrower_broker_upfront_fee, borrower_broker_settlement_fee),
        ],
        pro_rata=offer.pro_rata,
        delegate=borrower,
    )
    assert compute_loan_hash(loan1) == p2p_nfts_usdc.loans(loan_id)

    loan_duration = loan1.maturity - loan1.start_time
    actual_duration = loan_duration * 2 // 3
    interest = (loan1.interest * actual_duration // loan_duration) if offer.pro_rata else loan1.interest
    protocol_fee_amount = interest * loan1.get_protocol_fee().settlement_bps // 10000
    broker_fee_amount = interest * loan1.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan1.get_borrower_broker_fee().settlement_bps // 10000

    lender2, key2 = (lender, lender_key) if same_lender else (lender2, lender2_key)
    offer2 = replace_namedtuple_field(
        offer_bayc.offer,
        principal=principal_loan2,
        interest=principal_loan2 // 10,
        lender=lender2,
        origination_fee_amount=origination_fee,
        broker_upfront_fee_amount=lender_broker_upfront_fee,
        broker_settlement_fee_bps=lender_broker_settlement_fee,
        expiration=offer.expiration + actual_duration,
        tracing_id=b"offer2".zfill(32),
    )
    signed_offer2 = sign_offer(offer2, key2, p2p_nfts_usdc.address)

    protocol_upfront_fee_amount = protocol_upfront_fee * offer2.principal // 10000
    total_upfront_fees = (
        offer2.origination_fee_amount
        + protocol_upfront_fee_amount
        + offer2.broker_upfront_fee_amount
        + borrower_broker_upfront_fee
    )

    borrower_delta = (
        offer2.principal
        - loan1.amount
        - borrower_broker_fee_amount
        - total_upfront_fees
        - interest
        + offer2.broker_upfront_fee_amount
    )
    current_lender_delta = loan1.amount + interest - protocol_fee_amount - broker_fee_amount
    new_lender_delta = offer2.origination_fee_amount - offer2.principal - offer2.broker_upfront_fee_amount

    print(f"{borrower=}, {lender=}, {lender2=}")
    print(f"{loan1.amount=}, {loan1.interest=}")
    print(f"{loan1.fees=}")
    print(f"{offer2.principal=}, {offer2.origination_fee_amount=}")
    print(f"{actual_duration=}, {interest=}, {protocol_fee_amount=}, {broker_fee_amount=} {borrower_broker_fee_amount=}")
    print(f"{borrower_delta=}, {current_lender_delta=}, {new_lender_delta=}")

    if lender != lender2:
        usdc.approve(p2p_nfts_usdc.address, -new_lender_delta, sender=lender2)
    elif current_lender_delta + new_lender_delta < 0:
        lender_delta = current_lender_delta + new_lender_delta
        usdc.approve(p2p_nfts_usdc.address, -lender_delta, sender=lender)

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, max(0, -borrower_delta), sender=borrower)

    initial_borrower_balance = usdc.balanceOf(borrower)
    initial_lender_balance = usdc.balanceOf(lender)
    initial_lender2_balance = usdc.balanceOf(lender2)

    loan2_id = p2p_nfts_usdc.replace_loan(
        loan1, signed_offer2, [], borrower_broker_upfront_fee, borrower_broker_settlement_fee, borrower_broker, sender=borrower
    )

    loan2 = Loan(
        id=loan2_id,
        offer_id=compute_signed_offer_id(signed_offer2),
        offer_tracing_id=offer2.tracing_id,
        amount=offer2.principal,
        interest=offer2.interest,
        payment_token=offer2.payment_token,
        maturity=now + actual_duration + offer2.duration,
        start_time=now + actual_duration,
        borrower=borrower,
        lender=lender2,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        fees=[
            Fee.protocol(p2p_nfts_usdc, offer2.principal),
            Fee.origination(offer2),
            Fee.lender_broker(offer2),
            Fee.borrower_broker(borrower_broker, borrower_broker_upfront_fee, borrower_broker_settlement_fee),
        ],
        pro_rata=offer2.pro_rata,
        delegate=borrower,
    )
    assert compute_loan_hash(loan2) == p2p_nfts_usdc.loans(loan2_id)

    assert usdc.balanceOf(borrower) == initial_borrower_balance + borrower_delta
    if lender != lender2:
        assert usdc.balanceOf(lender) == initial_lender_balance + current_lender_delta
        assert usdc.balanceOf(lender2) == initial_lender2_balance + new_lender_delta
    else:
        assert usdc.balanceOf(lender) == initial_lender_balance + new_lender_delta + current_lender_delta

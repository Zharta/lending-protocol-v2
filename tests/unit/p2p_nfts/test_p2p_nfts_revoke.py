import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import ZERO_ADDRESS, Offer, compute_signed_offer_id, get_last_event, sign_offer


@pytest.fixture
def p2p_nfts_proxy(p2p_nfts_eth, p2p_lending_nfts_proxy_contract_def):
    return p2p_lending_nfts_proxy_contract_def.deploy(p2p_nfts_eth.address)


def test_revoke_offer_reverts_if_sender_is_not_lender(p2p_nfts_eth, borrower, now, lender, lender_key, p2p_nfts_proxy):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("not lender"):
        p2p_nfts_eth.revoke_offer(signed_offer, sender=borrower)

    p2p_nfts_eth.set_proxy_authorization(p2p_nfts_proxy, True, sender=p2p_nfts_eth.owner())
    with boa.reverts("not lender"):
        p2p_nfts_proxy.revoke_offer(signed_offer, sender=borrower)


def test_revoke_offer_reverts_if_proxy_not_auth(p2p_nfts_eth, borrower, now, lender, lender_key, p2p_nfts_proxy):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.set_proxy_authorization(p2p_nfts_proxy, False, sender=p2p_nfts_eth.owner())
    with boa.reverts("not lender"):
        p2p_nfts_proxy.revoke_offer(signed_offer, sender=lender)


def test_revoke_offer_reverts_if_offer_expired(p2p_nfts_eth, borrower, now, lender, lender_key):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("offer expired"):
        p2p_nfts_eth.revoke_offer(signed_offer, sender=lender)


def test_revoke_offer_reverts_if_offer_not_signed_by_lender(p2p_nfts_eth, borrower, now, lender, borrower_key):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, borrower_key, p2p_nfts_eth.address)

    with boa.reverts("offer not signed by lender"):
        p2p_nfts_eth.revoke_offer(signed_offer, sender=lender)


def test_revoke_offer_reverts_if_offer_already_revoked(p2p_nfts_eth, borrower, now, lender, lender_key):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.revoke_offer(signed_offer, sender=lender)

    with boa.reverts("offer already revoked"):
        p2p_nfts_eth.revoke_offer(signed_offer, sender=lender)


def test_revoke_offer(p2p_nfts_eth, borrower, now, lender, lender_key):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.revoke_offer(signed_offer, sender=lender)

    assert p2p_nfts_eth.revoked_offers(compute_signed_offer_id(signed_offer))


def test_revoke_offer_logs_event(p2p_nfts_eth, borrower, now, lender, lender_key):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.revoke_offer(signed_offer, sender=lender)

    event = get_last_event(p2p_nfts_eth, "OfferRevoked")
    assert event.offer_id == compute_signed_offer_id(signed_offer)
    assert event.lender == lender
    assert event.collateral_contract == ZERO_ADDRESS
    assert event.collateral_min_token_id == 1
    assert event.collateral_max_token_id == 1


def test_revoke_offer_works_with_proxy(p2p_nfts_eth, borrower, now, lender, lender_key, p2p_nfts_proxy):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.set_proxy_authorization(p2p_nfts_proxy, True, sender=p2p_nfts_eth.owner())
    p2p_nfts_proxy.revoke_offer(signed_offer, sender=lender)

    assert p2p_nfts_eth.revoked_offers(compute_signed_offer_id(signed_offer))

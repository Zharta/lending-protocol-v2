from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import ZERO_ADDRESS, BrokerLock, CollateralStatus, WhitelistRecord, deploy_reverts, get_last_event

FOREVER = 2**256 - 1


def test_initial_state(
    p2p_nfts_eth,
    p2p_nfts_usdc,
    p2p_control,
    weth,
    usdc,
    delegation_registry,
    cryptopunks,
    owner,
    max_protocol_fee
):
    assert p2p_nfts_eth.owner() == owner
    assert p2p_nfts_eth.payment_token() == ZERO_ADDRESS
    assert p2p_nfts_eth.max_protocol_settlement_fee() == max_protocol_fee
    assert p2p_nfts_eth.delegation_registry() == delegation_registry.address
    assert p2p_nfts_eth.weth9() == weth.address
    assert p2p_nfts_eth.cryptopunks() == cryptopunks.address
    assert p2p_nfts_eth.controller() == p2p_control.address

    assert p2p_nfts_usdc.owner() == owner
    assert p2p_nfts_usdc.payment_token() == usdc.address
    assert p2p_nfts_usdc.max_protocol_settlement_fee() == max_protocol_fee
    assert p2p_nfts_usdc.delegation_registry() == delegation_registry.address
    assert p2p_nfts_usdc.weth9() == weth.address
    assert p2p_nfts_usdc.cryptopunks() == cryptopunks.address
    assert p2p_nfts_usdc.controller() == p2p_control.address


def test_set_protocol_fee_reverts_if_not_owner(p2p_nfts_eth):
    with boa.reverts("not owner"):
        p2p_nfts_eth.set_protocol_fee(1, 1, sender=boa.env.generate_address("random"))


def test_set_protocol_fee_reverts_if_protocol_fee_gt_max(p2p_nfts_eth, owner, max_protocol_fee):
    with boa.reverts("protocol fee > max fee"):
        p2p_nfts_eth.set_protocol_fee(0, max_protocol_fee + 1, sender=owner)


def test_set_protocol_fee(p2p_nfts_eth, owner, max_protocol_fee):
    upfront_fee = 1
    p2p_nfts_eth.set_protocol_fee(upfront_fee, max_protocol_fee, sender=owner)
    assert p2p_nfts_eth.protocol_upfront_fee() == upfront_fee
    assert p2p_nfts_eth.protocol_settlement_fee() == max_protocol_fee

    p2p_nfts_eth.set_protocol_fee(0, 0, sender=owner)
    assert p2p_nfts_eth.protocol_upfront_fee() == 0
    assert p2p_nfts_eth.protocol_settlement_fee() == 0


def test_set_protocol_fee_logs_event(p2p_nfts_eth, owner):
    old_upfront_fee = p2p_nfts_eth.protocol_upfront_fee()
    old_settlement_fee = p2p_nfts_eth.protocol_settlement_fee()
    new_upfront_fee = old_upfront_fee + 1
    new_settlement_fee = old_settlement_fee + 1

    p2p_nfts_eth.set_protocol_fee(new_upfront_fee, new_settlement_fee, sender=owner)
    event = get_last_event(p2p_nfts_eth, "ProtocolFeeSet")

    assert event.old_upfront_fee == old_upfront_fee
    assert event.old_settlement_fee == old_settlement_fee
    assert event.new_upfront_fee == new_upfront_fee
    assert event.new_settlement_fee == new_settlement_fee


def test_change_protocol_wallet_reverts_if_not_owner(p2p_nfts_eth):
    new_wallet = boa.env.generate_address("new_wallet")
    with boa.reverts("not owner"):
        p2p_nfts_eth.change_protocol_wallet(new_wallet, sender=boa.env.generate_address("random"))


def test_change_protocol_wallet_reverts_if_zero_address(p2p_nfts_eth, owner):
    with boa.reverts("wallet is the zero address"):
        p2p_nfts_eth.change_protocol_wallet(ZERO_ADDRESS, sender=owner)


def test_change_protocol_wallet(p2p_nfts_eth, owner):
    new_wallet = boa.env.generate_address("new_wallet")
    p2p_nfts_eth.change_protocol_wallet(new_wallet, sender=owner)

    assert p2p_nfts_eth.protocol_wallet() == new_wallet


def test_change_protocol_wallet_logs_event(p2p_nfts_eth, owner):
    new_wallet = boa.env.generate_address("new_wallet")
    p2p_nfts_eth.change_protocol_wallet(new_wallet, sender=owner)
    event = get_last_event(p2p_nfts_eth, "ProtocolWalletChanged")

    assert event.old_wallet == ZERO_ADDRESS
    assert event.new_wallet == new_wallet


def test_set_proxy_authorization_reverts_if_not_owner(p2p_nfts_eth):
    proxy = boa.env.generate_address("proxy")
    random = boa.env.generate_address("random")
    with boa.reverts("not owner"):
        p2p_nfts_eth.set_proxy_authorization(proxy, True, sender=random)


def test_set_proxy_authorization(p2p_nfts_eth, owner):
    proxy = boa.env.generate_address("proxy")
    p2p_nfts_eth.set_proxy_authorization(proxy, True, sender=owner)
    assert p2p_nfts_eth.authorized_proxies(proxy) == True

    p2p_nfts_eth.set_proxy_authorization(proxy, False, sender=owner)
    assert p2p_nfts_eth.authorized_proxies(proxy) == False


def test_set_proxy_authorization_logs_event(p2p_nfts_eth, owner):
    proxy = boa.env.generate_address("proxy")
    p2p_nfts_eth.set_proxy_authorization(proxy, True, sender=owner)
    event = get_last_event(p2p_nfts_eth, "ProxyAuthorizationChanged")

    assert event.proxy == proxy
    assert event.value == True


def test_propose_owner_reverts_if_wrong_caller(p2p_nfts_eth):
    new_owner = boa.env.generate_address("new_owner")
    with boa.reverts("not owner"):
        p2p_nfts_eth.propose_owner(new_owner, sender=new_owner)


def test_propose_owner_reverts_if_zero_address(p2p_nfts_eth, owner):
    with boa.reverts("_address is zero"):
        p2p_nfts_eth.propose_owner(ZERO_ADDRESS, sender=owner)


def test_propose_owner(p2p_nfts_eth, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_eth.propose_owner(new_owner, sender=owner)

    assert p2p_nfts_eth.proposed_owner() == new_owner


def test_propose_owner_logs_event(p2p_nfts_eth, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_eth.propose_owner(new_owner, sender=owner)
    event = get_last_event(p2p_nfts_eth, "OwnerProposed")

    assert event.owner == owner
    assert event.proposed_owner == new_owner


def test_claim_ownership_reverts_if_wrong_caller(p2p_nfts_eth, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_eth.propose_owner(new_owner, sender=owner)

    with boa.reverts("not the proposed owner"):
        p2p_nfts_eth.claim_ownership(sender=owner)


def test_claim_ownership(p2p_nfts_eth, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_eth.propose_owner(new_owner, sender=owner)

    p2p_nfts_eth.claim_ownership(sender=new_owner)

    assert p2p_nfts_eth.proposed_owner() == ZERO_ADDRESS
    assert p2p_nfts_eth.owner() == new_owner


def test_claim_ownership_logs_event(p2p_nfts_eth, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_eth.propose_owner(new_owner, sender=owner)

    p2p_nfts_eth.claim_ownership(sender=new_owner)
    event = get_last_event(p2p_nfts_eth, "OwnershipTransferred")

    assert event.old_owner == owner
    assert event.new_owner == new_owner

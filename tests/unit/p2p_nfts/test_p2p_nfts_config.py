import boa
import pytest

from ...conftest_base import ZERO_ADDRESS, get_last_event, WhitelistRecord

FOREVER = 2**256 - 1


@pytest.fixture
def collections():
    return ["0x" + str(i) * 40 for i in range(1, 6)]



def test_initial_state(
    p2p_nfts_usdc,
    weth,
    usdc,
    delegation_registry,
    cryptopunks,
    owner,
):
    assert p2p_nfts_usdc.owner() == owner
    assert p2p_nfts_usdc.payment_token() == usdc.address
    assert p2p_nfts_usdc.delegation_registry() == delegation_registry.address
    assert p2p_nfts_usdc.cryptopunks() == cryptopunks.address
    assert p2p_nfts_usdc.protocol_upfront_fee() == 0
    assert p2p_nfts_usdc.protocol_settlement_fee() == 0
    assert p2p_nfts_usdc.protocol_wallet() == owner


def test_set_protocol_fee_reverts_if_not_owner(p2p_nfts_usdc):
    with boa.reverts("not owner"):
        p2p_nfts_usdc.set_protocol_fee(1, 1, sender=boa.env.generate_address("random"))


def test_set_protocol_fee(p2p_nfts_usdc, owner):
    upfront_fee = 1
    settlement_fee = 1
    p2p_nfts_usdc.set_protocol_fee(upfront_fee, settlement_fee, sender=owner)
    assert p2p_nfts_usdc.protocol_upfront_fee() == upfront_fee
    assert p2p_nfts_usdc.protocol_settlement_fee() == settlement_fee

    p2p_nfts_usdc.set_protocol_fee(0, 0, sender=owner)
    assert p2p_nfts_usdc.protocol_upfront_fee() == 0
    assert p2p_nfts_usdc.protocol_settlement_fee() == 0


def test_set_protocol_fee_logs_event(p2p_nfts_usdc, owner):
    old_upfront_fee = p2p_nfts_usdc.protocol_upfront_fee()
    old_settlement_fee = p2p_nfts_usdc.protocol_settlement_fee()
    new_upfront_fee = old_upfront_fee + 1
    new_settlement_fee = old_settlement_fee + 1

    p2p_nfts_usdc.set_protocol_fee(new_upfront_fee, new_settlement_fee, sender=owner)
    event = get_last_event(p2p_nfts_usdc, "ProtocolFeeSet")

    assert event.old_upfront_fee == old_upfront_fee
    assert event.old_settlement_fee == old_settlement_fee
    assert event.new_upfront_fee == new_upfront_fee
    assert event.new_settlement_fee == new_settlement_fee


def test_change_protocol_wallet_reverts_if_not_owner(p2p_nfts_usdc):
    new_wallet = boa.env.generate_address("new_wallet")
    with boa.reverts("not owner"):
        p2p_nfts_usdc.change_protocol_wallet(new_wallet, sender=boa.env.generate_address("random"))


def test_change_protocol_wallet_reverts_if_zero_address(p2p_nfts_usdc, owner):
    with boa.reverts("wallet is the zero address"):
        p2p_nfts_usdc.change_protocol_wallet(ZERO_ADDRESS, sender=owner)


def test_change_protocol_wallet(p2p_nfts_usdc, owner):
    new_wallet = boa.env.generate_address("new_wallet")
    p2p_nfts_usdc.change_protocol_wallet(new_wallet, sender=owner)

    assert p2p_nfts_usdc.protocol_wallet() == new_wallet


def test_change_protocol_wallet_logs_event(p2p_nfts_usdc, owner):
    new_wallet = boa.env.generate_address("new_wallet")
    p2p_nfts_usdc.change_protocol_wallet(new_wallet, sender=owner)
    event = get_last_event(p2p_nfts_usdc, "ProtocolWalletChanged")

    assert event.old_wallet == owner
    assert event.new_wallet == new_wallet


def test_set_proxy_authorization_reverts_if_not_owner(p2p_nfts_usdc):
    proxy = boa.env.generate_address("proxy")
    random = boa.env.generate_address("random")
    with boa.reverts("not owner"):
        p2p_nfts_usdc.set_proxy_authorization(proxy, True, sender=random)


def test_set_proxy_authorization(p2p_nfts_usdc, owner):
    proxy = boa.env.generate_address("proxy")
    p2p_nfts_usdc.set_proxy_authorization(proxy, True, sender=owner)
    assert p2p_nfts_usdc.authorized_proxies(proxy) is True

    p2p_nfts_usdc.set_proxy_authorization(proxy, False, sender=owner)
    assert p2p_nfts_usdc.authorized_proxies(proxy) is False


def test_set_proxy_authorization_logs_event(p2p_nfts_usdc, owner):
    proxy = boa.env.generate_address("proxy")
    p2p_nfts_usdc.set_proxy_authorization(proxy, True, sender=owner)
    event = get_last_event(p2p_nfts_usdc, "ProxyAuthorizationChanged")

    assert event.proxy == proxy
    assert event.value is True


def test_propose_owner_reverts_if_wrong_caller(p2p_nfts_usdc):
    new_owner = boa.env.generate_address("new_owner")
    with boa.reverts("not owner"):
        p2p_nfts_usdc.propose_owner(new_owner, sender=new_owner)


def test_propose_owner_reverts_if_zero_address(p2p_nfts_usdc, owner):
    with boa.reverts("_address is zero"):
        p2p_nfts_usdc.propose_owner(ZERO_ADDRESS, sender=owner)


def test_propose_owner(p2p_nfts_usdc, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_usdc.propose_owner(new_owner, sender=owner)

    assert p2p_nfts_usdc.proposed_owner() == new_owner


def test_propose_owner_logs_event(p2p_nfts_usdc, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_usdc.propose_owner(new_owner, sender=owner)
    event = get_last_event(p2p_nfts_usdc, "OwnerProposed")

    assert event.owner == owner
    assert event.proposed_owner == new_owner


def test_claim_ownership_reverts_if_wrong_caller(p2p_nfts_usdc, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_usdc.propose_owner(new_owner, sender=owner)

    with boa.reverts("not the proposed owner"):
        p2p_nfts_usdc.claim_ownership(sender=owner)


def test_claim_ownership(p2p_nfts_usdc, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_usdc.propose_owner(new_owner, sender=owner)

    p2p_nfts_usdc.claim_ownership(sender=new_owner)

    assert p2p_nfts_usdc.proposed_owner() == ZERO_ADDRESS
    assert p2p_nfts_usdc.owner() == new_owner


def test_claim_ownership_logs_event(p2p_nfts_usdc, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_nfts_usdc.propose_owner(new_owner, sender=owner)

    p2p_nfts_usdc.claim_ownership(sender=new_owner)
    event = get_last_event(p2p_nfts_usdc, "OwnershipTransferred")

    assert event.old_owner == owner
    assert event.new_owner == new_owner


def test_change_whitelisted_collections_reverts_if_wrong_caller(p2p_nfts_eth):
    with boa.reverts("sender not owner"):
        p2p_nfts_eth.change_whitelisted_collections([], sender=boa.env.generate_address("random"))


def test_change_whitelisted_collections(p2p_nfts_eth, collections, owner):
    whitelist = [WhitelistRecord(c, i % 2 == 0) for i, c in enumerate(collections)]
    p2p_nfts_eth.change_whitelisted_collections(whitelist, sender=owner)

    for c, w in whitelist:
        assert p2p_nfts_eth.whitelisted(c) == w

    whitelist = [WhitelistRecord(c, i % 2 == 1) for i, c in enumerate(collections)]
    p2p_nfts_eth.change_whitelisted_collections(whitelist, sender=owner)

    for c, w in whitelist:
        assert p2p_nfts_eth.whitelisted(c) == w


def test_change_whitelisted_collections_logs_event(p2p_nfts_eth, collections, owner):
    whitelist = [WhitelistRecord(c, i % 2 == 0) for i, c in enumerate(collections)]
    p2p_nfts_eth.change_whitelisted_collections(whitelist, sender=owner)
    event = get_last_event(p2p_nfts_eth, "WhitelistChanged")

    assert event.changed == whitelist


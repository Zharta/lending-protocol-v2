from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import ZERO_ADDRESS, BrokerLock, CollateralStatus, WhitelistRecord, deploy_reverts, get_last_event

FOREVER = 2**256 - 1


@pytest.fixture
def max_lock_expiration():
    return 2 * 86400


@pytest.fixture
def p2p_control(p2p_lending_control_contract_def, cryptopunks, max_lock_expiration):
    return p2p_lending_control_contract_def.deploy(cryptopunks, max_lock_expiration)


@pytest.fixture
def collections():
    return ["0x" + str(i) * 40 for i in range(1, 6)]


@pytest.fixture
def erc721(erc721_contract_def):
    return erc721_contract_def.deploy()


@pytest.fixture
def now():
    return boa.eval("block.timestamp")


def test_initial_state(p2p_control, cryptopunks, max_lock_expiration):
    assert p2p_control.cryptopunks() == cryptopunks.address
    assert p2p_control.max_broker_lock_duration() == max_lock_expiration


def test_propose_owner_reverts_if_wrong_caller(p2p_control):
    new_owner = boa.env.generate_address("new_owner")
    with boa.reverts("not owner"):
        p2p_control.propose_owner(new_owner, sender=new_owner)


def test_propose_owner_reverts_if_zero_address(p2p_control, owner):
    with boa.reverts("address is zero"):
        p2p_control.propose_owner(ZERO_ADDRESS, sender=owner)


def test_propose_owner(p2p_control, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_control.propose_owner(new_owner, sender=owner)

    assert p2p_control.proposed_owner() == new_owner


def test_propose_owner_logs_event(p2p_control, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_control.propose_owner(new_owner, sender=owner)
    event = get_last_event(p2p_control, "OwnerProposed")

    assert event.owner == owner
    assert event.proposed_owner == new_owner


def test_claim_ownership_reverts_if_wrong_caller(p2p_control, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_control.propose_owner(new_owner, sender=owner)

    with boa.reverts("not the proposed owner"):
        p2p_control.claim_ownership(sender=owner)


def test_claim_ownership(p2p_control, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_control.propose_owner(new_owner, sender=owner)

    p2p_control.claim_ownership(sender=new_owner)

    assert p2p_control.proposed_owner() == ZERO_ADDRESS
    assert p2p_control.owner() == new_owner


def test_claim_ownership_logs_event(p2p_control, owner):
    new_owner = boa.env.generate_address("new_owner")
    p2p_control.propose_owner(new_owner, sender=owner)

    p2p_control.claim_ownership(sender=new_owner)
    event = get_last_event(p2p_control, "OwnershipTransferred")

    assert event.old_owner == owner
    assert event.new_owner == new_owner


def test_change_whitelisted_collections_reverts_if_wrong_caller(p2p_control):
    with boa.reverts("sender not owner"):
        p2p_control.change_whitelisted_collections([], sender=boa.env.generate_address("random"))


def test_change_whitelisted_collections(p2p_control, collections, owner):
    whitelist = [WhitelistRecord(c, i % 2 == 0) for i, c in enumerate(collections)]
    p2p_control.change_whitelisted_collections(whitelist, sender=owner)

    for c, w in whitelist:
        assert p2p_control.whitelisted(c) == w

    whitelist = [WhitelistRecord(c, i % 2 == 1) for i, c in enumerate(collections)]
    p2p_control.change_whitelisted_collections(whitelist, sender=owner)

    for c, w in whitelist:
        assert p2p_control.whitelisted(c) == w


def test_change_whitelisted_collections_logs_event(p2p_control, collections, owner):
    whitelist = [WhitelistRecord(c, i % 2 == 0) for i, c in enumerate(collections)]
    p2p_control.change_whitelisted_collections(whitelist, sender=owner)
    event = get_last_event(p2p_control, "WhitelistChanged")

    assert event.changed == whitelist


def test_change_whitelisted_collections_changes_collateral_status(p2p_control, collections, owner):
    token_id = 1
    whitelist = [WhitelistRecord(c, i % 2 == 0) for i, c in enumerate(collections)]
    p2p_control.change_whitelisted_collections(whitelist, sender=owner)

    for c, w in whitelist:
        status = CollateralStatus(*p2p_control.get_collateral_status(c, token_id))
        assert status.whitelisted == w

    whitelist = [WhitelistRecord(c, i % 2 == 1) for i, c in enumerate(collections)]
    p2p_control.change_whitelisted_collections(whitelist, sender=owner)

    for c, w in whitelist:
        status = CollateralStatus(*p2p_control.get_collateral_status(c, token_id))
        assert status.whitelisted == w


def test_add_broker_lock_reverts_if_not_owner_of_collateral(p2p_control, erc721, cryptopunks):
    broker = boa.env.generate_address("broker")
    borrower = boa.env.generate_address("borrower")
    token_id = 1

    erc721.mint(boa.env.generate_address("random"), token_id)
    with boa.reverts("not owner"):
        p2p_control.add_broker_lock(erc721, token_id, broker, 1, sender=borrower)

    with boa.reverts("not owner"):
        p2p_control.add_broker_lock(cryptopunks, token_id, broker, 1, sender=borrower)


def test_add_broker_lock_reverts_if_lock_exists(p2p_control, erc721, now, borrower):
    broker = boa.env.generate_address("broker")
    token_id = 1
    lock_duration = 100

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration, sender=borrower)

    boa.env.time_travel(seconds=lock_duration)

    with boa.reverts("lock exists"):
        p2p_control.add_broker_lock(erc721, token_id, broker, 1, sender=borrower)


def test_add_broker_lock_reverts_if_expiration_too_far(p2p_control, erc721, now, borrower, max_lock_expiration):
    broker = boa.env.generate_address("broker")
    lock_duration = max_lock_expiration + 1
    token_id = 1

    erc721.mint(borrower, token_id)
    with boa.reverts("expiration too far"):
        p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration, sender=borrower)


def test_add_broker_lock_reverts_if_broker_is_zero(p2p_control, erc721, borrower, now):
    token_id = 1

    erc721.mint(borrower, token_id)
    with boa.reverts("broker is zero"):
        p2p_control.add_broker_lock(erc721, token_id, ZERO_ADDRESS, now + 1, sender=borrower)


def test_add_broker_lock(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + 1, sender=borrower)

    lock = BrokerLock(*p2p_control.get_broker_lock(erc721, token_id))
    assert lock.broker == broker
    assert lock.expiration == now + 1


def test_add_broker_lock_with_previous_lock_expired(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1
    lock_duration = 100

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration, sender=borrower)

    boa.env.time_travel(seconds=lock_duration + 1)

    p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration + 2, sender=borrower)


def test_add_broker_lock_logs_event(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + 1, sender=borrower)
    event = get_last_event(p2p_control, "BrokerLockAdded")

    assert event.collateral_address == erc721.address
    assert event.collateral_token_id == token_id
    assert event.broker == broker
    assert event.expiration == now + 1


def test_add_broker_lock_changes_collateral_status(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + 1, sender=borrower)

    status = CollateralStatus.from_tuple(p2p_control.get_collateral_status(erc721.address, token_id))
    assert status.broker_lock.broker == broker
    assert status.broker_lock.expiration == now + 1


def test_remove_broker_lock_reverts_if_not_broker(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1
    lock_duration = 100

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration, sender=borrower)

    with boa.reverts("not broker"):
        p2p_control.remove_broker_lock(erc721, token_id, sender=borrower)


def test_remove_broker_lock(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1
    lock_duration = 100

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration, sender=borrower)

    p2p_control.remove_broker_lock(erc721, token_id, sender=broker)

    lock = BrokerLock(*p2p_control.get_broker_lock(erc721, token_id))
    assert lock.expiration == 0


def test_remove_broker_lock_logs_event(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1
    lock_duration = 100

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration, sender=borrower)

    p2p_control.remove_broker_lock(erc721, token_id, sender=broker)
    event = get_last_event(p2p_control, "BrokerLockRemoved")

    assert event.collateral_address == erc721.address
    assert event.collateral_token_id == token_id


def test_remove_broker_lock_changes_collateral_status(p2p_control, erc721, borrower, now):
    broker = boa.env.generate_address("broker")
    token_id = 1
    lock_duration = 100

    erc721.mint(borrower, token_id)
    p2p_control.add_broker_lock(erc721, token_id, broker, now + lock_duration, sender=borrower)

    p2p_control.remove_broker_lock(erc721, token_id, sender=broker)

    status = CollateralStatus.from_tuple(p2p_control.get_collateral_status(erc721.address, token_id))
    assert status.broker_lock.expiration == 0


def test_set_max_broker_lock_duration_reverts_if_not_owner(p2p_control):
    with boa.reverts("not owner"):
        p2p_control.set_max_broker_lock_duration(1, sender=boa.env.generate_address("random"))


def test_set_max_broker_lock_duration(p2p_control, owner):
    old_duration = p2p_control.max_broker_lock_duration()
    new_duration = old_duration + 1

    p2p_control.set_max_broker_lock_duration(new_duration, sender=owner)

    assert p2p_control.max_broker_lock_duration() == new_duration


def test_set_max_broker_lock_duration_logs_event(p2p_control, owner):
    old_duration = p2p_control.max_broker_lock_duration()
    new_duration = old_duration + 1

    p2p_control.set_max_broker_lock_duration(new_duration, sender=owner)
    event = get_last_event(p2p_control, "MaxBrokerLockDurationChanged")

    assert event.old_duration == old_duration
    assert event.new_duration == new_duration

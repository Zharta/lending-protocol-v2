from textwrap import dedent

import boa
import pytest
from boa.vm.py_evm import register_raw_precompile
from eth_account import Account


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(scope="session", autouse=True)
def boa_env():
    boa.interpret.set_cache_dir(cache_dir=".cache/titanoboa")
    return boa


@pytest.fixture(scope="session")
def accounts(boa_env):
    _accounts = [boa.env.generate_address() for _ in range(10)]
    for account in _accounts:
        boa.env.set_balance(account, 10**21)
    return _accounts


@pytest.fixture(scope="session")
def owner_account():
    return Account.create()


@pytest.fixture(scope="session")
def owner(owner_account, boa_env):
    boa.env.eoa = owner_account.address
    boa.env.set_balance(owner_account.address, 10**21)
    return owner_account.address


@pytest.fixture(scope="session")
def owner_key(owner_account):
    return owner_account.key


@pytest.fixture(scope="session")
def borrower_account():
    return Account.create()


@pytest.fixture(scope="session")
def borrower(borrower_account, boa_env):
    boa.env.set_balance(borrower_account.address, 10**21)
    return borrower_account.address


@pytest.fixture(scope="session")
def borrower_key(borrower_account):
    return borrower_account.key


@pytest.fixture(scope="session")
def lender_account():
    return Account.create()


@pytest.fixture(scope="session")
def lender(lender_account, boa_env):
    boa.env.set_balance(lender_account.address, 10**21)
    return lender_account.address


@pytest.fixture(scope="session")
def lender_key(lender_account):
    return lender_account.key


@pytest.fixture(scope="session")
def lender2_account():
    return Account.create()


@pytest.fixture(scope="session")
def lender2(lender2_account, boa_env):
    boa.env.set_balance(lender2_account.address, 10**21)
    return lender2_account.address


@pytest.fixture(scope="session")
def lender2_key(lender2_account):
    return lender2_account.key


@pytest.fixture(scope="session")
def protocol_wallet(accounts):
    yield accounts[3]


@pytest.fixture(scope="session")
def erc721_contract_def(boa_env):
    return boa.load_partial("contracts/auxiliary/ERC721.vy")


@pytest.fixture(scope="session")
def weth9_contract_def(boa_env):
    return boa.load_partial("contracts/auxiliary/WETH9Mock.vy")


@pytest.fixture(scope="session")
def weth(weth9_contract_def, owner):
    return weth9_contract_def.deploy("Wrapped Ether", "WETH", 18, 10**20)


@pytest.fixture(scope="session")
def cryptopunks_contract_def(boa_env):
    return boa.load_partial("contracts/auxiliary/CryptoPunksMarketMock.vy")


@pytest.fixture(scope="session")
def cryptopunks(cryptopunks_contract_def, owner):
    return cryptopunks_contract_def.deploy()


@pytest.fixture(scope="session")
def delegation_registry_contract_def(boa_env):
    return boa.load_partial("contracts/auxiliary/DelegationRegistryMock.vy")


@pytest.fixture(scope="session")
def p2p_lending_nfts_contract_def(boa_env):
    return boa.load_partial("contracts/P2PLendingNfts.vy")


@pytest.fixture(scope="session")
def p2p_lending_control_contract_def(boa_env):
    return boa.load_partial("contracts/P2PLendingControl.vy")


@pytest.fixture(scope="session")
def p2p_lending_nfts_proxy_contract_def(boa_env):
    return boa.load_partial("tests/stubs/P2PNftsProxy.vy")


@pytest.fixture(scope="module")
def empty_contract_def(boa_env):
    return boa.loads_partial(
        dedent(
            """
        dummy: uint256
     """
        )
    )


@boa.precompile("def debug_bytes32(data: bytes32)")
def debug_bytes32(data: bytes):
    print(f"DEBUG: {data.hex()}")


@pytest.fixture(scope="session")
def debug_precompile(boa_env):
    register_raw_precompile("0x0000000000000000000000000000000000011111", debug_bytes32)
    yield

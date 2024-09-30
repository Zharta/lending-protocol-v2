from hashlib import sha3_256
from textwrap import dedent

import boa
import pytest

from ...conftest_base import CollectionContract


@pytest.fixture(scope="module")
def max_lock_expiration():
    return 2 * 86400


@pytest.fixture
def bayc(erc721_contract_def, owner):
    return erc721_contract_def.deploy()


@pytest.fixture
def usdc(weth9_contract_def, owner):
    return weth9_contract_def.deploy("USDC", "USDC", 9, 10**20)


@pytest.fixture
def delegation_registry(delegation_registry_contract_def, owner):
    return delegation_registry_contract_def.deploy()


@pytest.fixture
def bayc_key_hash():
    return sha3_256(b"bayc").digest()


@pytest.fixture
def punks_key_hash():
    return sha3_256(b"cryptopunks").digest()


@pytest.fixture
def p2p_control(p2p_lending_control_contract_def, owner, cryptopunks, bayc, bayc_key_hash, punks_key_hash):
    p2p_control = p2p_lending_control_contract_def.deploy()
    p2p_control.change_collections_contracts(
        [CollectionContract(punks_key_hash, cryptopunks.address), CollectionContract(bayc_key_hash, bayc.address)]
    )
    return p2p_control


@pytest.fixture
def p2p_nfts_usdc(p2p_lending_nfts_contract_def, usdc, delegation_registry, cryptopunks, owner, p2p_control):
    return p2p_lending_nfts_contract_def.deploy(
        usdc, p2p_control, delegation_registry, cryptopunks, 0, 0, owner, 10000, 10000, 10000, 10000
    )


@pytest.fixture
def now():
    return boa.eval("block.timestamp")


@pytest.fixture
def traits():
    return {
        "openness": [
            "curious",
            "inventive",
            "artistic",
            "wide interests",
            "excitable",
            "unconventional",
            "imaginative",
            "traditional",
            "prefer routine",
            "practical",
        ],
        "conscientiousness": [
            "organized",
            "efficient",
            "dependable",
            "thorough",
            "self-disciplined",
            "careful",
            "lazy",
            "impulsive",
            "careless",
            "easy-going",
        ],
        "extraversion": [
            "outgoing",
            "energetic",
            "assertive",
            "sociable",
            "talkative",
            "enthusiastic",
            "reserved",
            "shy",
            "quiet",
            "solitary",
        ],
        "agreeableness": [
            "friendly",
            "compassionate",
            "cooperative",
            "trusting",
            "helpful",
            "empathetic",
            "critical",
            "uncooperative",
            "suspicious",
            "competitive",
        ],
        "neuroticism": [
            "sensitive",
            "nervous",
            "anxious",
            "moody",
            "easily upset",
            "insecure",
            "stable",
            "calm",
            "confident",
            "resilient",
        ],
    }

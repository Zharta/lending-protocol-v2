import os
import random
from collections import namedtuple
from dataclasses import field
from enum import Enum, IntEnum
from textwrap import dedent
from typing import NamedTuple

import ape
import eth_abi
import requests
import web3
from ape import convert, networks
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak
from hexbytes import HexBytes

from scripts.deployment import DeploymentManager, Environment

ENV = Environment[os.environ.get("ENV", "local")]
CHAIN = os.environ.get("CHAIN", "nochain")

ZERO_ADDRESS = "0x" + "0" * 40
ZERO_BYTES32 = b"\0" * 32

URL_ENV_INFIX = f".{ENV.name}" if ENV != Environment.prod else ""  # noqa: SIM300 Yoda this condition is not
P2P_SERVICE_BASE_URL = f"https://api{URL_ENV_INFIX}.zharta.io/loans-p2p/v1"


class Context(Enum):
    DEPLOYMENT = "deployment"
    CONSOLE = "console"


def inject_poa(w3):
    w3.middleware_onion.inject(web3.middleware.geth_poa_middleware, layer=0)
    return w3


def transfer(w3, wallet, val=10**60):
    b = w3.eth.coinbase
    w3.eth.send_transaction({"from": b, "to": wallet, "value": val})
    print(f"new balance: {w3.eth.get_balance(wallet)}")


def propose_owner(dm, from_wallet, to_wallet):
    contracts = [c for c in dm.context.contracts.values() if hasattr(c.contract, "proposeOwner")]
    dm.owner.set_autosign(True)
    for i, c in enumerate(contracts):
        c.contract.proposeOwner(to_wallet, sender=from_wallet, gas_price=convert("28 gwei", int))
        print(f"Signed contract {i + 1} out of {len(contracts)}")


def claim_ownership(dm, wallet):
    contracts = [c for c in dm.context.contracts.values() if hasattr(c.contract, "claimOwnership")]
    dm.owner.set_autosign(True)
    for i, c in enumerate(contracts):
        c.contract.claimOwnership(sender=wallet, gas_price=convert("28 gwei", int))
        print(f"Signed contract {i + 1} out of {len(contracts)}")


class FeeType(IntEnum):
    PROTOCOL = 1 << 0
    ORIGINATION = 1 << 1
    LENDER_BROKER = 1 << 2
    BORROWER_BROKER = 1 << 3


class OfferType(IntEnum):
    TOKEN = 1 << 0
    COLLECTION = 1 << 1
    TRAIT = 1 << 2


class Offer(NamedTuple):
    principal: int = 0
    interest: int = 0
    payment_token: str = ZERO_ADDRESS
    duration: int = 0
    origination_fee_amount: int = 0
    broker_upfront_fee_amount: int = 0
    broker_settlement_fee_bps: int = 0
    broker_address: str = ZERO_ADDRESS
    offer_type: OfferType = OfferType.TOKEN
    token_id: int = 0
    token_range_min: int = 0
    token_range_max: int = 2**256 - 1
    collection_key_hash: str = ZERO_BYTES32
    trait_hash: str = ZERO_BYTES32
    expiration: int = 0
    lender: str = ZERO_ADDRESS
    pro_rata: bool = False
    size: int = 1
    tracing_id: bytes = random.randbytes(32)


Signature = namedtuple("Signature", ["v", "r", "s"], defaults=[0, ZERO_BYTES32, ZERO_BYTES32])


SignedOffer = namedtuple("SignedOffer", ["offer", "signature"], defaults=[Offer(), Signature()])


class Fee(NamedTuple):
    type: FeeType = FeeType.PROTOCOL
    upfront_amount: int = 0
    settlement_bps: int = 0
    wallet: str = ZERO_ADDRESS

    @classmethod
    def protocol(cls, contract, principal):
        return cls(
            FeeType.PROTOCOL,
            int(contract.protocol_upfront_fee() * principal // 10000),
            contract.protocol_settlement_fee(),
            contract.protocol_wallet(),
        )

    @classmethod
    def origination(cls, offer):
        return cls(FeeType.ORIGINATION, offer.origination_fee_amount, 0, offer.lender)

    @classmethod
    def lender_broker(cls, offer):
        return cls(
            FeeType.LENDER_BROKER, offer.broker_upfront_fee_amount, offer.broker_settlement_fee_bps, offer.broker_address
        )

    @classmethod
    def borrower_broker(cls, broker, upfront_amount=0, settlement_bps=0):
        return cls(FeeType.BORROWER_BROKER, upfront_amount, settlement_bps, broker)


FeeAmount = namedtuple("FeeAmount", ["type", "amount", "wallet"], defaults=[0, 0, ZERO_ADDRESS])


class Loan(NamedTuple):
    id: bytes = ZERO_BYTES32
    offer_id: bytes = ZERO_BYTES32
    offer_tracing_id: bytes = ZERO_BYTES32
    amount: int = 0
    interest: int = 0
    payment_token: str = ZERO_ADDRESS
    maturity: int = 0
    start_time: int = 0
    borrower: str = ZERO_ADDRESS
    lender: str = ZERO_ADDRESS
    collateral_contract: str = ZERO_ADDRESS
    collateral_token_id: int = 0
    fees: list[Fee] = field(default_factory=list)
    pro_rata: bool = False
    delegate: str = ZERO_ADDRESS

    def get_protocol_fee(self):
        return next((f for f in self.fees if f.type == FeeType.PROTOCOL), None)

    def get_lender_broker_fee(self):
        return next((f for f in self.fees if f.type == FeeType.LENDER_BROKER), None)

    def get_borrower_broker_fee(self):
        return next((f for f in self.fees if f.type == FeeType.BORROWER_BROKER), None)

    def get_origination_fee(self):
        return next((f for f in self.fees if f.type == FeeType.ORIGINATION), None)

    def get_settlement_fees(self, timestamp=None):
        interest = self.get_interest(timestamp) if timestamp else self.interest
        return sum(f.settlement_bps * interest // 10000 for f in self.fees)

    def get_interest(self, timestamp):
        if self.pro_rata:
            return self.interest * (timestamp - self.start_time) // (self.maturity - self.start_time)
        return self.interest

    def calc_borrower_broker_settlement_fee(self, timestamp):
        interest = self.get_interest(timestamp)
        fee = self.get_borrower_broker_fee()
        return interest * fee.settlement_bps // 10000


CollectionContract = namedtuple("CollectionContract", ["collection", "contract"], defaults=[ZERO_BYTES32, ZERO_ADDRESS])


def compute_loan_hash(loan: Loan):
    print(f"compute_loan_hash {loan=}")
    encoded = eth_abi.encode(
        [
            "(bytes32,bytes32,bytes32,uint256,uint256,address,uint256,uint256,address,address,address,uint256,(uint256,uint256,uint256,address)[],bool,address)"
        ],
        [loan],
    )
    return keccak(encoded)


def compute_signed_offer_id(offer: SignedOffer):
    import boa  # noqa: PLC0415 temp workaround

    return boa.eval(
        dedent(
            f"""keccak256(
            concat(
                convert({offer.signature.v}, bytes32),
                convert({offer.signature.r}, bytes32),
                convert({offer.signature.s}, bytes32),
            ))"""
        )
    )


def sign_offer(offer: Offer, lender, verifying_contract: str) -> SignedOffer:
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Offer": [
                {"name": "principal", "type": "uint256"},
                {"name": "interest", "type": "uint256"},
                {"name": "payment_token", "type": "address"},
                {"name": "duration", "type": "uint256"},
                {"name": "origination_fee_amount", "type": "uint256"},
                {"name": "broker_upfront_fee_amount", "type": "uint256"},
                {"name": "broker_settlement_fee_bps", "type": "uint256"},
                {"name": "broker_address", "type": "address"},
                {"name": "offer_type", "type": "uint256"},
                {"name": "token_id", "type": "uint256"},
                {"name": "token_range_min", "type": "uint256"},
                {"name": "token_range_max", "type": "uint256"},
                {"name": "collection_key_hash", "type": "bytes32"},
                {"name": "trait_hash", "type": "bytes32"},
                {"name": "expiration", "type": "uint256"},
                {"name": "lender", "type": "address"},
                {"name": "pro_rata", "type": "bool"},
                {"name": "size", "type": "uint256"},
                {"name": "tracing_id", "type": "bytes32"},
            ],
        },
        "primaryType": "Offer",
        "domain": {
            "name": "Zharta",
            "version": "1",
            "chainId": networks.chain_manager.chain_id,
            "verifyingContract": verifying_contract,
        },
        "message": offer._asdict(),
    }
    signable_msg = encode_typed_data(full_message=typed_data)
    signed_msg = lender.sign_message(signable_msg)

    if type(signed_msg.r) is bytes:
        lender_signature = Signature(signed_msg.v, signed_msg.r.hex(), signed_msg.s.hex())
    elif type(signed_msg.r) is int:
        lender_signature = Signature(signed_msg.v, hex(signed_msg.r), hex(signed_msg.s))
    else:
        lender_signature = Signature(signed_msg.v, signed_msg.r, signed_msg.s)

    return SignedOffer(offer, lender_signature)


def create_offer_draft(**offer):
    payload = {
        "offer_type": offer.get("offer_type"),
        "principal": str(int(offer.get("principal"))),
        "apr": str(int(offer.get("apr"))),
        "p2p_contract_key": offer.get("p2p_contract_key"),
        "duration": offer.get("duration"),
        "lender": offer.get("lender"),
        "pro_rata": offer.get("pro_rata", True),
        "size": offer.get("size", 1),
        "expiration": offer.get("expiration", 2000000000),
        "origination_fee_amount": str(int(offer.get("origination_fee_amount", 0))),
        "broker_upfront_fee_amount": str(int(offer.get("broker_upfront_fee_amount", 0))),
        "broker_settlement_fee_bps": offer.get("broker_settlement_fee_bps", 0),
        "collection_key": offer.get("collection_key"),
    }
    if offer.get("token_id"):
        payload["token_id"] = offer.get("token_id")
    if offer.get("updated_offer_id"):
        payload["updated_offer_id"] = offer.get("updated_offer_id")
    if offer.get("broker_address"):
        payload["broker_address"] = offer.get("broker_address")
    if offer.get("trait_name"):
        payload["trait_name"] = offer.get("trait_name")
    if offer.get("trait_value"):
        payload["trait_value"] = offer.get("trait_value")

    response = requests.post(f"{P2P_SERVICE_BASE_URL}/offers/draft", json=payload)

    if response.status_code != 200:
        print(response.text)
    response.raise_for_status()

    return response.json()


def create_offer_backend(signer: Account, **offer):
    filtered_offer = {k: v for k, v in offer.items() if k in Offer._fields}
    filtered_offer["offer_type"] = OfferType[filtered_offer["offer_type"]]
    filtered_offer["principal"] = int(filtered_offer["principal"])
    filtered_offer["interest"] = int(filtered_offer["interest"])
    filtered_offer["origination_fee_amount"] = int(filtered_offer["origination_fee_amount"])
    filtered_offer["broker_upfront_fee_amount"] = int(filtered_offer["broker_upfront_fee_amount"])
    filtered_offer["token_range_min"] = int(filtered_offer.get("token_range_min"))
    filtered_offer["token_range_max"] = int(filtered_offer.get("token_range_max"))
    filtered_offer["trait_hash"] = bytes.fromhex(filtered_offer.get("trait_hash", ZERO_BYTES32))
    filtered_offer["collection_key_hash"] = bytes.fromhex(filtered_offer["collection_key_hash"])
    filtered_offer["tracing_id"] = bytes.fromhex(filtered_offer["tracing_id"])
    _offer = Offer(**filtered_offer)

    verifying_contract = offer.get("p2p_contract")
    signed_offer = sign_offer(_offer, signer, verifying_contract)
    sig = signed_offer.signature

    payload = {
        "offer_type": offer.get("offer_type"),
        "offer_display_type": offer.get("offer_display_type", "AUTOMATIC"),
        "principal": str(_offer.principal),
        "interest": str(_offer.interest),
        "apr": offer.get("apr"),
        "payment_token": _offer.payment_token,
        "p2p_contract": offer.get("p2p_contract"),
        "duration": _offer.duration,
        "lender": _offer.lender,
        "pro_rata": _offer.pro_rata,
        "size": _offer.size,
        "expiration": _offer.expiration,
        "tracing_id": _offer.tracing_id.hex(),
        "origination_fee_amount": str(_offer.origination_fee_amount),
        "broker_upfront_fee_amount": str(_offer.broker_upfront_fee_amount),
        "broker_settlement_fee_bps": _offer.broker_settlement_fee_bps,
        "broker_address": _offer.broker_address,
        "collection_key": offer.get("collection_key"),
        "collection_key_hash": _offer.collection_key_hash.hex(),
        "collection_contract": offer.get("collection_contract"),
        "token_id": _offer.token_id,
        "token_range_min": offer.get("token_range_min"),
        "token_range_max": offer.get("token_range_max"),
        "trait_hash": offer.get("trait_hash"),
        "trait_name": offer.get("trait_name"),
        "trait_value": offer.get("trait_value"),
        "signature": {"v": sig.v, "r": sig.r, "s": sig.s},
    }

    response = requests.post(f"{P2P_SERVICE_BASE_URL}/offers", json=payload)

    if response.status_code != 200:
        print(response.text)
    response.raise_for_status()

    return response.json()


def get_offer_backend(offer_id):
    response = requests.get(f"{P2P_SERVICE_BASE_URL}/offers/{offer_id}")
    if response.status_code != 200:
        print(response.text)
    response.raise_for_status()

    return response.json()


def revoke_offer(signed_offer: dict, contract: str, *, sender):
    filtered_offer = {k: v for k, v in signed_offer.items() if k in Offer._fields}
    filtered_offer["offer_type"] = OfferType[filtered_offer["offer_type"]]
    filtered_offer["principal"] = int(filtered_offer["principal"])
    filtered_offer["interest"] = int(filtered_offer["interest"])
    filtered_offer["origination_fee_amount"] = int(filtered_offer["origination_fee_amount"])
    filtered_offer["broker_upfront_fee_amount"] = int(filtered_offer["broker_upfront_fee_amount"])
    filtered_offer["token_range_min"] = int(filtered_offer.get("token_range_min"))
    filtered_offer["token_range_max"] = int(filtered_offer.get("token_range_max"))
    filtered_offer["trait_hash"] = bytes.fromhex(filtered_offer.get("trait_hash", ZERO_BYTES32))
    filtered_offer["collection_key_hash"] = bytes.fromhex(filtered_offer["collection_key_hash"])
    filtered_offer["tracing_id"] = bytes.fromhex(filtered_offer["tracing_id"])

    _offer = Offer(**filtered_offer)
    offer_signature = signed_offer.get("signature")
    _signature = Signature(offer_signature.get("v"), HexBytes(offer_signature.get("r")), HexBytes(offer_signature.get("s")))
    _signed_offer = SignedOffer(_offer, _signature)

    return contract.revoke_offer(_signed_offer, sender=sender)


def create_loan(
    signed_offer: dict,
    token_id: int,
    contract,
    *,
    proof=[],
    delegate=ZERO_ADDRESS,
    borrower_broker_upfront_fee_amount=0,
    borrower_broker_settlement_fee_bps=0,
    borrower_broker=ZERO_ADDRESS,
    sender,
):
    filtered_offer = {k: v for k, v in signed_offer.items() if k in Offer._fields}
    filtered_offer["offer_type"] = OfferType[filtered_offer["offer_type"]]
    filtered_offer["principal"] = int(filtered_offer["principal"])
    filtered_offer["interest"] = int(filtered_offer["interest"])
    filtered_offer["origination_fee_amount"] = int(filtered_offer["origination_fee_amount"])
    filtered_offer["broker_upfront_fee_amount"] = int(filtered_offer["broker_upfront_fee_amount"])
    filtered_offer["token_range_min"] = int(filtered_offer.get("token_range_min"))
    filtered_offer["token_range_max"] = int(filtered_offer.get("token_range_max"))
    filtered_offer["trait_hash"] = bytes.fromhex(filtered_offer.get("trait_hash", ZERO_BYTES32))
    filtered_offer["collection_key_hash"] = bytes.fromhex(filtered_offer["collection_key_hash"])
    filtered_offer["tracing_id"] = bytes.fromhex(filtered_offer["tracing_id"])
    _offer = Offer(**filtered_offer)
    offer_signature = signed_offer.get("signature")
    _signed_offer = SignedOffer(
        _offer, Signature(offer_signature.get("v"), HexBytes(offer_signature.get("r")), HexBytes(offer_signature.get("s")))
    )

    p2p_control = ape.Contract(contract.p2p_control())
    collateral_contract = ape.Contract(p2p_control.contracts(_offer.collection_key_hash))
    collateral_contract.approve(contract.address, token_id, sender=sender)
    return contract.create_loan(
        _signed_offer,
        token_id,
        proof,
        delegate,
        borrower_broker_upfront_fee_amount,
        borrower_broker_settlement_fee_bps,
        borrower_broker,
        sender=sender,
    )


def get_loan(loan_id):
    response = requests.get(f"{P2P_SERVICE_BASE_URL}/loans/{loan_id}")
    if response.status_code != 200:
        print(response.text)
    response.raise_for_status()

    loan_data = response.json()
    print(loan_data)

    fees = [
        Fee(
            type=FeeType[f.get("type").replace("_FEE", "")],
            upfront_amount=int(f.get("upfront_amount")),
            settlement_bps=int(f.get("interest_bps")),
            wallet=f.get("wallet"),
        )
        for f in loan_data["fees"].values()
    ]

    fees_dict = {f.type: f for f in fees}

    loan = Loan(
        id=HexBytes(loan_data["loan_id"]),
        offer_id=HexBytes(loan_data["offer_id"]),
        offer_tracing_id=HexBytes(loan_data["offer_tracing_id"]),
        amount=int(loan_data["amount"]),
        interest=int(loan_data["interest"]),
        payment_token=loan_data["payment_token"],
        maturity=int(loan_data["maturity"]),
        start_time=int(loan_data["start_time"]),
        borrower=loan_data["borrower"],
        lender=loan_data["lender"],
        collateral_contract=loan_data["collateral_contract"],
        collateral_token_id=int(loan_data["collateral_token_id"]),
        pro_rata=loan_data["pro_rata"],
        fees=[fees_dict[k] for k in FeeType],
        delegate=loan_data["delegate"],
    )
    print(loan)

    loan_hash = compute_loan_hash(loan)
    print(f"loan_hash: {loan_hash.hex()}")

    return loan


def pay_loan(loan_id, contract, *, sender):
    response = requests.get(f"{P2P_SERVICE_BASE_URL}/loans/{loan_id}")
    if response.status_code != 200:
        print(response.text)
    response.raise_for_status()

    loan_data = response.json()
    print(loan_data)

    fees = [
        Fee(
            type=FeeType[f.get("type").replace("_FEE", "")],
            upfront_amount=int(f.get("upfront_amount")),
            settlement_bps=int(f.get("interest_bps")),
            wallet=f.get("wallet"),
        )
        for f in loan_data["fees"].values()
    ]

    fees_dict = {f.type: f for f in fees}

    loan = Loan(
        id=HexBytes(loan_data["loan_id"]),
        offer_id=HexBytes(loan_data["offer_id"]),
        offer_tracing_id=HexBytes(loan_data["offer_tracing_id"]),
        amount=int(loan_data["amount"]),
        interest=int(loan_data["interest"]),
        payment_token=loan_data["payment_token"],
        maturity=int(loan_data["maturity"]),
        start_time=int(loan_data["start_time"]),
        borrower=loan_data["borrower"],
        lender=loan_data["lender"],
        collateral_contract=loan_data["collateral_contract"],
        collateral_token_id=int(loan_data["collateral_token_id"]),
        pro_rata=loan_data["pro_rata"],
        fees=[fees_dict[k] for k in FeeType],
        delegate=loan_data["delegate"],
    )
    print(loan)

    loan_hash = compute_loan_hash(loan)
    print(f"loan_hash: {loan_hash.hex()}")

    loan_hash_in_contract = contract.loans(loan.id)
    print(f"loan_hash_in_contract: {loan_hash_in_contract.hex()}")

    payment_contract = ape.Contract(loan.payment_token)
    payment_contract.approve(
        contract.address, loan.amount + loan.interest + fees_dict[FeeType.BORROWER_BROKER].settlement_bps, sender=sender
    )

    contract.settle_loan(loan, sender=sender)


def claim_loan_collateral(loan_id, contract, *, sender):
    loan = get_loan(loan_id)
    loan_hash_in_contract = contract.loans(loan.id)
    print(f"loan_hash_in_contract: {loan_hash_in_contract.hex()}")

    contract.claim_defaulted_loan_collateral(loan, sender=sender)


"""
 draft = create_offer_draft(
     offer_type="TOKEN",
     principal=1e9,
     interest=1e7,
     p2p_contract="usdc_nfts",
     duration=30*86400,
     lender=me.address,
     collection_key="bayc",
     token_id=666
 )

 offer = create_offer_backend(me, **draft)
 loan_id = create_loan(offer, 1, p2p_usdc_nfts, sender=me)
"""


def ape_init_extras():
    dm = DeploymentManager(ENV, CHAIN, Context.CONSOLE)

    globals()["dm"] = dm
    globals()["owner"] = dm.owner
    for k, v in dm.context.contracts.items():
        globals()[k.replace(".", "_").replace("-", "_")] = v.contract
        print(k.replace(".", "_"), v.contract)
    for k, v in dm.context.config.items():
        globals()[k.replace(".", "_").replace("-", "_")] = v

from functools import cached_property
from itertools import starmap

import boa
import vyper


import contextlib
from collections import namedtuple
from typing import NamedTuple
from dataclasses import dataclass, field
from textwrap import dedent

from boa.contracts.vyper.event import Event
from boa.contracts.vyper.vyper_contract import VyperContract
from eth.exceptions import Revert
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_intended_validator, encode_structured_data
from eth_utils import encode_hex, keccak
from web3 import Web3


ZERO_ADDRESS = boa.eval("empty(address)")
ZERO_BYTES32 = boa.eval("empty(bytes32)")


def get_last_event(contract: VyperContract, name: str | None = None):
    # print("CONTRACT LOGS", contract.get_logs())
    # print("\n\n\n")
    matching_events = [e for e in contract.get_logs() if isinstance(e, Event) and (name is None or name == e.event_type.name)]
    return EventWrapper(matching_events[-1])


def get_events(contract: VyperContract, name: str | None = None):
    return [
        EventWrapper(e) for e in contract.get_logs() if isinstance(e, Event) and (name is None or name == e.event_type.name)
    ]


class EventWrapper:
    def __init__(self, event: Event):
        self.event = event
        self.event_name = event.event_type.name

    def __getattr__(self, name):
        print(f"getattr {self=} {name=}")
        if name in self.args_dict:
            return self.args_dict[name]
        raise AttributeError(f"No attr {name} in {self.event_name}. Event data is {self.event}")

    @cached_property
    def args_dict(self):
        # print(f"{self.event=} {self.event.event_type.arguments=}")
        args = self.event.event_type.arguments.keys()
        indexed = self.event.event_type.indexed
        topic_values = (v for v in self.event.topics)
        args_values = (v for v in self.event.args)
        _args = [(arg, next(topic_values) if indexed[i] else next(args_values)) for i, arg in enumerate(args)]

        return {k: self._format_value(v, self.event.event_type.arguments[k]) for k, v in _args}

    def _format_value(self, v, _type):  # noqa: PLR6301
        # print(f"_format_value {v=} {_type=} {type(v).__name__=} {type(_type)=}")
        if isinstance(_type, vyper.semantics.types.primitives.AddressT):
            return Web3.to_checksum_address(v)
        if isinstance(_type, vyper.semantics.types.primitives.BytesT):
            return f"0x{v.hex()}"
        return v

    def __repr__(self):
        return f"<EventWrapper {self.event_name} {self.args_dict}>"


# TODO: find a better way to do this. also would be useful to get structs attrs by name
def checksummed(obj, vyper_type=None):
    if vyper_type is None and hasattr(obj, "_vyper_type"):
        vyper_type = obj._vyper_type
    print(f"checksummed {obj=} {vyper_type=} {type(obj).__name__=} {type(vyper_type)=}")

    if isinstance(vyper_type, vyper.codegen.types.types.DArrayType):
        return [checksummed(x, vyper_type.subtype) for x in obj]

    if isinstance(vyper_type, vyper.codegen.types.types.StructType):
        return tuple(starmap(checksummed, zip(obj, vyper_type.tuple_members())))

    if isinstance(vyper_type, vyper.codegen.types.types.BaseType):
        if vyper_type.typ == "address":
            return Web3.toChecksumAddress(obj)
        if vyper_type.typ == "bytes32":
            return f"0x{obj.hex()}"

    return obj


@contextlib.contextmanager
def deploy_reverts():
    try:
        yield
        raise ValueError("Did not revert")
    except Revert:
        ...


Offer = namedtuple(
    "Offer",
    [
        "principal",
        "interest",
        "payment_token",
        "duration",
        "origination_fee_amount",
        "broker_fee_bps",
        "broker_address",
        "collateral_contract",
        "collateral_min_token_id",
        "collateral_max_token_id",
        "expiration",
        "lender",
        "pro_rata",
        "size"
    ],
    defaults=[0, 0, ZERO_ADDRESS, 0, 0, 0, ZERO_ADDRESS, ZERO_ADDRESS, 0, 0, 0, ZERO_ADDRESS, False, 0]
)

Signature = namedtuple("Signature", ["v", "r", "s"], defaults=[0, ZERO_BYTES32, ZERO_BYTES32])

SignedOffer = namedtuple("SignedOffer", ["offer", "signature"], defaults=[Offer(), Signature()])

Loan = namedtuple(
    "Loan",
    [
        "id",
        "amount",
        "interest",
        "payment_token",
        "maturity",
        "start_time",
        "borrower",
        "lender",
        "collateral_contract",
        "collateral_token_id",
        "origination_fee_amount",
        "broker_fee_bps",
        "broker_address",
        "protocol_fee_bps",
        "pro_rata",
    ],
    defaults=[
        ZERO_BYTES32,
        0,
        0,
        ZERO_ADDRESS,
        0,
        0,
        ZERO_ADDRESS,
        ZERO_ADDRESS,
        ZERO_ADDRESS,
        0,
        0,
        0,
        ZERO_ADDRESS,
        0,
        False
    ]
)

BrokerLock = namedtuple("BrokerLock", ["broker", "expiration"], defaults=[ZERO_ADDRESS, 0])


class CollateralStatus(NamedTuple):
    broker_lock: BrokerLock = BrokerLock()
    whitelisted: bool = False

    @classmethod
    def from_tuple(cls, t):
        broker_lock, whitelisted = t
        return cls(BrokerLock(*broker_lock), whitelisted)


PunkOffer = namedtuple(
    "PunkOffer",
    ["isForSale", "punkIndex", "seller", "minValue", "onlySellTo"],
    defaults=[False, 0, ZERO_ADDRESS, 0, ZERO_ADDRESS]
)


WhitelistRecord = namedtuple("WhitelistRecord", ["collection", "whitelisted"], defaults=[ZERO_ADDRESS, False])


def compute_loan_hash(loan: Loan):
    return boa.eval(
        dedent(
            f"""keccak256(
            concat(
                {loan.id},
                convert({loan.amount}, bytes32),
                convert({loan.interest}, bytes32),
                convert({loan.payment_token}, bytes32),
                convert({loan.maturity}, bytes32),
                convert({loan.start_time}, bytes32),
                convert({loan.borrower}, bytes32),
                convert({loan.lender}, bytes32),
                convert({loan.collateral_contract}, bytes32),
                convert({loan.collateral_token_id}, bytes32),
                convert({loan.origination_fee_amount}, bytes32),
                convert({loan.broker_fee_bps}, bytes32),
                convert({loan.broker_address}, bytes32),
                convert({loan.protocol_fee_bps}, bytes32),
                convert({loan.pro_rata}, bytes32),
            ))"""
        )
    )


def compute_signed_offer_id(offer: SignedOffer):
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


def sign_offer(offer: Offer, lender_key: str, verifying_contract: str) -> SignedOffer:
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
                {"name": "broker_fee_bps", "type": "uint256"},
                {"name": "broker_address", "type": "address"},
                {"name": "collateral_contract", "type": "address"},
                {"name": "collateral_min_token_id", "type": "uint256"},
                {"name": "collateral_max_token_id", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "lender", "type": "address"},
                {"name": "pro_rata", "type": "bool"},
                {"name": "size", "type": "uint256"},
            ],
        },
        "primaryType": "Offer",
        "domain": {
            "name": "Zharta",
            "version": "1",
            "chainId": boa.eval("chain.id"),
            "verifyingContract": verifying_contract,
        },
        "message": offer._asdict(),
    }
    signable_msg = encode_structured_data(typed_data)
    signed_msg = Account.from_key(lender_key).sign_message(signable_msg)
    lender_signature = Signature(signed_msg.v, signed_msg.r, signed_msg.s)

    return SignedOffer(offer, lender_signature)

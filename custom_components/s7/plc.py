"""PLC client backends for the s7 integration.

Two wire protocols are supported behind one small interface:

* ``legacy``     - classic S7 (PUT/GET) via ``python-snap7``. Works on
  S7-300/400 and on S7-1200/1500 with PUT/GET access enabled.
* ``s7commplus`` - S7CommPlus (V1/V2/V3) via ``s7commplus``, for S7-1200/1500
  CPUs where PUT/GET is disabled.

Both backends are blocking and are only ever called from the executor.
Tags use absolute (byte-offset) addressing, so S7-1200/1500 data blocks must
have "Optimized block access" turned off.
"""

from __future__ import annotations

from typing import Any, Protocol

from s7commplus import Client as CommPlusClient
from s7commplus.protocol import DataType, Ids
from snap7.client import Client as LegacyClient
from snap7.client import _decode_tag, _encode_tag
from snap7.tags import Tag
from snap7.type import Area

from .const import PROTOCOL_LEGACY, PROTOCOL_S7COMMPLUS

# Native object RIDs of the non-DB memory areas in S7CommPlus.
_AREA_RIDS: dict[Area, int] = {
    Area.PE: Ids.NATIVE_THE_I_AREA_RID,
    Area.PA: Ids.NATIVE_THE_Q_AREA_RID,
    Area.MK: Ids.NATIVE_THE_M_AREA_RID,
}

# S7CommPlus wants the wire datatype of the target on writes. Everything
# not listed here (strings, times, arrays, ...) is written as a raw BLOB.
_WRITE_DATATYPES: dict[str, DataType] = {
    "BOOL": DataType.BYTE,  # read-modify-write of the containing byte
    "BYTE": DataType.BYTE,
    "SINT": DataType.SINT,
    "USINT": DataType.USINT,
    "INT": DataType.INT,
    "UINT": DataType.UINT,
    "WORD": DataType.WORD,
    "DINT": DataType.DINT,
    "UDINT": DataType.UDINT,
    "DWORD": DataType.DWORD,
    "REAL": DataType.REAL,
    "LINT": DataType.LINT,
    "ULINT": DataType.ULINT,
    "LWORD": DataType.LWORD,
    "LREAL": DataType.LREAL,
}


class PlcClient(Protocol):
    """What the coordinator needs from a PLC connection."""

    @property
    def connected(self) -> bool: ...

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def read_tags(self, tags: list[Tag]) -> list[Any]: ...

    def write_tag(self, tag: Tag, value: Any) -> None: ...


def _reject_symbolic(tag: Tag) -> None:
    if tag.is_symbolic:
        raise NotImplementedError(f"Symbolic (LID-based) access is not supported: {tag}")


class LegacyPlcClient:
    """Classic S7 backend (python-snap7)."""

    def __init__(self, host: str, rack: int, slot: int, port: int) -> None:
        self._client = LegacyClient()
        self._host = host
        self._rack = rack
        self._slot = slot
        self._port = port

    @property
    def connected(self) -> bool:
        return bool(self._client.connected)

    def connect(self) -> None:
        self._client.connect(self._host, self._rack, self._slot, self._port)

    def disconnect(self) -> None:
        self._client.disconnect()

    def read_tags(self, tags: list[Tag]) -> list[Any]:
        # Passing Tag objects lets python-snap7's optimizer coalesce reads.
        return list(self._client.read_tags(tags))

    def write_tag(self, tag: Tag, value: Any) -> None:
        self._client.write_tag(tag, value)


class CommPlusPlcClient:
    """S7CommPlus backend (s7commplus) for S7-1200/1500."""

    def __init__(self, host: str, port: int, use_tls: bool, password: str | None) -> None:
        self._client = CommPlusClient()
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._password = password

    @property
    def connected(self) -> bool:
        return bool(self._client.connected)

    def connect(self) -> None:
        self._client.connect(self._host, self._port, use_tls=self._use_tls, password=self._password or None)

    def disconnect(self) -> None:
        self._client.disconnect()

    def _read_raw(self, tag: Tag) -> bytes:
        if tag.area == Area.DB:
            data = self._client.db_read(tag.db_number, tag.byte_offset, tag.size)
        else:
            data = self._client.read_area(_AREA_RIDS[Area(tag.area)], tag.byte_offset, tag.size)
        if len(data) < tag.size:
            raise RuntimeError(f"Short read for {tag}: got {len(data)} of {tag.size} bytes")
        return data

    def read_tags(self, tags: list[Tag]) -> list[Any]:
        for tag in tags:
            _reject_symbolic(tag)
        db_idx = [i for i, t in enumerate(tags) if t.area == Area.DB]
        results: list[Any] = [None] * len(tags)

        # All DB tags go out in one request; other areas are read one by one.
        if db_idx:
            chunks = self._client.db_read_multi([(tags[i].db_number, tags[i].byte_offset, tags[i].size) for i in db_idx])
            for i, chunk in zip(db_idx, chunks, strict=True):
                if len(chunk) < tags[i].size:
                    raise RuntimeError(f"Read failed for {tags[i]}")
                results[i] = _decode_tag(tags[i], bytearray(chunk))
        for i, tag in enumerate(tags):
            if tag.area != Area.DB:
                results[i] = _decode_tag(tag, bytearray(self._read_raw(tag)))
        return results

    def write_tag(self, tag: Tag, value: Any) -> None:
        _reject_symbolic(tag)
        buf = bytearray(tag.size)
        if tag.datatype.upper() == "BOOL":
            buf[:] = self._read_raw(tag)[: tag.size]
        _encode_tag(tag, buf, value)
        datatype = _WRITE_DATATYPES.get(tag.datatype.upper(), DataType.BLOB)
        if tag.area == Area.DB:
            self._client.db_write(tag.db_number, tag.byte_offset, bytes(buf), datatype)
        else:
            self._client.write_area(_AREA_RIDS[Area(tag.area)], tag.byte_offset, bytes(buf), datatype=datatype)


def create_client(
    protocol: str,
    *,
    host: str,
    rack: int,
    slot: int,
    port: int,
    use_tls: bool,
    password: str | None,
) -> PlcClient:
    """Build the backend for the configured protocol."""
    if protocol == PROTOCOL_S7COMMPLUS:
        return CommPlusPlcClient(host, port, use_tls, password)
    if protocol == PROTOCOL_LEGACY:
        return LegacyPlcClient(host, rack, slot, port)
    raise ValueError(f"Unknown protocol: {protocol!r}")

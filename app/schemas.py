"""Pydantic schemas for API and web-form validation."""
import ipaddress
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import (
    ADDRESS_FAMILIES,
    ALLOCATION_METHODS,
    ANTIVIRUS_STATUSES,
    BACKUP_STATUSES,
    COMPLIANCE_STATUSES,
    CRITICALITY_LEVELS,
    DATA_CLASSIFICATIONS,
    DEVICE_CLASSES,
    DISCOVERY_SOURCES,
    LIFECYCLE_STATUSES,
    NETWORK_ENVIRONMENTS,
    NETWORK_STATUSES,
    PATCH_STATUSES,
    ROLE_ADMIN,
    ROLE_VIEWER,
)

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_MAC_SPLIT_RE = re.compile(r"[,;\s]+")
_STATUSES = Literal["Available", "Reserved", "Active", "Deprecated"]
MAX_MAC_ADDRESSES = 20


def _clean_ip(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    ip = str(value).strip()
    ipaddress.ip_address(ip)
    return ip


def _clean_mac(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    mac = str(value).strip()
    if not _MAC_RE.fullmatch(mac):
        raise ValueError("Invalid MAC address, expected XX:XX:XX:XX:XX:XX")
    return mac


def _split_macs(value: Any) -> list[str]:
    """Normalise a MAC submission into a list of candidate strings.

    Accepts a list/tuple (one entry per repeatable input) or a single string
    holding comma, semicolon or whitespace separated addresses.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [part for part in _MAC_SPLIT_RE.split(value.strip()) if part]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("MAC addresses must be a list or a separated string")


def _clean_ip_list(value: Any) -> list[str]:
    """Validate a list of IP addresses (DNS servers).

    ``_clean_ip`` raises on a malformed address; for a list we drop unusable
    entries instead, so one bad DNS server does not block the whole network.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for candidate in _split_macs(value):
        try:
            parsed = _clean_ip(candidate)
        except ValueError:
            continue
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        cleaned.append(parsed)
    return cleaned


def _clean_mac_list(value: Any) -> list[str]:
    """Validate, de-duplicate and bound a list of MAC addresses."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for candidate in _split_macs(value):
        mac = _clean_mac(candidate)
        if mac is None:
            continue
        key = mac.lower().replace("-", ":")
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(mac)
    if len(cleaned) > MAX_MAC_ADDRESSES:
        raise ValueError(f"At most {MAX_MAC_ADDRESSES} MAC addresses are allowed")
    return cleaned


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal[ROLE_ADMIN, ROLE_VIEWER] = ROLE_VIEWER


class UserUpdate(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    role: Literal[ROLE_ADMIN, ROLE_VIEWER]
    is_active: bool = True


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    last_login: datetime | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# IP addresses
# --------------------------------------------------------------------------- #
class IPAddressBase(BaseModel):
    ip_address: str | None = None
    subnet_prefix: int | None = Field(default=None, ge=1, le=128)
    gateway: str | None = None
    vlan_id: int | None = Field(default=None, ge=1, le=4094)
    network_segment: str | None = Field(default=None, max_length=100)
    mac_addresses: list[str] = Field(default_factory=list, max_length=MAX_MAC_ADDRESSES)
    hostname: str | None = Field(default=None, max_length=255)
    assigned_to: str | None = Field(default=None, max_length=255)
    device_type: str | None = Field(default=None, max_length=50)
    interface_name: str | None = Field(default=None, max_length=50)
    status: _STATUSES = "Available"
    description: str | None = None
    notes: str | None = None
    assigned_date: datetime | None = None
    expiry_date: datetime | None = None
    owner: str | None = Field(default=None, max_length=100)
    responsible_person: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    team: str | None = Field(default=None, max_length=100)
    allocation_type: Literal["Static", "DHCP"] = "Static"
    fqdn: str | None = Field(default=None, max_length=255)
    device_model: str | None = Field(default=None, max_length=100)
    vendor: str | None = Field(default=None, max_length=100)
    operating_system: str | None = Field(default=None, max_length=100)
    firmware: str | None = Field(default=None, max_length=100)
    role: str | None = Field(default=None, max_length=100)
    purpose: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=100)
    tags: str | None = Field(default=None, max_length=255)
    security_group: str | None = Field(default=None, max_length=100)
    acl_applied: str | None = Field(default=None, max_length=100)
    subnet_id: int | None = Field(default=None, ge=1)
    is_primary: bool = False

    # ---------------- assignment governance ---------------- #
    allocation_method: Literal[ALLOCATION_METHODS] = "Manual"
    reverse_dns: str | None = Field(default=None, max_length=255)
    redundancy_group: str | None = Field(default=None, max_length=100)
    shared_with: str | None = None
    status_reason: str | None = Field(default=None, max_length=255)
    status_changed_at: datetime | None = None
    approved_by: str | None = Field(default=None, max_length=100)
    discovery_source: Literal[DISCOVERY_SOURCES] = "Manual"
    device_id: int | None = Field(default=None, ge=1)

    @field_validator("ip_address", "gateway")
    @classmethod
    def _validate_ip(cls, value: str | None) -> str | None:
        return _clean_ip(value)

    @field_validator("mac_addresses", mode="before")
    @classmethod
    def _validate_mac(cls, value: Any) -> list[str]:
        return _clean_mac_list(value)


class IPAddressCreate(IPAddressBase):
    ip_address: str
    subnet_prefix: int = Field(ge=1, le=128)


class IPAddressUpdate(IPAddressBase):
    pass


class IPAddressOut(IPAddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Networks
# --------------------------------------------------------------------------- #
class NetworkBase(BaseModel):
    network_name: str | None = Field(default=None, max_length=100)
    network_range: str | None = Field(default=None, max_length=50)
    cidr: str | None = Field(default=None, max_length=50)
    subnet_mask: str | None = Field(default=None, max_length=15)
    broadcast_address: str | None = None
    vlan_id: int | None = Field(default=None, ge=1, le=4094)
    network_role: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=100)
    description: str | None = None

    # ---------------- addressing ---------------- #
    address_family: Literal[ADDRESS_FAMILIES] = "IPv4"
    gateway: str | None = None
    dns_servers: list[str] = Field(default_factory=list, max_length=10)
    domain_name: str | None = Field(default=None, max_length=255)
    vrf: str | None = Field(default=None, max_length=100)
    dhcp_enabled: bool = False
    dhcp_server: str | None = Field(default=None, max_length=100)
    dhcp_range_start: str | None = None
    dhcp_range_end: str | None = None

    # ---------------- vlan span ---------------- #
    vlan_name: str | None = Field(default=None, max_length=100)
    vlan_range_start: str | None = None
    vlan_range_end: str | None = None

    # ---------------- ownership & governance ---------------- #
    environment: Literal[NETWORK_ENVIRONMENTS] | None = None
    tenant: str | None = Field(default=None, max_length=100)
    criticality: Literal[CRITICALITY_LEVELS] = "Medium"
    owner: str | None = Field(default=None, max_length=100)
    contact_email: str | None = Field(default=None, max_length=255)
    cost_center: str | None = Field(default=None, max_length=50)
    site_code: str | None = Field(default=None, max_length=50)
    datacenter: str | None = Field(default=None, max_length=100)

    # ---------------- lifecycle ---------------- #
    status: Literal[NETWORK_STATUSES] = "Active"
    tags: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    parent_network_id: int | None = Field(default=None, ge=1)

    @field_validator("broadcast_address")
    @classmethod
    def _validate_broadcast(cls, value: str | None) -> str | None:
        return _clean_ip(value)

    @field_validator("gateway", "dhcp_range_start", "dhcp_range_end",
                     "vlan_range_start", "vlan_range_end")
    @classmethod
    def _validate_address(cls, value: str | None) -> str | None:
        return _clean_ip(value)

    @field_validator("dns_servers", mode="before")
    @classmethod
    def _validate_dns(cls, value: Any) -> list[str]:
        return _clean_ip_list(value)

    @field_validator("cidr")
    @classmethod
    def _validate_cidr(cls, value: str | None) -> str | None:
        if not value:
            return value
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError(f"Not a valid CIDR block: {exc}") from exc
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> "NetworkBase":
        """Cross-field rules that need the whole record.

        This runs where a field validator cannot: ``address_family`` is usually
        left at its default, and Pydantic skips field validators on defaults.
        """
        block = None
        if self.cidr:
            block = ipaddress.ip_network(self.cidr, strict=False)
            # The CIDR is authoritative; the dropdown just mirrors it.
            self.address_family = "IPv6" if block.version == 6 else "IPv4"

        if self.gateway and block is not None:
            gateway = ipaddress.ip_address(self.gateway)
            if gateway.version != block.version or gateway not in block:
                raise ValueError(f"Gateway {gateway} is outside {self.cidr}")

        if self.broadcast_address and block is not None:
            broadcast = ipaddress.ip_address(self.broadcast_address)
            if broadcast.version != block.version or broadcast not in block:
                raise ValueError(f"Broadcast {broadcast} is outside {self.cidr}")

        for start_label, start, end in (
            ("DHCP", self.dhcp_range_start, self.dhcp_range_end),
            ("VLAN", self.vlan_range_start, self.vlan_range_end),
        ):
            if bool(start) != bool(end):
                raise ValueError(
                    f"{start_label} range needs both a start and an end address"
                )
            if not start or not end:
                continue
            start_ip = ipaddress.ip_address(start)
            end_ip = ipaddress.ip_address(end)
            if start_ip.version != end_ip.version:
                raise ValueError(f"{start_label} range mixes IPv4 and IPv6")
            if int(start_ip) > int(end_ip):
                raise ValueError(f"{start_label} range start must not be above its end")
            if block is not None:
                if start_ip.version != block.version or start_ip not in block:
                    raise ValueError(f"{start_label} range start {start} is outside {self.cidr}")
                if end_ip.version != block.version or end_ip not in block:
                    raise ValueError(f"{start_label} range end {end} is outside {self.cidr}")
        return self


class NetworkCreate(NetworkBase):
    network_name: str
    network_range: str
    cidr: str


class NetworkUpdate(NetworkBase):
    pass


class NetworkOut(NetworkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Devices
# --------------------------------------------------------------------------- #
class DeviceBase(BaseModel):
    hostname: str | None = Field(default=None, max_length=255)
    fqdn: str | None = Field(default=None, max_length=255)
    device_model: str | None = Field(default=None, max_length=100)
    vendor: str | None = Field(default=None, max_length=100)
    operating_system: str | None = Field(default=None, max_length=100)
    firmware: str | None = Field(default=None, max_length=100)
    role: str | None = Field(default=None, max_length=100)
    purpose: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    rack: str | None = Field(default=None, max_length=50)
    room: str | None = Field(default=None, max_length=50)
    datacenter: str | None = Field(default=None, max_length=100)
    owner: str | None = Field(default=None, max_length=100)
    responsible_person: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    team: str | None = Field(default=None, max_length=100)
    status: Literal["Active", "Inactive", "Maintenance"] = "Active"
    description: str | None = None
    notes: str | None = None

    # ---------------- CMDB: identification ---------------- #
    asset_tag: str | None = Field(default=None, max_length=64)
    inventory_id: str | None = Field(default=None, max_length=64)
    instance_id: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, max_length=64)
    device_uuid: str | None = Field(default=None, max_length=64)

    # ---------------- CMDB: classification ---------------- #
    device_class: Literal[DEVICE_CLASSES] = "Other"
    device_subtype: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=100)
    part_number: str | None = Field(default=None, max_length=100)
    chassis_type: str | None = Field(default=None, max_length=50)
    is_virtual: bool = False

    # ---------------- CMDB: lifecycle ---------------- #
    lifecycle_status: Literal[LIFECYCLE_STATUSES] = "In Service"
    purchase_date: date | None = None
    warranty_start: date | None = None
    warranty_end: date | None = None
    install_date: date | None = None
    decommission_date: date | None = None
    last_audit_date: date | None = None
    next_review_date: date | None = None

    # ---------------- CMDB: financial ---------------- #
    purchase_cost: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    po_number: str | None = Field(default=None, max_length=50)
    contract_number: str | None = Field(default=None, max_length=50)
    supplier: str | None = Field(default=None, max_length=100)
    lease_end: date | None = None

    # ---------------- CMDB: organisation ---------------- #
    cost_center: str | None = Field(default=None, max_length=50)
    business_unit: str | None = Field(default=None, max_length=100)
    asset_custodian: str | None = Field(default=None, max_length=100)
    managed_by: str | None = Field(default=None, max_length=100)
    approver: str | None = Field(default=None, max_length=100)

    # ---------------- CMDB: location / placement ---------------- #
    site_code: str | None = Field(default=None, max_length=50)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    floor: str | None = Field(default=None, max_length=20)
    rack_position: int | None = Field(default=None, ge=1, le=60)
    rack_units: int | None = Field(default=None, ge=1, le=60)
    slot_position: str | None = Field(default=None, max_length=50)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=50)

    # ---------------- CMDB: technical specification ---------------- #
    bios_version: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=100)
    cpu_model: str | None = Field(default=None, max_length=100)
    cpu_count: int | None = Field(default=None, ge=0, le=4096)
    memory_gb: int | None = Field(default=None, ge=0, le=1048576)
    storage_gb: int | None = Field(default=None, ge=0)
    power_draw_w: int | None = Field(default=None, ge=0)
    weight_kg: Decimal | None = Field(default=None, ge=0)
    mac_addresses: list[str] = Field(default_factory=list, max_length=MAX_MAC_ADDRESSES)
    parent_device_id: int | None = Field(default=None, ge=1)

    # ---------------- CMDB: network identity ---------------- #
    primary_ip: str | None = None
    management_ip: str | None = None
    network_segment: str | None = Field(default=None, max_length=100)
    dns_domain: str | None = Field(default=None, max_length=255)
    port_count: int | None = Field(default=None, ge=0, le=100000)
    uplink_speed_mbps: int | None = Field(default=None, ge=0)

    # ---------------- CMDB: service & resilience ---------------- #
    service_name: str | None = Field(default=None, max_length=100)
    service_group: str | None = Field(default=None, max_length=100)
    application: str | None = Field(default=None, max_length=100)
    redundancy_group: str | None = Field(default=None, max_length=100)
    cluster_name: str | None = Field(default=None, max_length=100)
    rto_minutes: int | None = Field(default=None, ge=0)
    rpo_minutes: int | None = Field(default=None, ge=0)
    maintenance_window: str | None = Field(default=None, max_length=100)
    support_ticket: str | None = Field(default=None, max_length=50)
    change_reference: str | None = Field(default=None, max_length=50)

    # ---------------- CMDB: security & compliance ---------------- #
    criticality: Literal[CRITICALITY_LEVELS] = "Medium"
    data_classification: Literal[DATA_CLASSIFICATIONS] | None = None
    compliance_status: Literal[COMPLIANCE_STATUSES] | None = None
    compliance_framework: str | None = Field(default=None, max_length=100)
    authorized_use: bool = True
    patch_status: Literal[PATCH_STATUSES] | None = None
    patch_due_date: date | None = None
    antivirus_status: Literal[ANTIVIRUS_STATUSES] | None = None
    monitoring_enabled: bool = False
    monitoring_agent: str | None = Field(default=None, max_length=100)
    last_seen: datetime | None = None
    backup_status: Literal[BACKUP_STATUSES] | None = None
    last_backup_date: datetime | None = None
    discovery_source: Literal[DISCOVERY_SOURCES] = "Manual"
    last_cmdb_sync: datetime | None = None

    @field_validator("primary_ip", "management_ip")
    @classmethod
    def _validate_cmb_ip(cls, value: str | None) -> str | None:
        return _clean_ip(value)

    @field_validator("mac_addresses", mode="before")
    @classmethod
    def _validate_mac(cls, value: Any) -> list[str]:
        return _clean_mac_list(value)

    @field_validator("currency")
    @classmethod
    def _normalise_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class DeviceCreate(DeviceBase):
    hostname: str


class DeviceUpdate(DeviceBase):
    pass


class DeviceOut(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip_addresses: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("ip_addresses", mode="before")
    @classmethod
    def _flatten_ips(cls, value: Any) -> list[str]:
        """Accept either a list of IPAddress rows or plain strings."""
        if value is None:
            return []
        return [str(getattr(item, "ip_address", item)) for item in value]


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
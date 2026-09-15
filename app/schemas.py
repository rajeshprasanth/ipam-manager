"""Pydantic schemas for API and web-form validation."""
import ipaddress
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import ROLE_ADMIN, ROLE_VIEWER

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_STATUSES = Literal["Available", "Reserved", "Active", "Deprecated"]


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
    mac_address: str | None = None
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

    @field_validator("ip_address", "gateway")
    @classmethod
    def _validate_ip(cls, value: str | None) -> str | None:
        return _clean_ip(value)

    @field_validator("mac_address")
    @classmethod
    def _validate_mac(cls, value: str | None) -> str | None:
        return _clean_mac(value)


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

    @field_validator("broadcast_address")
    @classmethod
    def _validate_broadcast(cls, value: str | None) -> str | None:
        return _clean_ip(value)


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


class DeviceCreate(DeviceBase):
    hostname: str


class DeviceUpdate(DeviceBase):
    pass


class DeviceOut(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


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
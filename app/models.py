"""ORM models for the IPAM application."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.security import utcnow

ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"


class User(Base):
    """Portal user account."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class IPAddress(Base):
    """Model for IP address entries."""
    __tablename__ = "ip_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(39), unique=True, nullable=False, index=True)
    subnet_prefix: Mapped[int] = mapped_column(Integer, nullable=False)
    gateway: Mapped[str | None] = mapped_column(String(39))
    vlan_id: Mapped[int | None] = mapped_column(Integer, index=True)
    network_segment: Mapped[str | None] = mapped_column(String(100))
    mac_address: Mapped[str | None] = mapped_column(String(17))
    hostname: Mapped[str | None] = mapped_column(String(255))
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    device_type: Mapped[str | None] = mapped_column(String(50), index=True)
    interface_name: Mapped[str | None] = mapped_column(String(50))

    status: Mapped[str] = mapped_column(String(20), default="Available", index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    assigned_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner: Mapped[str | None] = mapped_column(String(100))
    responsible_person: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))
    team: Mapped[str | None] = mapped_column(String(100))
    allocation_type: Mapped[str] = mapped_column(String(20), default="Static", nullable=False)

    fqdn: Mapped[str | None] = mapped_column(String(255))
    device_model: Mapped[str | None] = mapped_column(String(100))
    vendor: Mapped[str | None] = mapped_column(String(100))
    operating_system: Mapped[str | None] = mapped_column(String(100))
    firmware: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100))
    purpose: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(100))

    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ping_status: Mapped[str | None] = mapped_column(String(20))
    availability: Mapped[str | None] = mapped_column(String(20))
    related_tickets: Mapped[str | None] = mapped_column(Text)
    incidents: Mapped[str | None] = mapped_column(Text)

    tags: Mapped[str | None] = mapped_column(String(255))
    dns_records: Mapped[str | None] = mapped_column(Text)
    security_group: Mapped[str | None] = mapped_column(String(100))
    acl_applied: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<IPAddress {self.ip_address}>"


class Network(Base):
    """Model for network/subnet entries."""
    __tablename__ = "networks"

    id: Mapped[int] = mapped_column(primary_key=True)
    network_name: Mapped[str] = mapped_column(String(100), nullable=False)
    network_range: Mapped[str] = mapped_column(String(50), nullable=False)
    cidr: Mapped[str] = mapped_column(String(50), nullable=False)
    subnet_mask: Mapped[str | None] = mapped_column(String(15))
    broadcast_address: Mapped[str | None] = mapped_column(String(39))
    vlan_id: Mapped[int | None] = mapped_column(Integer, index=True)
    network_role: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Network {self.network_name} ({self.network_range})>"


class Device(Base):
    """Model for device entries."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    fqdn: Mapped[str | None] = mapped_column(String(255))
    device_model: Mapped[str | None] = mapped_column(String(100))
    vendor: Mapped[str | None] = mapped_column(String(100))
    operating_system: Mapped[str | None] = mapped_column(String(100))
    firmware: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100))
    purpose: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(100))
    rack: Mapped[str | None] = mapped_column(String(50))
    room: Mapped[str | None] = mapped_column(String(50))
    datacenter: Mapped[str | None] = mapped_column(String(100))
    owner: Mapped[str | None] = mapped_column(String(100))
    responsible_person: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))
    team: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="Active", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Device {self.hostname}>"


class IPHistory(Base):
    """Model for IP address assignment history."""
    __tablename__ = "ip_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(39), nullable=False, index=True)
    ip_id: Mapped[int | None] = mapped_column(ForeignKey("ip_addresses.id", ondelete="SET NULL"))
    previous_hostname: Mapped[str | None] = mapped_column(String(255))
    previous_assigned_to: Mapped[str | None] = mapped_column(String(255))
    previous_status: Mapped[str | None] = mapped_column(String(20))
    change_reason: Mapped[str | None] = mapped_column(String(255))
    changed_by: Mapped[str | None] = mapped_column(String(100))
    change_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<IPHistory {self.ip_address} - {self.change_date}>"
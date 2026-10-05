"""ORM models for the IPAM application."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.security import utcnow

ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"

# --------------------------------------------------------------------------- #
# CMDB vocabularies
#
# These drive both the dropdowns in the device form and the Literal types in
# app/schemas.py, so adding a value here is a one-line change.
# --------------------------------------------------------------------------- #
DEVICE_CLASSES = (
    "Server", "Virtual Machine", "Switch", "Router", "Firewall", "Access Point",
    "Workstation", "Laptop", "Mobile Device", "Storage", "Printer", "UPS", "PDU",
    "KVM", "Load Balancer", "Camera", "IoT Device", "Other",
)

LIFECYCLE_STATUSES = (
    "Planned", "In Service", "In Stock", "Under Repair", "Retired",
    "Decommissioned", "Disposed",
)

CRITICALITY_LEVELS = ("Critical", "High", "Medium", "Low")

DATA_CLASSIFICATIONS = ("Public", "Internal", "Confidential", "Restricted")

COMPLIANCE_STATUSES = ("Compliant", "Non-Compliant", "In Review", "Exempt", "Not Applicable")

PATCH_STATUSES = ("Up to Date", "Pending", "Overdue", "In Progress", "Not Applicable")

ANTIVIRUS_STATUSES = ("Protected", "Outdated", "Disabled", "Not Installed", "Unknown")

BACKUP_STATUSES = ("Success", "Failed", "Never Backed Up", "In Progress", "Not Required")

DISCOVERY_SOURCES = ("Manual", "Network Scan", "Agent", "Import", "API", "Hypervisor")

# --------------------------------------------------------------------------- #
# Network / IP vocabularies
# --------------------------------------------------------------------------- #
ADDRESS_FAMILIES = ("IPv4", "IPv6")

NETWORK_ENVIRONMENTS = (
    "Production", "Staging", "Development", "Test", "QA",
    "Disaster Recovery", "Management",
)

NETWORK_STATUSES = ("Active", "Planned", "Reserved", "Decommissioned")

ALLOCATION_METHODS = (
    "Manual", "Static Reservation", "DHCP", "DHCP Reservation",
    "IPv6 SLAAC", "Cluster VIP",
)


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
    mac_addresses: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    hostname: Mapped[str | None] = mapped_column(String(255))
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    device_type: Mapped[str | None] = mapped_column(String(50), index=True)
    interface_name: Mapped[str | None] = mapped_column(String(50))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), index=True)
    # Declared subnet this address belongs to. network_segment stays as free
    # text for legacy rows; subnet_id is the authoritative link.
    subnet_id: Mapped[int | None] = mapped_column(ForeignKey("networks.id", ondelete="SET NULL"), index=True)
    # Which address reaches the device: a multi-homed host has several, but
    # only one management address.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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

    # ---------------- Assignment governance ---------------- #
    allocation_method: Mapped[str] = mapped_column(String(30), default="Manual", nullable=False)
    reverse_dns: Mapped[str | None] = mapped_column(String(255))
    redundancy_group: Mapped[str | None] = mapped_column(String(100))
    shared_with: Mapped[str | None] = mapped_column(Text)
    status_reason: Mapped[str | None] = mapped_column(String(255))
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(100))
    discovery_source: Mapped[str] = mapped_column(String(30), default="Manual", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    device: Mapped["Device | None"] = relationship(back_populates="ip_addresses")
    subnet: Mapped["Network | None"] = relationship(back_populates="ip_addresses")

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

    # ---------------- Addressing ---------------- #
    # A subnet-level gateway belongs to the network, not to each host address.
    address_family: Mapped[str] = mapped_column(String(5), default="IPv4", index=True, nullable=False)
    gateway: Mapped[str | None] = mapped_column(String(39))
    dns_servers: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    domain_name: Mapped[str | None] = mapped_column(String(255))
    vrf: Mapped[str | None] = mapped_column(String(100))
    dhcp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dhcp_server: Mapped[str | None] = mapped_column(String(100))
    dhcp_range_start: Mapped[str | None] = mapped_column(String(39))
    dhcp_range_end: Mapped[str | None] = mapped_column(String(39))

    # ---------------- VLAN span ---------------- #
    vlan_name: Mapped[str | None] = mapped_column(String(100))
    vlan_range_start: Mapped[str | None] = mapped_column(String(39))
    vlan_range_end: Mapped[str | None] = mapped_column(String(39))

    # ---------------- Ownership & governance ---------------- #
    environment: Mapped[str | None] = mapped_column(String(30), index=True)
    tenant: Mapped[str | None] = mapped_column(String(100))
    criticality: Mapped[str] = mapped_column(String(20), default="Medium", index=True, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    cost_center: Mapped[str | None] = mapped_column(String(50))
    site_code: Mapped[str | None] = mapped_column(String(50))
    datacenter: Mapped[str | None] = mapped_column(String(100))

    # ---------------- Lifecycle ---------------- #
    status: Mapped[str] = mapped_column(String(20), default="Active", index=True, nullable=False)
    tags: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    # Aggregation relationship: a child subnet points at the supernet it sits in.
    parent_network_id: Mapped[int | None] = mapped_column(
        ForeignKey("networks.id", ondelete="SET NULL"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    parent_network: Mapped["Network | None"] = relationship(
        remote_side="Network.id", back_populates="child_networks", foreign_keys=[parent_network_id],
    )
    child_networks: Mapped[list["Network"]] = relationship(
        back_populates="parent_network", foreign_keys=[parent_network_id], order_by="Network.cidr",
    )
    ip_addresses: Mapped[list["IPAddress"]] = relationship(
        back_populates="subnet", order_by="IPAddress.ip_address",
    )

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

    # ---------------- CMDB: identification ---------------- #
    # asset_tag is the canonical CMDB key: it is what audits, finance and
    # discovery tools reconcile against, so it carries a unique index.
    asset_tag: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    inventory_id: Mapped[str | None] = mapped_column(String(64), index=True)
    instance_id: Mapped[str | None] = mapped_column(String(100))
    barcode: Mapped[str | None] = mapped_column(String(64))
    device_uuid: Mapped[str | None] = mapped_column(String(64))

    # ---------------- CMDB: classification ---------------- #
    device_class: Mapped[str] = mapped_column(String(50), default="Other", index=True, nullable=False)
    device_subtype: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    part_number: Mapped[str | None] = mapped_column(String(100))
    chassis_type: Mapped[str | None] = mapped_column(String(50))
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---------------- CMDB: lifecycle ---------------- #
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="In Service", index=True, nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    warranty_start: Mapped[date | None] = mapped_column(Date)
    warranty_end: Mapped[date | None] = mapped_column(Date)
    install_date: Mapped[date | None] = mapped_column(Date)
    decommission_date: Mapped[date | None] = mapped_column(Date)
    last_audit_date: Mapped[date | None] = mapped_column(Date)
    next_review_date: Mapped[date | None] = mapped_column(Date)

    # ---------------- CMDB: financial ---------------- #
    purchase_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    po_number: Mapped[str | None] = mapped_column(String(50))
    contract_number: Mapped[str | None] = mapped_column(String(50))
    supplier: Mapped[str | None] = mapped_column(String(100))
    lease_end: Mapped[date | None] = mapped_column(Date)

    # ---------------- CMDB: organisation ---------------- #
    cost_center: Mapped[str | None] = mapped_column(String(50), index=True)
    business_unit: Mapped[str | None] = mapped_column(String(100))
    asset_custodian: Mapped[str | None] = mapped_column(String(100))
    managed_by: Mapped[str | None] = mapped_column(String(100))
    approver: Mapped[str | None] = mapped_column(String(100))

    # ---------------- CMDB: location / placement ---------------- #
    site_code: Mapped[str | None] = mapped_column(String(50), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    state_province: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(100))
    floor: Mapped[str | None] = mapped_column(String(20))
    rack_position: Mapped[int | None] = mapped_column(Integer)
    rack_units: Mapped[int | None] = mapped_column(Integer)
    slot_position: Mapped[str | None] = mapped_column(String(50))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    timezone: Mapped[str | None] = mapped_column(String(50))

    # ---------------- CMDB: technical specification ---------------- #
    bios_version: Mapped[str | None] = mapped_column(String(100))
    os_version: Mapped[str | None] = mapped_column(String(100))
    cpu_model: Mapped[str | None] = mapped_column(String(100))
    cpu_count: Mapped[int | None] = mapped_column(Integer)
    memory_gb: Mapped[int | None] = mapped_column(Integer)
    storage_gb: Mapped[int | None] = mapped_column(Integer)
    power_draw_w: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(8, 2))
    mac_addresses: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    # Hypervisor / enclosure containment: a virtual machine points at its host,
    # a blade at its chassis. Self-referencing so the hierarchy stays walkable.
    parent_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )

    # ---------------- CMDB: network identity ---------------- #
    primary_ip: Mapped[str | None] = mapped_column(String(39))
    management_ip: Mapped[str | None] = mapped_column(String(39))
    network_segment: Mapped[str | None] = mapped_column(String(100))
    dns_domain: Mapped[str | None] = mapped_column(String(255))
    port_count: Mapped[int | None] = mapped_column(Integer)
    uplink_speed_mbps: Mapped[int | None] = mapped_column(Integer)

    # ---------------- CMDB: service & resilience ---------------- #
    service_name: Mapped[str | None] = mapped_column(String(100))
    service_group: Mapped[str | None] = mapped_column(String(100))
    application: Mapped[str | None] = mapped_column(String(100))
    redundancy_group: Mapped[str | None] = mapped_column(String(100))
    cluster_name: Mapped[str | None] = mapped_column(String(100))
    rto_minutes: Mapped[int | None] = mapped_column(Integer)
    rpo_minutes: Mapped[int | None] = mapped_column(Integer)
    maintenance_window: Mapped[str | None] = mapped_column(String(100))
    support_ticket: Mapped[str | None] = mapped_column(String(50))
    change_reference: Mapped[str | None] = mapped_column(String(50))

    # ---------------- CMDB: security & compliance ---------------- #
    criticality: Mapped[str] = mapped_column(String(20), default="Medium", index=True, nullable=False)
    data_classification: Mapped[str | None] = mapped_column(String(30))
    compliance_status: Mapped[str | None] = mapped_column(String(30))
    compliance_framework: Mapped[str | None] = mapped_column(String(100))
    authorized_use: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    patch_status: Mapped[str | None] = mapped_column(String(30))
    patch_due_date: Mapped[date | None] = mapped_column(Date)
    antivirus_status: Mapped[str | None] = mapped_column(String(30))
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    monitoring_agent: Mapped[str | None] = mapped_column(String(100))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    backup_status: Mapped[str | None] = mapped_column(String(30))
    last_backup_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovery_source: Mapped[str] = mapped_column(String(30), default="Manual", nullable=False)
    last_cmdb_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    ip_addresses: Mapped[list["IPAddress"]] = relationship(
        back_populates="device",
        order_by="IPAddress.ip_address",
        lazy="selectin",
    )
    parent_device: Mapped["Device | None"] = relationship(
        remote_side="Device.id", back_populates="child_devices", foreign_keys=[parent_device_id],
    )
    child_devices: Mapped[list["Device"]] = relationship(
        back_populates="parent_device", foreign_keys=[parent_device_id], order_by="Device.hostname",
    )

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
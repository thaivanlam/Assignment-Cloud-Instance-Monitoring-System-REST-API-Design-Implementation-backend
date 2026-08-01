import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    CLIENT_MANAGER = "CLIENT_MANAGER"


class ContractPlan(str, enum.Enum):
    BASIC = "BASIC"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


class InstanceType(str, enum.Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class InstanceStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class AlertType(str, enum.Enum):
    CPU_HIGH = "CPU_HIGH"
    ERROR_DETECTED = "ERROR_DETECTED"
    LONG_STOPPED = "LONG_STOPPED"


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.CLIENT_MANAGER)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    clients: Mapped[list["Client"]] = relationship(back_populates="manager")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    clientName: Mapped[str] = mapped_column(String(100), nullable=False)
    contractPlan: Mapped[ContractPlan] = mapped_column(Enum(ContractPlan), nullable=False)
    managerId: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    manager: Mapped["Member"] = relationship(back_populates="clients")
    instances: Mapped[list["Instance"]] = relationship(back_populates="client")
    cost_snapshots: Mapped[list["CostSnapshot"]] = relationship(back_populates="client")


class Instance(Base):
    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instanceName: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    instanceType: Mapped[InstanceType] = mapped_column(Enum(InstanceType), nullable=False)
    status: Mapped[InstanceStatus] = mapped_column(
        Enum(InstanceStatus), nullable=False, default=InstanceStatus.STOPPED
    )
    cpuUsage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    monthlyCost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    clientId: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    launchedAt: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    client: Mapped["Client"] = relationship(back_populates="instances")
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="instance", cascade="all, delete-orphan"
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instanceId: Mapped[int] = mapped_column(ForeignKey("instances.id"), nullable=False)
    alertType: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    isResolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detectedAt: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    resolvedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    instance: Mapped["Instance"] = relationship(back_populates="alerts")


class CostSnapshot(Base):
    __tablename__ = "cost_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    clientId: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    snapshotMonth: Mapped[str] = mapped_column(String(7), nullable=False)  # "YYYY-MM"
    totalCost: Mapped[float] = mapped_column(Float, nullable=False)
    instanceCount: Mapped[int] = mapped_column(Integer, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="cost_snapshots")

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .agent import AgentSettings
from .mobile_web import MobileWebSettings
from .remote_auth import RemoteAuthSettings
from .value_objects import (
    CheckInterval,
    ConfirmationId,
    DataDirectory,
    LimitsSettings,
    Money,
    NotificationSettings,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
    TelegramBotSettings,
)


class BookingStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class Booking:
    booking_id: str
    platform: Platform
    product_type: ProductType
    confirmation_id: ConfirmationId
    property: Property
    stay_dates: StayDates
    room_type: RoomType
    baseline_price: Money
    refundability: RefundabilityPolicy
    registered_at: datetime
    status: BookingStatus = BookingStatus.ACTIVE
    # None is reserved for rows registered before schema v5 (ADR-014); new
    # registrations always carry occupancy via create().
    occupancy: Occupancy | None = None

    @classmethod
    def create(
        cls,
        platform: Platform,
        product_type: ProductType,
        confirmation_id: ConfirmationId,
        property: Property,
        stay_dates: StayDates,
        room_type: RoomType,
        baseline_price: Money,
        refundability: RefundabilityPolicy,
        registered_at: datetime,
        occupancy: Occupancy,
    ) -> Booking:
        return cls(
            booking_id=str(uuid.uuid4()),
            platform=platform,
            product_type=product_type,
            confirmation_id=confirmation_id,
            property=property,
            stay_dates=stay_dates,
            room_type=room_type,
            baseline_price=baseline_price,
            refundability=refundability,
            registered_at=registered_at,
            occupancy=occupancy,
        )


@dataclass
class Config:
    check_interval: CheckInterval
    data_directory: DataDirectory
    notification_settings: NotificationSettings
    loaded_at: datetime
    extraction_settings: dict[str, str] = field(default_factory=dict)
    agent_settings: AgentSettings = field(default_factory=AgentSettings)
    telegram_bot_settings: TelegramBotSettings = field(default_factory=TelegramBotSettings)
    limits_settings: LimitsSettings = field(default_factory=LimitsSettings)
    mobile_web_settings: MobileWebSettings = field(default_factory=MobileWebSettings)
    remote_auth_settings: RemoteAuthSettings = field(default_factory=RemoteAuthSettings)

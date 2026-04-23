"""Entitlement evaluation for overlay availability, activation, and preview gating."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from lap_coach_logger.overlays.models import OverlayAccessState, OverlayDefinition, OverlayPremiumTier


@dataclass(slots=True, frozen=True)
class OverlayEntitlementContext:
    premium_active: bool = False
    feature_flags: frozenset[str] = field(default_factory=frozenset)
    internal_access: bool = False
    dev_mode: bool = False
    subscription_tier: str = ""
    license_features: frozenset[str] = field(default_factory=frozenset)


@dataclass(slots=True, frozen=True)
class OverlayEntitlementResult:
    access_state: OverlayAccessState
    tier: OverlayPremiumTier
    reason: str = ""
    upsell_message: str = ""
    access_badge: str = ""
    can_select: bool = True
    can_preview: bool = True
    can_view_settings: bool = True
    can_activate: bool = False
    visible_in_catalog: bool = True

    @property
    def entitled(self) -> bool:
        return self.can_activate

    @property
    def accessible(self) -> bool:
        return self.access_state == "accessible"

    @property
    def locked(self) -> bool:
        return self.access_state in {"preview_only", "locked"}

    @property
    def hidden(self) -> bool:
        return self.access_state == "hidden"

    @property
    def preview_only(self) -> bool:
        return self.access_state == "preview_only"


class OverlayEntitlementResolver(Protocol):
    def evaluate(
        self,
        definition: OverlayDefinition,
        *,
        context: OverlayEntitlementContext | None = None,
    ) -> OverlayEntitlementResult:
        ...

    def resolve(
        self,
        definition: OverlayDefinition,
        *,
        context: OverlayEntitlementContext | None = None,
    ) -> OverlayEntitlementResult:
        ...


class StaticOverlayEntitlementResolver:
    """Local overlay entitlement service without payment or remote validation concerns."""

    def evaluate(
        self,
        definition: OverlayDefinition,
        *,
        context: OverlayEntitlementContext | None = None,
    ) -> OverlayEntitlementResult:
        account = context or OverlayEntitlementContext()
        requirement = definition.entitlement
        tier = requirement.tier

        if definition.internal or tier == "internal" or definition.availability_status == "internal":
            if self._has_internal_access(account, requirement.feature_key):
                return OverlayEntitlementResult(
                    access_state="accessible",
                    tier="internal",
                    access_badge="DEV",
                    can_select=True,
                    can_preview=definition.capabilities.preview_supported or bool(definition.preview_asset_ref),
                    can_view_settings=True,
                    can_activate=True,
                    visible_in_catalog=True,
                )
            return OverlayEntitlementResult(
                access_state="hidden",
                tier="internal",
                reason="Developer-only overlay",
                access_badge="DEV",
                can_select=False,
                can_preview=False,
                can_view_settings=False,
                can_activate=False,
                visible_in_catalog=False,
            )

        if tier == "free":
            return OverlayEntitlementResult(
                access_state="accessible",
                tier="free",
                access_badge="FREE",
                can_select=True,
                can_preview=definition.capabilities.preview_supported or bool(definition.preview_asset_ref),
                can_view_settings=True,
                can_activate=True,
                visible_in_catalog=True,
            )

        if self._has_premium_access(account, requirement.feature_key):
            return OverlayEntitlementResult(
                access_state="accessible",
                tier="premium",
                access_badge="PRO",
                can_select=True,
                can_preview=definition.capabilities.preview_supported or bool(definition.preview_asset_ref),
                can_view_settings=True,
                can_activate=True,
                visible_in_catalog=True,
            )

        preview_available = requirement.allow_preview_without_access and (
            definition.capabilities.preview_supported or bool(definition.preview_asset_ref)
        )
        settings_visible = requirement.allow_settings_without_access
        reason = self._locked_reason(requirement.feature_key)
        upsell = "Upgrade to premium to activate this overlay."
        return OverlayEntitlementResult(
            access_state="preview_only" if preview_available or settings_visible else "locked",
            tier="premium",
            reason=reason,
            upsell_message=upsell,
            access_badge="PRO",
            can_select=True,
            can_preview=preview_available,
            can_view_settings=settings_visible,
            can_activate=False,
            visible_in_catalog=True,
        )

    def resolve(
        self,
        definition: OverlayDefinition,
        *,
        context: OverlayEntitlementContext | None = None,
    ) -> OverlayEntitlementResult:
        return self.evaluate(definition, context=context)

    @staticmethod
    def _has_premium_access(context: OverlayEntitlementContext, feature_key: str) -> bool:
        if context.premium_active or context.subscription_tier.lower() == "premium":
            return True
        if feature_key and feature_key in context.feature_flags:
            return True
        if feature_key and feature_key in context.license_features:
            return True
        return False

    @staticmethod
    def _has_internal_access(context: OverlayEntitlementContext, feature_key: str) -> bool:
        if context.internal_access or context.dev_mode:
            return True
        if feature_key and feature_key in context.feature_flags:
            return True
        if feature_key and feature_key in context.license_features:
            return True
        return False

    @staticmethod
    def _locked_reason(feature_key: str) -> str:
        if feature_key:
            return f"Requires entitlement '{feature_key}'"
        return "Premium subscription required"

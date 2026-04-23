"""Runtime state controller for mounted overlay instances and previews."""

from __future__ import annotations

import uuid

from lap_coach_logger.overlays.models import (
    OverlayInstance,
    OverlayPreviewSession,
    OverlayRuntimeState,
    OverlayStateDocument,
    utc_now_iso,
)


class OverlayRuntimeController:
    """Tracks runtime state without depending on any Qt window implementation."""

    def __init__(self) -> None:
        self._runtime_states: dict[str, OverlayRuntimeState] = {}
        self._preview_sessions: dict[str, OverlayPreviewSession] = {}

    def sync_document(self, document: OverlayStateDocument) -> None:
        instance_map = document.instance_map()
        preset_map = document.preset_map()
        active_preset = preset_map.get(document.active_preset_id)
        mounted_ids = set(active_preset.instance_ids) if active_preset else set()

        for instance_id in list(self._runtime_states):
            if instance_id not in instance_map:
                self._runtime_states.pop(instance_id, None)

        for instance_id in mounted_ids:
            instance = instance_map.get(instance_id)
            if not instance:
                continue
            state = self._runtime_states.get(instance_id)
            if state is None:
                self._runtime_states[instance_id] = OverlayRuntimeState(
                    instance_id=instance.instance_id,
                    overlay_id=instance.overlay_id,
                    preset_id=instance.preset_id,
                    mode="live",
                    status="mounted" if instance.enabled else "hidden",
                    visible=instance.enabled,
                )
            else:
                state.preset_id = instance.preset_id
                state.status = "mounted" if instance.enabled else "hidden"
                state.visible = instance.enabled
                state.updated_at_utc = utc_now_iso()

        for instance_id, state in list(self._runtime_states.items()):
            if instance_id not in mounted_ids:
                state.status = "inactive"
                state.visible = False
                state.updated_at_utc = utc_now_iso()

    def start_preview(self, overlay_id: str, *, settings: dict[str, object] | None = None) -> OverlayPreviewSession:
        preview = OverlayPreviewSession(
            preview_id=f"preview-{uuid.uuid4().hex[:10]}",
            overlay_id=overlay_id,
            settings=dict(settings or {}),
        )
        self._preview_sessions[preview.preview_id] = preview
        return preview

    def stop_preview(self, preview_id: str) -> None:
        self._preview_sessions.pop(preview_id, None)

    def runtime_states(self) -> tuple[OverlayRuntimeState, ...]:
        return tuple(self._runtime_states.values())

    def preview_sessions(self) -> tuple[OverlayPreviewSession, ...]:
        return tuple(self._preview_sessions.values())

    def runtime_state_for(self, instance_id: str) -> OverlayRuntimeState | None:
        return self._runtime_states.get(instance_id)

    def set_instance_visibility(self, instance: OverlayInstance, *, visible: bool) -> None:
        state = self._runtime_states.get(instance.instance_id)
        if state is None:
            self._runtime_states[instance.instance_id] = OverlayRuntimeState(
                instance_id=instance.instance_id,
                overlay_id=instance.overlay_id,
                preset_id=instance.preset_id,
                mode="live",
                status="mounted" if visible else "hidden",
                visible=visible,
            )
            return
        state.status = "mounted" if visible else "hidden"
        state.visible = visible
        state.updated_at_utc = utc_now_iso()

    def set_instance_error(self, instance: OverlayInstance, message: str) -> None:
        state = self._runtime_states.get(instance.instance_id)
        if state is None:
            self._runtime_states[instance.instance_id] = OverlayRuntimeState(
                instance_id=instance.instance_id,
                overlay_id=instance.overlay_id,
                preset_id=instance.preset_id,
                mode="live",
                status="error",
                visible=False,
                error=message,
            )
            return
        state.status = "error"
        state.error = message
        state.visible = False
        state.updated_at_utc = utc_now_iso()


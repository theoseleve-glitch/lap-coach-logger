"""Mode engine — runtime-selectable behaviour profiles.

Each :class:`~lap_coach_logger.core.modes.base.Mode` binds four
orthogonal dimensions of session behaviour:

- Overlay preset (T112)
- Coaching verbosity (T113)
- Strategy assumptions / safety margins (T114)
- Session tagging (T115)

Concrete modes (T107-T110) are class-level constants — stateless,
shareable. T111's :class:`ModeEngine` instantiates each once and
dispatches on ``id``.
"""

from lap_coach_logger.core.modes.base import Mode

__all__ = ["Mode"]

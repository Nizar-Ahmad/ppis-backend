"""Public Pydantic schema namespace, grouped by domain source modules."""

from app.schemas.common import *  # noqa: F403
from app.schemas.auth import *  # noqa: F403
from app.schemas.otp import *  # noqa: F403
from app.schemas.sessions import *  # noqa: F403
from app.schemas.profile import *  # noqa: F403
from app.schemas.feedback import *  # noqa: F403
from app.schemas.analytics import *  # noqa: F403
from app.schemas.productivity import *  # noqa: F403
from app.schemas.google_health import *  # noqa: F403
from app.schemas.admin import *  # noqa: F403

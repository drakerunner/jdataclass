from typing import Any, Callable, Optional

JSON = dict[str, Any]
JPROPERTY_INITIALIZER = Callable[..., Any]
JPATH_TOKEN = tuple[str, Optional[JPROPERTY_INITIALIZER]]
JPATH_TOKENS = tuple[JPATH_TOKEN]

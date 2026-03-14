from enum import Enum


class Page(str, Enum):
    DASHBOARD = "Dashboard"
    CALENDAR = "Calendar"
    SETTINGS = "Settings"

"""Konfiguration des optionalen Standard-Webzugriffs."""

from pydantic import BaseModel


class WebAccessConfig(BaseModel):
    enabled: bool = False

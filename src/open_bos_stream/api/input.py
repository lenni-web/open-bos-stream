"""
Input API

Liefert alle verfügbaren Input-Plugins.
"""

from __future__ import annotations

from fastapi import APIRouter

from open_bos_stream.stream.inputs import registry
from open_bos_stream.core.installation import installation_profile

router = APIRouter(
    prefix="/stream",
    tags=["Stream Inputs"],
)


@router.get("/inputs")
async def list_inputs():

    inputs = registry.metadata()
    if installation_profile() == "server":
        return [
            item
            for item in inputs
            if item["type"] != "v4l2"
        ]
    return inputs

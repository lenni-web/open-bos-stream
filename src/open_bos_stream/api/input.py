"""
Input API

Liefert alle verfügbaren Input-Plugins.
"""

from __future__ import annotations

from fastapi import APIRouter

from open_bos_stream.stream.inputs import registry

router = APIRouter(
    prefix="/stream",
    tags=["Stream Inputs"],
)


@router.get("/inputs")
async def list_inputs():

    return registry.metadata()

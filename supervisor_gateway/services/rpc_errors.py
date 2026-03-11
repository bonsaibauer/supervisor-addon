from __future__ import annotations

import xmlrpc.client

from fastapi import HTTPException


def raise_http_from_rpc(error: Exception) -> None:
    if isinstance(error, xmlrpc.client.Fault):
        if error.faultCode == 10:
            raise HTTPException(status_code=404, detail=error.faultString)
        raise HTTPException(status_code=400, detail=error.faultString)
    if isinstance(error, xmlrpc.client.ProtocolError):
        raise HTTPException(
            status_code=502,
            detail=f"rpc protocol error {error.errcode}: {error.errmsg}",
        )
    raise HTTPException(status_code=502, detail=str(error))


from fastapi import APIRouter

from brikta_ia import __version__

router = APIRouter(tags=["saúde"])


@router.get("/health")
def health() -> dict[str, str]:
    """Healthcheck público. Não toca em banco nem em provedores."""
    return {"status": "ok", "versao": __version__}

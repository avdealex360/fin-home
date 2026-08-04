"""Кошелёк USDC (ERC-20): компактные настройки + кэшированный баланс для шапки."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ws_id
from app.db import get_db
from app.services import crypto_wallet

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


class WalletBody(BaseModel):
    """Все поля опциональны: None = «не трогать».

    Пустая строка в `address` выключает фичу, пустой `etherscan_api_key`
    оставляет сохранённый ключ. `notify_user_id = 0` — писать всем, кто привязан
    к Telegram.
    """

    address: str | None = None
    etherscan_api_key: str | None = None
    threshold: str | None = None
    notify_user_id: int | None = None


@router.get("")
def get_wallet(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    """Статус из кэша — фоновый воркер обновляет его раз в 5 минут."""
    return crypto_wallet.status(db, ws)


@router.post("")
def save_wallet(
    body: WalletBody,
    db: Session = Depends(get_db),
    ws: int = Depends(ws_id),
):
    """Доступно любому участнику workspace: кошелёк и ключ живут в его пределах."""
    try:
        return crypto_wallet.save_config(
            db,
            ws,
            address=body.address,
            api_key=body.etherscan_api_key,
            threshold=body.threshold,
            notify_user_id=body.notify_user_id,
        )
    except crypto_wallet.WalletError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/refresh")
def refresh_wallet(db: Session = Depends(get_db), ws: int = Depends(ws_id)):
    """Обновить баланс сейчас же (переворот баланса в шапке, кнопка в настройках).

    Уведомление отсюда тоже может уйти — правило «раз в месяц» одно на всех.
    """
    return crypto_wallet.check(db, ws)

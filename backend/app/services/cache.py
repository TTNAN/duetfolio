"""Result cache for the expensive portfolio computations.

Holdings are replayed from the full transaction log on every request —
simple and never stale, but it repeats identical work on each page view.
Instead of persisting partial snapshots (which can go subtly wrong when an
old trade is edited), results are memoized by a *data version*:

- every ORM flush that adds/changes/deletes a Transaction, PriceSnapshot,
  CashFlow or Instrument bumps `app_meta.data_version` in the same DB
  transaction (bulk deletes too);
- a cached result is reused only while the version, base currency, cost
  method and FX rates are unchanged.

Because the version lives in the database, invalidation also works with
several uvicorn workers or after a restart.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from app.models.models import AppMeta, CashFlow, Instrument, PriceSnapshot, Transaction

_TRACKED = (Transaction, PriceSnapshot, CashFlow, Instrument)
_KEY = "data_version"
_lock = threading.Lock()
_store: "OrderedDict[tuple, object]" = OrderedDict()
_MAX = 64


def _bump(session: Session) -> None:
    conn = session.connection()
    res = conn.execute(update(AppMeta.__table__).where(AppMeta.__table__.c.key == _KEY)
                       .values(value=AppMeta.__table__.c.value + 1))
    if res.rowcount == 0:
        conn.execute(AppMeta.__table__.insert().values(key=_KEY, value=1))


@event.listens_for(Session, "before_flush")
def _on_flush(session, flush_context, instances):
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if isinstance(obj, _TRACKED):
            if obj in session.dirty and not session.is_modified(obj):
                continue
            _bump(session)
            return


@event.listens_for(Session, "do_orm_execute")
def _on_bulk(orm_execute_state):
    # query(...).delete() / bulk update bypass before_flush
    if orm_execute_state.is_delete or orm_execute_state.is_update:
        mappers = orm_execute_state.all_mappers
        if any(m.class_ in _TRACKED for m in mappers):
            _bump(orm_execute_state.session)


def data_version(db: Session) -> int:
    v = db.execute(select(AppMeta.value).where(AppMeta.key == _KEY)).scalar()
    return int(v or 0)


def get_or_compute(key: tuple, fn):
    with _lock:
        if key in _store:
            _store.move_to_end(key)
            return _store[key]
    val = fn()
    with _lock:
        _store[key] = val
        _store.move_to_end(key)
        while len(_store) > _MAX:
            _store.popitem(last=False)
    return val


def clear() -> None:
    with _lock:
        _store.clear()

"""Medical communications queue (plan step 37, contract 2.10.0).

Rules
-----
C-1  Messages are durable rows. `client_message_id` makes a resend after a lost response idempotent.
C-2  Transmission is computed from the clock whenever the queue is read or written. One message is sent at a time
     (`transmit_seconds`), urgent before routine among the messages waiting, and only while the link is up.
     Arrival is `transmit start + transmit_seconds + one_way_delay_seconds`.
C-3  A message already sent keeps travelling during an outage. Messages created during an outage wait in
     `queued` and are sent when the link returns.
C-4  Only the receiving side may acknowledge, and only after delivery (409 NOT_DELIVERED). Acknowledgement is
     idempotent.
The delay and link are a fictional simulation; there is no real ground link.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError, not_found
from . import access
from .audit import audit

LINK_ID = "LINK-HAB-01-GROUND"
PRIORITY_ORDER = {"urgent": 0, "routine": 1}


def config(fx: dict) -> dict:
    return fx["comms"]


def link(db: Session) -> m.CommsLink:
    row = db.get(m.CommsLink, LINK_ID)
    if row is None:
        row = m.CommsLink(link_id=LINK_ID, state="up", changed_at=utcnow() - timedelta(days=1), changed_by="system",
                          reason="Initial state")
        db.add(row)
        db.flush()
    return row


def advance(db: Session, fx: dict, now: datetime | None = None) -> bool:
    """Rules C-2 and C-3. Returns True when anything changed (the caller commits)."""
    now = now or utcnow()
    cfg = config(fx)
    tx, delay = timedelta(seconds=cfg["transmit_seconds"]), timedelta(seconds=cfg["one_way_delay_seconds"])
    changed = False
    lk = link(db)
    if lk.state == "up":
        sent = db.scalars(select(m.CommsMessage).where(m.CommsMessage.transmit_at.is_not(None))).all()
        channel_free = max([s.transmit_at + tx for s in sent], default=lk.changed_at)
        channel_free = max(channel_free, lk.changed_at)
        waiting = db.scalars(select(m.CommsMessage).where(m.CommsMessage.status == "queued")).all()
        waiting.sort(key=lambda x: (PRIORITY_ORDER[x.priority], x.created_at, x.message_id))
        while waiting:
            # The channel starts its next transmission when it is free and a message exists; among the messages
            # that exist at that moment, urgent goes first.
            start = max(channel_free, min(w.created_at for w in waiting))
            if start > now:
                break
            eligible = [w for w in waiting if w.created_at <= start]
            nxt = min(eligible, key=lambda x: (PRIORITY_ORDER[x.priority], x.created_at, x.message_id))
            nxt.status, nxt.transmit_at, nxt.deliver_at = "in_transit", start, start + tx + delay
            channel_free = start + tx
            waiting.remove(nxt)
            changed = True
    for msg in db.scalars(select(m.CommsMessage).where(m.CommsMessage.status == "in_transit",
                                                       m.CommsMessage.deliver_at <= now)):
        msg.status, msg.delivered_at = "delivered", msg.deliver_at
        audit(db, "comms-simulator", "comms.delivered", "comms_message", msg.message_id, msg.case_id,
              direction=msg.direction, priority=msg.priority)
        changed = True
    return changed


def _sync(db: Session, fx: dict) -> None:
    if advance(db, fx):
        db.commit()


def send(db: Session, fx: dict, sender_id: str, direction: str, priority: str, subject: str, body: str,
         case_id: str | None = None, client_message_id: str | None = None,
         check_role: bool = True) -> tuple[m.CommsMessage, bool]:
    _sync(db, fx)
    if client_message_id:
        dup = db.scalars(select(m.CommsMessage).where(m.CommsMessage.client_message_id == client_message_id)).first()
        if dup is not None:
            return dup, True
    _, role = access.resolve(db, fx, sender_id)
    if check_role:
        access.require(db, fx, sender_id, f"comms.send_{direction}", "comms_message", client_message_id or "new",
                       case_id)
    if case_id is not None and db.get(m.MedicalCase, case_id) is None:
        raise not_found("Case", case_id)
    now = utcnow()
    msg = m.CommsMessage(message_id=m.new_id("MSG"), client_message_id=client_message_id, direction=direction,
                         priority=priority, sender_id=sender_id, sender_role=role,
                         recipient_role="flight_surgeon" if direction == "to_ground" else "crew", case_id=case_id,
                         subject=subject, body=body, status="queued", created_at=now)
    db.add(msg)
    db.flush()
    audit(db, sender_id, "comms.queued", "comms_message", msg.message_id, case_id, direction=direction,
          priority=priority, link_state=link(db).state)
    advance(db, fx, now)
    db.commit()
    return msg, False


def get(db: Session, fx: dict, message_id: str) -> m.CommsMessage:
    _sync(db, fx)
    msg = db.get(m.CommsMessage, message_id)
    if msg is None:
        raise not_found("Message", message_id)
    return msg


def listing(db: Session, fx: dict, direction: str | None = None, status: str | None = None,
            case_id: str | None = None) -> list[m.CommsMessage]:
    _sync(db, fx)
    q = select(m.CommsMessage)
    if direction:
        q = q.where(m.CommsMessage.direction == direction)
    if status:
        q = q.where(m.CommsMessage.status == status)
    if case_id:
        q = q.where(m.CommsMessage.case_id == case_id)
    rows = db.scalars(q).all()
    return sorted(rows, key=lambda x: (PRIORITY_ORDER[x.priority], x.created_at, x.message_id))


def acknowledge(db: Session, fx: dict, message_id: str, actor_id: str) -> m.CommsMessage:
    msg = get(db, fx, message_id)
    access.require(db, fx, actor_id, f"comms.acknowledge_{msg.direction}", "comms_message", msg.message_id,
                   msg.case_id)
    if msg.status == "acknowledged":
        return msg
    if msg.status != "delivered":
        raise ApiError(409, "NOT_DELIVERED", "The message has not arrived yet, so it cannot be acknowledged.",
                       {"message_id": message_id, "status": msg.status,
                        "deliver_at": msg.deliver_at.isoformat() if msg.deliver_at else None})
    msg.status, msg.acknowledged_at, msg.acknowledged_by = "acknowledged", utcnow(), actor_id
    audit(db, actor_id, "comms.acknowledged", "comms_message", msg.message_id, msg.case_id)
    db.commit()
    return msg


def set_link(db: Session, fx: dict, state: str, actor_id: str, reason: str) -> m.CommsLink:
    access.require(db, fx, actor_id, "comms.link", "comms_link", LINK_ID)
    _sync(db, fx)  # deliver/transmit everything due before the change
    lk = link(db)
    if lk.state != state:
        lk.state, lk.changed_at, lk.changed_by, lk.reason = state, utcnow(), actor_id, reason
        lk.outage_count = (lk.outage_count or 0) + (1 if state == "down" else 0)
        audit(db, actor_id, f"comms.link_{state}", "comms_link", LINK_ID, reason=reason,
              note="Simulated communication link state.")
    advance(db, fx)
    db.commit()
    return lk

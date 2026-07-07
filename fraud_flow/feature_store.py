from __future__ import annotations

import json
from collections.abc import Iterable
from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import islice
from typing import DefaultDict

import redis

from .schema import FeatureLookup, TransactionEvent


class RollingAmountTracker:
    def __init__(self, window_hours: int) -> None:
        self.window_hours = window_hours
        self.values: DefaultDict[str, deque[tuple[int, float]]] = defaultdict(deque)
        self.running_sum: DefaultDict[str, float] = defaultdict(float)

    def _evict(self, key: str, current_step: int) -> None:
        queue = self.values[key]
        cutoff = current_step - self.window_hours
        while queue and queue[0][0] < cutoff:
            _, amount = queue.popleft()
            self.running_sum[key] -= amount
        if not queue:
            self.running_sum.pop(key, None)

    def count(self, key: str, current_step: int) -> int:
        self._evict(key, current_step)
        return len(self.values[key])

    def mean(self, key: str, current_step: int) -> float:
        self._evict(key, current_step)
        count = len(self.values[key])
        if count == 0:
            return 0.0
        return self.running_sum[key] / count

    def observe(self, key: str, current_step: int, amount: float) -> None:
        self._evict(key, current_step)
        self.values[key].append((current_step, amount))
        self.running_sum[key] += amount


@dataclass
class EntityRiskSnapshot:
    total_count: int
    labeled_count: int
    fraud_count: int

    @property
    def fraud_rate(self) -> float:
        if self.labeled_count == 0:
            return 0.0
        return self.fraud_count / self.labeled_count


class HistoricalRiskTracker:
    def __init__(self) -> None:
        self.total: DefaultDict[str, int] = defaultdict(int)
        self.labeled: DefaultDict[str, int] = defaultdict(int)
        self.fraud: DefaultDict[str, int] = defaultdict(int)

    def snapshot(self, key: str) -> EntityRiskSnapshot:
        return EntityRiskSnapshot(self.total[key], self.labeled[key], self.fraud[key])

    def rate(self, key: str) -> float:
        snap = self.snapshot(key)
        return snap.fraud_rate

    def observe_activity(self, key: str) -> None:
        self.total[key] += 1

    def observe_feedback(self, key: str, label: int | None) -> None:
        if label is None:
            return
        self.labeled[key] += 1
        if label:
            self.fraud[key] += 1

    def observe(self, key: str, label: int | None) -> None:
        self.observe_activity(key)
        self.observe_feedback(key, label)


class FeatureStore:
    """Feature store + risk registry that powers both training and real-time lookup."""

    def __init__(self) -> None:
        self.card_24h = RollingAmountTracker(window_hours=24)
        self.card_7d = RollingAmountTracker(window_hours=24 * 7)
        self.device_24h = RollingAmountTracker(window_hours=24)
        self.location_24h = RollingAmountTracker(window_hours=24)
        self.merchant_24h = RollingAmountTracker(window_hours=24)

        self.location_risk = HistoricalRiskTracker()
        self.ip_risk = HistoricalRiskTracker()
        self.merchant_risk = HistoricalRiskTracker()
        self.card_risk = HistoricalRiskTracker()
        self.device_risk = HistoricalRiskTracker()

    def lookup(self, event: TransactionEvent) -> FeatureLookup:
        return FeatureLookup(
            tx_count_24h=self.card_24h.count(event.card_id, event.step),
            avg_amount_7d=round(self.card_7d.mean(event.card_id, event.step), 6),
            device_tx_count_24h=self.device_24h.count(event.device_id, event.step),
            location_tx_count_24h=self.location_24h.count(event.location_id, event.step),
            merchant_tx_count_24h=self.merchant_24h.count(event.merchant_id, event.step),
            location_fraud_rate=round(self.location_risk.rate(event.location_id), 6),
            ip_fraud_rate=round(self.ip_risk.rate(event.ip_address), 6),
            merchant_fraud_rate=round(self.merchant_risk.rate(event.merchant_id), 6),
        )

    def observe_activity(self, event: TransactionEvent) -> None:
        self.card_24h.observe(event.card_id, event.step, event.amount)
        self.card_7d.observe(event.card_id, event.step, event.amount)
        self.device_24h.observe(event.device_id, event.step, event.amount)
        self.location_24h.observe(event.location_id, event.step, event.amount)
        self.merchant_24h.observe(event.merchant_id, event.step, event.amount)

        self.location_risk.observe_activity(event.location_id)
        self.ip_risk.observe_activity(event.ip_address)
        self.merchant_risk.observe_activity(event.merchant_id)
        self.card_risk.observe_activity(event.card_id)
        self.device_risk.observe_activity(event.device_id)

    def observe_feedback(self, event: TransactionEvent, label: int | None) -> None:
        self.location_risk.observe_feedback(event.location_id, label)
        self.ip_risk.observe_feedback(event.ip_address, label)
        self.merchant_risk.observe_feedback(event.merchant_id, label)
        self.card_risk.observe_feedback(event.card_id, label)
        self.device_risk.observe_feedback(event.device_id, label)

    def observe(self, event: TransactionEvent, label: int | None) -> None:
        self.observe_activity(event)
        self.observe_feedback(event, label)

    def warm_start(self, events: Iterable[TransactionEvent]) -> None:
        for event in events:
            self.observe(event, event.is_fraud)

    def card_summary(self, card_id: str, current_step: int) -> dict[str, float | int]:
        snapshot = self.card_risk.snapshot(card_id)
        return {
            "tx_count_24h": self.card_24h.count(card_id, current_step),
            "avg_amount_7d": round(self.card_7d.mean(card_id, current_step), 2),
            "historical_tx_count": snapshot.total_count,
            "labeled_tx_count": snapshot.labeled_count,
            "historical_fraud_count": snapshot.fraud_count,
            "historical_fraud_rate": round(snapshot.fraud_rate, 4),
        }

    def device_summary(self, device_id: str, current_step: int) -> dict[str, float | int | bool]:
        snapshot = self.device_risk.snapshot(device_id)
        tx_count_24h = self.device_24h.count(device_id, current_step)
        return {
            "device_tx_count_24h": tx_count_24h,
            "historical_tx_count": snapshot.total_count,
            "labeled_tx_count": snapshot.labeled_count,
            "historical_fraud_rate": round(snapshot.fraud_rate, 4),
            "is_new_device": snapshot.total_count == 0,
            "needs_step_up": tx_count_24h == 0 or snapshot.fraud_rate >= 0.1,
        }

    def merchant_summary(self, merchant_id: str, current_step: int) -> dict[str, float | int]:
        snapshot = self.merchant_risk.snapshot(merchant_id)
        return {
            "merchant_tx_count_24h": self.merchant_24h.count(merchant_id, current_step),
            "historical_tx_count": snapshot.total_count,
            "labeled_tx_count": snapshot.labeled_count,
            "historical_fraud_count": snapshot.fraud_count,
            "merchant_fraud_rate": round(snapshot.fraud_rate, 4),
        }

    def ip_summary(self, ip_address: str) -> dict[str, float | int | bool]:
        snapshot = self.ip_risk.snapshot(ip_address)
        blacklisted = snapshot.fraud_count >= 3 and snapshot.fraud_rate >= 0.2
        return {
            "historical_tx_count": snapshot.total_count,
            "labeled_tx_count": snapshot.labeled_count,
            "historical_fraud_count": snapshot.fraud_count,
            "ip_fraud_rate": round(snapshot.fraud_rate, 4),
            "blacklisted": blacklisted,
        }


class RedisFeatureStore:
    """Redis-backed feature store used by the online scoring flow."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    def flush(self) -> None:
        self.client.flushdb()

    def lookup(self, event: TransactionEvent) -> FeatureLookup:
        return FeatureLookup(
            tx_count_24h=self._window_count(self._timeline_key("card", event.card_id), event.step, 24),
            avg_amount_7d=round(self._window_average(self._timeline_key("card", event.card_id), event.step, 24 * 7), 6),
            device_tx_count_24h=self._window_count(self._timeline_key("device", event.device_id), event.step, 24),
            location_tx_count_24h=self._window_count(self._timeline_key("location", event.location_id), event.step, 24),
            merchant_tx_count_24h=self._window_count(self._timeline_key("merchant", event.merchant_id), event.step, 24),
            location_fraud_rate=round(self._fraud_rate("location", event.location_id), 6),
            ip_fraud_rate=round(self._fraud_rate("ip", event.ip_address), 6),
            merchant_fraud_rate=round(self._fraud_rate("merchant", event.merchant_id), 6),
        )

    def observe_activity(self, event: TransactionEvent) -> None:
        encoded_member = self._encode_member(event.tx_id, event.amount)
        pipe = self.client.pipeline(transaction=False)
        pipe.zadd(self._timeline_key("card", event.card_id), {encoded_member: event.step})
        pipe.zadd(self._timeline_key("device", event.device_id), {encoded_member: event.step})
        pipe.zadd(self._timeline_key("location", event.location_id), {encoded_member: event.step})
        pipe.zadd(self._timeline_key("merchant", event.merchant_id), {encoded_member: event.step})
        pipe.hincrby(self._risk_key("location", event.location_id), "total_count", 1)
        pipe.hincrby(self._risk_key("ip", event.ip_address), "total_count", 1)
        pipe.hincrby(self._risk_key("merchant", event.merchant_id), "total_count", 1)
        pipe.hincrby(self._risk_key("card", event.card_id), "total_count", 1)
        pipe.hincrby(self._risk_key("device", event.device_id), "total_count", 1)
        pipe.execute()

    def observe_feedback(self, event: TransactionEvent, label: int | None) -> None:
        if label is None:
            return
        pipe = self.client.pipeline(transaction=False)
        pipe.hincrby(self._risk_key("location", event.location_id), "labeled_count", 1)
        pipe.hincrby(self._risk_key("ip", event.ip_address), "labeled_count", 1)
        pipe.hincrby(self._risk_key("merchant", event.merchant_id), "labeled_count", 1)
        pipe.hincrby(self._risk_key("card", event.card_id), "labeled_count", 1)
        pipe.hincrby(self._risk_key("device", event.device_id), "labeled_count", 1)
        if label:
            pipe.hincrby(self._risk_key("location", event.location_id), "fraud_count", 1)
            pipe.hincrby(self._risk_key("ip", event.ip_address), "fraud_count", 1)
            pipe.hincrby(self._risk_key("merchant", event.merchant_id), "fraud_count", 1)
            pipe.hincrby(self._risk_key("card", event.card_id), "fraud_count", 1)
            pipe.hincrby(self._risk_key("device", event.device_id), "fraud_count", 1)
        pipe.execute()

    def observe(self, event: TransactionEvent, label: int | None) -> None:
        self.observe_activity(event)
        self.observe_feedback(event, label)

    def warm_start(self, events: Iterable[TransactionEvent], *, batch_size: int = 2000) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size phải lớn hơn 0.")

        iterator = iter(events)
        while True:
            batch = list(islice(iterator, batch_size))
            if not batch:
                return

            pipe = self.client.pipeline(transaction=False)
            for event in batch:
                encoded_member = self._encode_member(event.tx_id, event.amount)
                pipe.zadd(self._timeline_key("card", event.card_id), {encoded_member: event.step})
                pipe.zadd(self._timeline_key("device", event.device_id), {encoded_member: event.step})
                pipe.zadd(self._timeline_key("location", event.location_id), {encoded_member: event.step})
                pipe.zadd(self._timeline_key("merchant", event.merchant_id), {encoded_member: event.step})
                pipe.hincrby(self._risk_key("location", event.location_id), "total_count", 1)
                pipe.hincrby(self._risk_key("ip", event.ip_address), "total_count", 1)
                pipe.hincrby(self._risk_key("merchant", event.merchant_id), "total_count", 1)
                pipe.hincrby(self._risk_key("card", event.card_id), "total_count", 1)
                pipe.hincrby(self._risk_key("device", event.device_id), "total_count", 1)

                label = event.is_fraud
                if label is None:
                    continue

                pipe.hincrby(self._risk_key("location", event.location_id), "labeled_count", 1)
                pipe.hincrby(self._risk_key("ip", event.ip_address), "labeled_count", 1)
                pipe.hincrby(self._risk_key("merchant", event.merchant_id), "labeled_count", 1)
                pipe.hincrby(self._risk_key("card", event.card_id), "labeled_count", 1)
                pipe.hincrby(self._risk_key("device", event.device_id), "labeled_count", 1)
                if label:
                    pipe.hincrby(self._risk_key("location", event.location_id), "fraud_count", 1)
                    pipe.hincrby(self._risk_key("ip", event.ip_address), "fraud_count", 1)
                    pipe.hincrby(self._risk_key("merchant", event.merchant_id), "fraud_count", 1)
                    pipe.hincrby(self._risk_key("card", event.card_id), "fraud_count", 1)
                    pipe.hincrby(self._risk_key("device", event.device_id), "fraud_count", 1)

            pipe.execute()

    def card_summary(self, card_id: str, current_step: int) -> dict[str, float | int]:
        total, labeled, fraud = self._counts("card", card_id)
        return {
            "tx_count_24h": self._window_count(self._timeline_key("card", card_id), current_step, 24),
            "avg_amount_7d": round(self._window_average(self._timeline_key("card", card_id), current_step, 24 * 7), 2),
            "historical_tx_count": total,
            "labeled_tx_count": labeled,
            "historical_fraud_count": fraud,
            "historical_fraud_rate": round(self._safe_rate(labeled, fraud), 4),
        }

    def device_summary(self, device_id: str, current_step: int) -> dict[str, float | int | bool]:
        total, labeled, fraud = self._counts("device", device_id)
        tx_count_24h = self._window_count(self._timeline_key("device", device_id), current_step, 24)
        return {
            "device_tx_count_24h": tx_count_24h,
            "historical_tx_count": total,
            "labeled_tx_count": labeled,
            "historical_fraud_rate": round(self._safe_rate(labeled, fraud), 4),
            "is_new_device": total == 0,
            "needs_step_up": tx_count_24h == 0 or self._safe_rate(labeled, fraud) >= 0.1,
        }

    def merchant_summary(self, merchant_id: str, current_step: int) -> dict[str, float | int]:
        total, labeled, fraud = self._counts("merchant", merchant_id)
        return {
            "merchant_tx_count_24h": self._window_count(self._timeline_key("merchant", merchant_id), current_step, 24),
            "historical_tx_count": total,
            "labeled_tx_count": labeled,
            "historical_fraud_count": fraud,
            "merchant_fraud_rate": round(self._safe_rate(labeled, fraud), 4),
        }

    def ip_summary(self, ip_address: str) -> dict[str, float | int | bool]:
        total, labeled, fraud = self._counts("ip", ip_address)
        rate = self._safe_rate(labeled, fraud)
        return {
            "historical_tx_count": total,
            "labeled_tx_count": labeled,
            "historical_fraud_count": fraud,
            "ip_fraud_rate": round(rate, 4),
            "blacklisted": fraud >= 3 and rate >= 0.2,
        }

    def _window_count(self, key: str, current_step: int, window_hours: int) -> int:
        return int(self.client.zcount(key, current_step - window_hours, current_step))

    def _window_average(self, key: str, current_step: int, window_hours: int) -> float:
        members = self.client.zrangebyscore(key, current_step - window_hours, current_step)
        if not members:
            return 0.0
        amounts = [self._decode_member(member)["amount"] for member in members]
        return sum(amounts) / len(amounts)

    def _fraud_rate(self, entity: str, entity_id: str) -> float:
        _, labeled, fraud = self._counts(entity, entity_id)
        return self._safe_rate(labeled, fraud)

    def _counts(self, entity: str, entity_id: str) -> tuple[int, int, int]:
        payload = self.client.hgetall(self._risk_key(entity, entity_id))
        total = int(payload.get("total_count", 0))
        labeled = int(payload.get("labeled_count", 0))
        fraud = int(payload.get("fraud_count", 0))
        return total, labeled, fraud

    @staticmethod
    def _safe_rate(total: int, fraud: int) -> float:
        if total == 0:
            return 0.0
        return fraud / total

    @staticmethod
    def _encode_member(tx_id: str, amount: float) -> str:
        return json.dumps({"tx_id": tx_id, "amount": amount}, separators=(",", ":"))

    @staticmethod
    def _decode_member(member: str) -> dict[str, float | str]:
        return json.loads(member)

    @staticmethod
    def _timeline_key(entity: str, entity_id: str) -> str:
        return f"timeline:{entity}:{entity_id}"

    @staticmethod
    def _risk_key(entity: str, entity_id: str) -> str:
        return f"risk:{entity}:{entity_id}"

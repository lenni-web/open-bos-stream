"""Verbindung zum MQTT-Broker auf demselben Server."""

from __future__ import annotations

import logging
from collections.abc import Callable

import paho.mqtt.client as mqtt

from open_bos_stream.dji.config import DjiConfig
from open_bos_stream.dji.telemetry import SUBSCRIPTIONS


logger = logging.getLogger(__name__)


class BrokerClient:
    """Abonniert die Gerätethemen und sendet die Antworten zurück."""

    def __init__(self, config: DjiConfig, handler: Callable[[str, bytes], list[tuple[str, str]]]) -> None:
        self.config = config
        self.handler = handler
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="open-bos-server")
        self.client.username_pw_set(config.server_username, config.server_password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.on_connect = self._connect
        self.client.on_disconnect = self._disconnect
        self.client.on_message = self._message

    def start(self) -> None:
        # connect_async: Die Anwendung startet auch ohne laufenden Broker.
        self.client.connect_async(self.config.broker_host, self.config.broker_port)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()

    def _connect(self, client, _userdata, _flags, reason, _properties) -> None:
        if reason.is_failure:
            logger.warning("MQTT-Broker lehnt die Anmeldung ab: %s", reason)
            return
        self.connected = True
        client.subscribe([(topic, 0) for topic in SUBSCRIPTIONS])
        logger.info("Mit dem MQTT-Broker verbunden (DJI Cloud API).")

    def _disconnect(self, *_args) -> None:
        self.connected = False

    def _message(self, client, _userdata, message) -> None:
        try:
            for topic, payload in self.handler(message.topic, message.payload):
                client.publish(topic, payload)
        except Exception:  # Eine Nachricht darf den Empfang nie beenden.
            logger.exception("DJI-Nachricht auf %s nicht verarbeitet.", message.topic)

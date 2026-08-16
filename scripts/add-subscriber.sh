#!/usr/bin/env bash
# Добавление абонента в базу ядра. Ключи должны совпадать с config/ue.yaml,
# иначе аутентификация закончится MAC failure.
#
# Использование: scripts/add-subscriber.sh [IMSI]

set -euo pipefail

IMSI="${1:-999700000000001}"
KEY="${KEY:-465B5CE8B199B49FAA5F0A2EE238A6BC}"
OPC="${OPC:-E8ED289DEBA952E4283B54E88E6183CA}"
MONGO_CONTAINER="${MONGO_CONTAINER:-o5g-mongo}"

echo "добавляю абонента ${IMSI} ..."

docker exec -i "${MONGO_CONTAINER}" mongosh --quiet open5gs <<EOF
db.subscribers.replaceOne(
  { imsi: "${IMSI}" },
  {
    imsi: "${IMSI}",
    subscribed_rau_tau_timer: 12,
    network_access_mode: 0,
    subscriber_status: 0,
    access_restriction_data: 32,
    slice: [
      {
        sst: 1,
        default_indicator: true,
        session: [
          {
            name: "internet",
            type: 3,
            qos: {
              index: 9,
              arp: { priority_level: 8, pre_emption_capability: 1, pre_emption_vulnerability: 1 }
            },
            ambr: {
              downlink: { value: 1, unit: 3 },
              uplink:   { value: 1, unit: 3 }
            }
          }
        ]
      }
    ],
    ambr: {
      downlink: { value: 1, unit: 3 },
      uplink:   { value: 1, unit: 3 }
    },
    security: {
      k: "${KEY}",
      amf: "8000",
      opc: "${OPC}",
      op: null
    },
    schema_version: 1,
    __v: 0
  },
  { upsert: true }
);

const doc = db.subscribers.findOne({ imsi: "${IMSI}" });
print(doc ? "абонент в базе: " + doc.imsi : "ОШИБКА: абонент не создан");
EOF

echo "готово"

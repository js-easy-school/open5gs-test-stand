# Open5GS Test Stand: QA-автоматизация 5G Core

Портфолио-проект для вакансии QA automation в телеком-команде. Стенд поднимает
настоящие сетевые функции 5G SA из Open5GS, эмулирует gNB и UE через UERANSIM и
проверяет регистрацию абонента, PDU-сессию, user plane и негативные сценарии.

Это не мок API: тесты работают с Linux TUN, SCTP/NGAP, PFCP, GTP-U, HTTP/2 SBI и
MongoDB. Физический радиоуровень не моделируется — UERANSIM эмулирует протоколы
выше PHY.

## Что внутри

- Open5GS `v2.8.0`, собранный из официального commit
  `157f611a530e292e40ec50f9d23f0ef5d4fcd6a6`;
- UERANSIM `v3.3.0`, commit
  `6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156`;
- 11 функций ядра: NRF, SCP, AMF, SMF, UPF, AUSF, UDM, UDR, PCF, BSF, NSSF;
- MongoDB с профилями абонентов;
- сценарии pytest и pytest-bdd на русском Gherkin;
- статическая проверка адресов, образов и конфигурации до запуска Docker;
- GitHub Actions и GitLab CI с JUnit/HTML-отчётами и логами при падении.

## Схема

```text
UE (UERANSIM) --RLS--> gNB --SCTP/NGAP--> AMF --HTTP/2 SBI--> NRF/SCP/AUSF/UDM/UDR/PCF/NSSF
      |                                                   |
      +-- TUN/PDU --GTP-U--> UPF <--PFCP-- SMF -----------+
                               |
                            internet APN
```

Сеть контейнеров: `10.33.0.0/24`. UE получает адрес из
`10.45.0.0/16`. Тестовый PLMN — `999/70`, slice — `SST 1`.

## Требования к хосту

- Linux x86_64;
- Docker Engine с Compose v2;
- доступный `/dev/net/tun`;
- поддержка SCTP в ядре (`/proc/net/sctp/assocs`);
- примерно 4 ГБ свободной RAM и 8 ГБ диска на первую сборку.

Обычный WSL 1 не подходит. Для WSL 2 виртуализация должна быть включена в
BIOS/UEFI, а ядро WSL обязано предоставлять TUN и SCTP. Перед долгой сборкой
проверка окружения объяснит проблему конкретно:

```bash
./scripts/preflight.sh
```

## Быстрый старт

```bash
git clone https://github.com/js-easy-school/open5gs-test-stand.git
cd open5gs-test-stand
cp .env.example .env

python3 scripts/validate-configs.py
./scripts/up.sh
./scripts/test.sh -m "not slow"
./scripts/down.sh --purge
```

Первый `up.sh` собирает Open5GS и UERANSIM из закреплённых исходников, поэтому
занимает дольше последующих запусков. Успех считается только после реального
статуса `RM-REGISTERED`; один лишь HTTP 200 от NRF недостаточен.

Полный прогон, включая перерегистрацию:

```bash
./scripts/test.sh
```

Отчёты появляются в `reports/junit.xml` и `reports/report.html`.

## BDD-сценарии

`features/registration.feature` — исполняемая спецификация. Она связывает
требование с кодом и содержит три основных потока:

1. зарегистрированный абонент получает PDU-сессию и доступ к шлюзу UPF;
2. неизвестный IMSI получает отказ;
3. заведённый IMSI с неверным ключом не проходит аутентификацию.

Для негативных тестов создаётся отдельный временный контейнер UE. Это исключает
ложный результат из-за логов предыдущего запуска или повторного использования
уже зарегистрированного абонента.

## Полезные команды при расследовании

```bash
docker compose ps --all
docker compose logs --tail=100 amf ausf udm gnb ue
docker exec o5g-ue nr-cli imsi-999700000000001 -e status
docker exec o5g-mongo mongosh open5gs --quiet --eval 'db.subscribers.find().pretty()'
./scripts/logs.sh
```

| Симптом | Что проверить первым |
|---|---|
| preflight сообщает про TUN | `ls -l /dev/net/tun`, затем `sudo modprobe tun` |
| preflight сообщает про SCTP | `sudo modprobe sctp`, наличие `lksctp-tools` |
| gNB не соединяется с AMF | PLMN/TAC в `gnb.yaml`, SCTP 38412, логи `amf` и `gnb` |
| UE остаётся `RM-DEREGISTERED` | IMSI/K/OPc, запись MongoDB, логи AUSF/UDM/AMF |
| PDU-сессия есть, ping не идёт | TUN `ogstun`, PFCP, GTP-U и `net.ipv4.ip_forward` |
| NF отсутствует в NRF | её SBI-адрес, URI NRF/SCP и контейнерные логи |

## Почему прежний запуск не стартовал

Проблемы ядра Linux проверяются скриптом `preflight.sh`, но конкретный запуск
GitHub Actions может не дойти даже до Linux runner. В таком случае в интерфейсе
Actions нет шагов job, а есть сообщение уровня аккаунта/billing. Исправление YAML,
Docker или Open5GS не может разблокировать runner — сначала владелец аккаунта
должен восстановить доступ к Actions, после чего CI выполнит реальные шаги
`validate` и `e2e`.

## Документация

- `docs/test-plan.md` — требования, покрытие, критерии входа/выхода и риски;
- `features/registration.feature` — исполняемые acceptance-сценарии;
- `.github/workflows/ci.yml` — проверка конфигураций и полный e2e;
- `.gitlab-ci.yml` — эквивалентный пайплайн для Linux shell runner.

Проект предназначен для обучения и демонстрации QA-навыков. Он не является
production-конфигурацией оператора связи.

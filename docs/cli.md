# CLI Reference

The `sharklocal` CLI is invoked as a Python module and provides discovery, testing, monitoring, and direct command capabilities.

```bash
python -m sharklocal <IP_ADDRESS> [OPTIONS]
```

---

## Discovery Probe

Identify which mapping configuration works for your vacuum model. This is the recommended first step for new hardware:

```bash
python -m sharklocal <IP_ADDRESS> --probe
```

---

## Compatibility Testing

Run non-destructive tests (Status, Events, Info) to verify support for local REST and MQTT features:

```bash
python -m sharklocal <IP_ADDRESS> --test
```

Run all tests, including destructive commands (Start, Stop, Dock), and automatically generate a compatibility matrix for contributing back to the project:

```bash
python -m sharklocal <IP_ADDRESS> --test-all --save-report
```

---

## Real-Time Monitoring

Stream real-time status updates via MQTT. This is the best way to verify that a vacuum is correctly publishing its state:

```bash
python -m sharklocal <IP_ADDRESS> --monitor
```

---

## Direct Commands

Send a specific command via a chosen transport (defaults to `mqtt`):

```bash
python -m sharklocal <IP_ADDRESS> --cmd dock --transport mqtt
```

Available commands: `start`, `stop`, `dock`, `status`, `events`, `info`.

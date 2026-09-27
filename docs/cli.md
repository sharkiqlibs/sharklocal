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

Available commands: `start`, `stop`, `dock`, `status`, `events`, `info`, `find`, `suction-eco`, `suction-normal`, `suction-max`, `recharge-resume-on`, `recharge-resume-off`, `evac-resume-on`, `evac-resume-off`.

The settings and `find` commands exist only in the MQTT mapping. While `--monitor` is running, any status update that carries map data prints an extra `[MAP]` line with the grid size, the number of cleaned-path points, the robot's pose and the room names (persisted map only).

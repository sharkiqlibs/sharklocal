import asyncio
import argparse
import sys
import os
from datetime import datetime
from typing import Optional, Any, Dict, List

from . import (
    RESTVacuumClient,
    MQTTVacuumClient,
    load_rest_mapping,
    load_mqtt_mapping,
    list_rest_mappings,
    list_mqtt_mappings,
    VacuumClient,
    VacuumStatus,
    VacuumMode,
    SharklocalError
)

# Actions metadata for help and validation
VALID_COMMANDS = ["start", "stop", "dock", "status", "events", "info"]
ACTION_MAP = {
    "status": "get_status",
    "start": "start_cleaning",
    "stop": "stop",
    "dock": "go_home",
    "events": "get_events",
    "info": "get_robot_id",
}

def print_status(status: VacuumStatus, prefix: str = "[STATUS]"):
    """Helper to format status output."""
    bat = f"{status.battery_level}%" if status.battery_level is not None else "N/A"
    chg = f" (Charging)" if status.charging else ""
    mode_str = status.mode.value if hasattr(status.mode, "value") else str(status.mode)
    print(f"\r{prefix} Mode: {mode_str:20} | Battery: {bat}{chg}", end="", flush=True)

async def run_command(host: str, cmd: str, transport: str):
    """Execute a single specific command."""
    action = ACTION_MAP[cmd]
    
    if transport == "rest":
        for m_id in list_rest_mappings():
            try:
                mapping = load_rest_mapping(m_id)
                if action not in mapping.actions: continue
                client = RESTVacuumClient(host, mapping)
                print(f"Sending {cmd} via REST ({m_id})...")
                res = await asyncio.wait_for(client.call(action), timeout=5.0)
                print(f"Response: {res}")
                await client.close()
                return
            except Exception as e:
                print(f"REST {m_id} failed: {e}")
    else:
        for m_id in list_mqtt_mappings():
            try:
                mapping = load_mqtt_mapping(m_id)
                if action not in mapping.actions: continue
                client = MQTTVacuumClient(host, mapping)
                print(f"Sending {cmd} via MQTT ({m_id})...")
                res = await asyncio.wait_for(client.call(action), timeout=5.0)
                print(f"Response: {res}")
                return
            except Exception as e:
                print(f"MQTT {m_id} failed: {e}")

async def monitor_vacuum(host: str):
    """Start real-time monitoring via MQTT."""
    print(f"Starting real-time monitoring for {host} (Ctrl+C to stop)...")
    try:
        mqtt_maps = list_mqtt_mappings()
        if not mqtt_maps:
            print("No MQTT mappings found.")
            return
            
        async with VacuumClient(host, mqtt_mappings=mqtt_maps[0]) as vacuum:
            vacuum.on_status_update(lambda s: print_status(s))
            await vacuum.start_monitoring()
            while True:
                await asyncio.sleep(1)
    except Exception as e:
        print(f"\nMonitoring failed: {e}")

async def run_probe(host: str):
    """Perform a connectivity probe to identify working mappings."""
    print(f"\n>>> PROBING: {host}")
    
    async with VacuumClient(
        host,
        rest_mappings=list_rest_mappings(),
        mqtt_mappings=list_mqtt_mappings()
    ) as vacuum:
        print("Testing candidates...")
        try:
            res = await asyncio.wait_for(vacuum.probe(), timeout=15.0)
            
            print(f"\nResults:")
            print(f"  REST Transport: {'PINNED [' + res.rest_mapping + ']' if res.has_rest else 'FAILED'}")
            print(f"  MQTT Transport: {'PINNED [' + res.mqtt_mapping + ']' if res.has_mqtt else 'FAILED'}")
            print(f"  Primary Conn:   {vacuum.via}")
            
            if not res.is_connected:
                print("\nSuggestion: Verify that the vacuum is online and reachable at this IP.")
            elif res.has_rest:
                print("\nHint: Run with --test to see detailed device information.")
        except asyncio.TimeoutError:
            print("\nError: Probe timed out. The device may be offline or blocking local ports.")
        except Exception as e:
            print(f"\nError: {e}")

async def run_test_logic(host: str, test_commands: bool = False) -> Dict[str, Any]:
    """Run compatibility suite and return structured results for reporting."""
    print(f"\n>>> TESTING: {host}")
    
    results = {
        "host": host,
        "model": None,
        "fw": None,
        "rest": {},
        "mqtt": {}
    }

    # 1. REST Probe
    for m_id in list_rest_mappings():
        try:
            mapping = load_rest_mapping(m_id)
            client = RESTVacuumClient(host, mapping)
            print(f"  [REST] Mapping: {m_id}")
            results["rest"][m_id] = {"actions": {}, "modes": set()}
            
            for raw_m, norm_m in mapping.mode_map.items():
                results["rest"][m_id]["modes"].add(norm_m)
                if norm_m == "docked" and raw_m == "ready":
                    results["rest"][m_id]["modes"].add("idle")

            actions_to_test = [
                ("Status", "get_status"),
                ("Explore", "explore"),
                ("Events", "get_events"),
                ("Info", "get_robot_id"),
                ("Wi-Fi", "get_wifi_status")
            ]
            
            for label, action in actions_to_test:
                if action not in mapping.actions: continue
                try:
                    res = await asyncio.wait_for(client.call(action), timeout=5.0)
                    results["rest"][m_id]["actions"][action] = True
                    detail = ""
                    if action == "get_status":
                        detail = f" (Mode: {res.mode}, Bat: {res.battery_level}%, Chg: {res.charging})"
                    elif action == "get_robot_id":
                        detail = f" (FW: {res.firmware}, MAC: {res.mac_address})"
                        results["fw"] = res.firmware
                        results["model"] = res.raw.get("robot_model")
                    elif action == "get_wifi_status":
                        detail = f" (RSSI: {res.rssi})"
                    elif action == "get_events":
                        detail = f" ({len(res)} events found)"
                    print(f"    - {label:10} ✅ SUCCESS{detail}")
                except Exception as e:
                    results["rest"][m_id]["actions"][action] = False
                    print(f"    - {label:10} ❌ FAILED ({type(e).__name__})")
            await client.close()
        except Exception: pass

    # 2. MQTT Probe
    for m_id in list_mqtt_mappings():
        try:
            mapping = load_mqtt_mapping(m_id)
            client = MQTTVacuumClient(host, mapping)
            print(f"  [MQTT] Mapping: {m_id}")
            results["mqtt"][m_id] = {"actions": {}, "fields": {}, "modes": set()}
            
            for norm_m in mapping.modes.values():
                results["mqtt"][m_id]["modes"].add(norm_m)

            try:
                status = await asyncio.wait_for(client.call("get_status"), timeout=5.0)
                results["mqtt"][m_id]["actions"]["get_status"] = True
                results["mqtt"][m_id]["fields"]["battery"] = status.battery_level is not None
                results["mqtt"][m_id]["fields"]["charging"] = status.charging is not None
                
                bat_support = "✅" if results["mqtt"][m_id]["fields"]["battery"] else "❌"
                chg_support = "✅" if results["mqtt"][m_id]["fields"]["charging"] else "❌"
                print(f"    - Status     ✅ SUCCESS (Mode: {status.mode}, Bat: {status.battery_level}%)")
                print(f"    - Field Audit: Battery: {bat_support} | Charging: {chg_support}")
            except Exception as e:
                results["mqtt"][m_id]["actions"]["get_status"] = False
                print(f"    - Status     ❌ FAILED ({type(e).__name__})")

            for label, action in [("Start", "start_cleaning"), ("Stop", "stop"), ("Dock", "go_home")]:
                if action not in mapping.actions: continue
                if not test_commands:
                    print(f"    - {label:10} ⏭️  SKIPPED")
                    continue
                try:
                    await asyncio.wait_for(client.call(action), timeout=5.0)
                    results["mqtt"][m_id]["actions"][action] = True
                    print(f"    - {label:10} ✅ SUCCESS")
                except Exception as e:
                    results["mqtt"][m_id]["actions"][action] = False
                    print(f"    - {label:10} ❌ FAILED ({type(e).__name__})")
        except Exception: pass
    
    return results

def generate_markdown_report(results: Dict[str, Any]) -> str:
    """Format test results into a compatibility matrix markdown matching the template."""
    model = results["model"] or "{model}"
    
    def check_act(transport: str, action: str):
        for m in results[transport].values():
            if m["actions"].get(action): return "✅"
        return "❌"

    def get_maps(act_or_mode: str, is_mode: bool = False):
        mappings = []
        for m_id, m in results["rest"].items():
            if is_mode:
                if act_or_mode in m["modes"]: mappings.append(f"REST: `{m_id}`")
            else:
                if m["actions"].get(act_or_mode): mappings.append(f"REST: `{m_id}`")
        for m_id, m in results["mqtt"].items():
            if is_mode:
                if act_or_mode in m["modes"]: mappings.append(f"MQTT: `{m_id}`")
            else:
                if m["actions"].get(act_or_mode): mappings.append(f"MQTT: `{m_id}`")
        
        return "<br/> ".join(mappings) if mappings else "None"

    report = f"# {model} — Compatibility Matrix\n\n---\n\n## Actions\n\n"
    report += "| Feature | REST | MQTT | Supported mappings |\n"
    report += "|---------|:----:|:----:|--------------------|\n"
    
    actions = [
        ("Start cleaning", "start_cleaning"),
        ("Stop", "stop"),
        ("Return to dock", "go_home"),
        ("Explore / Map", "explore"),
        ("Get status", "get_status"),
        ("Get event log", "get_events"),
        ("Get robot ID", "get_robot_id"),
        ("Get Wi-Fi status", "get_wifi_status"),
    ]
    for label, act in actions:
        report += f"| {label} | {check_act('rest', act)} | {check_act('mqtt', act)} | {get_maps(act)} |\n"

    report += "\n---\n\n## Status Fields\n\n"
    report += "| Field | REST | MQTT | Supported mappings |\n"
    report += "|-------|:----:|:----:|--------------------|\n"
    
    def check_field(transport: str, field_name: str):
        if transport == "rest":  # pragma: no cover
            return check_act("rest", "get_status")  # pragma: no cover
        for m in results["mqtt"].values():
            if m["fields"].get(field_name): return "✅"
        return "❌"

    report += f"| Operating mode | {check_act('rest', 'get_status')} | {check_act('mqtt', 'get_status')} | {get_maps('get_status')} |\n"
    report += f"| Battery level | {check_act('rest', 'get_status')} | {check_field('mqtt', 'battery')} | {get_maps('get_status')} |\n"
    report += f"| Charging status | {check_act('rest', 'get_status')} | {check_field('mqtt', 'charging')} | {get_maps('get_status')} |\n"

    report += "\n---\n\n## Operating Modes\n\n"
    report += "| Mode | REST | MQTT | Supported mappings |\n"
    report += "|------|:----:|:----:|--------------------|\n"
    
    modes = [
        ("`cleaning`          ", "cleaning"),
        ("`returning_to_dock` ", "returning_to_dock"),
        ("`docking`           ", "docking"),
        ("`docked`            ", "docked"),
        ("`idle`              ", "idle"),
        ("`exploring`         ", "exploring"),
    ]
    
    def check_mode(transport: str, mode: str):
        for m in results[transport].values():
            if m["actions"].get("get_status") and mode in m["modes"]:
                return "✅"
        return "❌"

    for label, mode in modes:
        report += f"| {label} | {check_mode('rest', mode)} | {check_mode('mqtt', mode)} | {get_maps(mode, is_mode=True)} |\n"

    # Known Issues notes
    has_rest = any(any(v for v in m["actions"].values()) for m in results["rest"].values())
    has_mqtt = any(any(v for v in m["actions"].values()) for m in results["mqtt"].values())
    
    if not has_rest or not has_mqtt:
        report += "\n---\n\n## Known Issues / Notes\n"
        if not has_rest and not has_mqtt:
            report += "- **Local Control Disabled:** Both REST and MQTT ports appear locked down or unreachable.\n"
        elif not has_rest:
            report += "- **REST API:** Local REST API (Ports 443/80) is closed or non-responsive.\n"
        elif not has_mqtt:  # pragma: no cover
            report += "- **MQTT:** Local MQTT broker (Port 1883) is closed or unreachable.\n"  # pragma: no cover

    return report

def setup_argparse() -> argparse.ArgumentParser:
    """Configure and return the argument parser."""
    parser = argparse.ArgumentParser(prog="sharklocal", description="SharkLocal CLI Utility")
    parser.add_argument("host", help="IP address of the vacuum")
    parser.add_argument("--cmd", choices=VALID_COMMANDS, help="Execute a specific command")
    parser.add_argument("--transport", choices=["rest", "mqtt"], default="mqtt", help="Transport for single command (default: mqtt)")
    parser.add_argument("--monitor", action="store_true", help="Stream real-time status updates (MQTT)")
    parser.add_argument("--probe", action="store_true", help="Discovery-only probe to identify working mappings")
    parser.add_argument("--test", action="store_true", help="Run non-destructive compatibility tests")
    parser.add_argument("--test-all", action="store_true", help="Run all compatibility tests, including destructive commands")
    parser.add_argument("--save-report", nargs='?', const=True, help="Save result to a markdown compatibility report (optional: filepath)")
    return parser

def save_report(results: Dict[str, Any], save_report_arg: Any):
    """Generate and save the markdown report."""
    report_md = generate_markdown_report(results)
    
    if isinstance(save_report_arg, str):
        filename = save_report_arg
    else:
        model_name = results["model"] or f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        filename = f"{model_name}.md"
    
    with open(filename, "w") as f:
        f.write(report_md)
    print(f"\nReport saved to: {os.path.abspath(filename)}")

def main():
    parser = setup_argparse()
    args = parser.parse_args()

    print("SharkLocal CLI Utility")
    print("======================")
    
    try:
        if args.monitor:
            asyncio.run(monitor_vacuum(args.host))
        elif args.probe:
            asyncio.run(run_probe(args.host))
        elif args.cmd:
            asyncio.run(run_command(args.host, args.cmd, args.transport))
        elif args.test or args.test_all or args.save_report:
            results = asyncio.run(run_test_logic(args.host, test_commands=args.test_all))
            if args.save_report:
                save_report(results, args.save_report)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nFATAL: {e}")
        sys.exit(1)
        
    print("\nDone.")

if __name__ == "__main__":  # pragma: no cover
    main()  # pragma: no cover

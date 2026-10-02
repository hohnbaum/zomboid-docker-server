"""Validate resolved Compose JSON without printing deployment values."""
import json
import sys


def check(value):
    services = value["services"]
    assert {"pz-server", "pz-ops", "pz-discord", "tools", "pz-init"} <= set(services)
    for name, service in services.items():
        assert not service.get("privileged", False), name
        for mount in service.get("volumes", []):
            assert "docker.sock" not in mount.get("source", ""), name
            assert "docker.sock" not in mount.get("target", ""), name
        for port in service.get("ports", []):
            assert name == "pz-server" and port["target"] in (16261, 16262) and port["protocol"] == "udp", name
    assert set(services["pz-ops"]["networks"]) == {"control"}
    assert value["networks"]["control"]["internal"]
    assert services["pz-discord"]["profiles"] == ["discord"]
    assert not services["pz-discord"].get("volumes")
    for service in ("pz-server", "pz-ops", "pz-discord"):
        assert services[service]["cap_drop"] == ["ALL"]
    return True


if __name__ == "__main__":
    check(json.load(sys.stdin))
    print("Compose boundary validation: PASS")

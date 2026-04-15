#!/usr/bin/env python3
"""
topology.py — Custom Mininet Topology for Traffic Monitoring Project
=====================================================================
Topology:
                        [POX Controller]
                               |
              +────────────────+────────────────+
              |                |                |
           [s1]            [s2]            [s3]
           /   \           /   \           /   \
         h1     h2       h3     h4       h5     h6

  - 3 switches, each connected to 2 hosts  (6 hosts total)
  - All switches connected to s1 (star topology)
  - POX controller runs externally on 127.0.0.1:6633

Usage:
  sudo python3 topology.py
  sudo python3 topology.py --test ping       # run pingall test
  sudo python3 topology.py --test iperf      # run iperf test
  sudo python3 topology.py --test both       # run both tests
"""

from mininet.net    import Mininet
from mininet.node   import RemoteController, OVSSwitch
from mininet.topo   import Topo
from mininet.link   import TCLink
from mininet.log    import setLogLevel, info
from mininet.cli    import CLI
import argparse
import time


class MonitorTopo(Topo):
    """
    Custom 3-switch, 6-host topology.

    s1 ── s2
    |  ╲  |
    |   ╲ |
    s3   (all switches connect to POX controller)

    Hosts:
      h1, h2 → s1
      h3, h4 → s2
      h5, h6 → s3
    """

    def build(self):
        # ── Switches ───────────────────────────────────────────────
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")

        # ── Hosts ──────────────────────────────────────────────────
        # Bandwidth & delay set on links for realistic simulation
        h1 = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        h2 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        h3 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")
        h4 = self.addHost("h4", ip="10.0.0.4/24", mac="00:00:00:00:00:04")
        h5 = self.addHost("h5", ip="10.0.0.5/24", mac="00:00:00:00:00:05")
        h6 = self.addHost("h6", ip="10.0.0.6/24", mac="00:00:00:00:00:06")

        # ── Host–Switch Links (10 Mbps, 5ms delay) ─────────────────
        self.addLink(h1, s1, bw=10, delay="5ms")
        self.addLink(h2, s1, bw=10, delay="5ms")
        self.addLink(h3, s2, bw=10, delay="5ms")
        self.addLink(h4, s2, bw=10, delay="5ms")
        self.addLink(h5, s3, bw=10, delay="5ms")
        self.addLink(h6, s3, bw=10, delay="5ms")

        # ── Switch–Switch Links (100 Mbps, 2ms delay) ──────────────
        self.addLink(s1, s2, bw=100, delay="2ms")
        self.addLink(s1, s3, bw=100, delay="2ms")
        self.addLink(s2, s3, bw=100, delay="2ms")


def run_topology(test_mode="cli"):
    """Build the network, connect to POX controller, and run tests."""

    setLogLevel("info")

    topo = MonitorTopo()
    net  = Mininet(
        topo       = topo,
        switch     = OVSSwitch,
        link       = TCLink,
        controller = None,        # no built-in controller
        autoSetMacs = False,
        autoStaticArp = False,
    )

    # Connect to external POX controller
    c0 = net.addController(
        "c0",
        controller = RemoteController,
        ip         = "127.0.0.1",
        port       = 6633,
    )

    info("\n*** Starting network\n")
    net.start()

    info("\n*** Topology Summary:\n")
    info("    Hosts  : %s\n" % " ".join([h.name for h in net.hosts]))
    info("    Switches: %s\n" % " ".join([s.name for s in net.switches]))
    info("    Controller: 127.0.0.1:6633 (POX)\n\n")

    # Give the controller a moment to install flows
    info("*** Waiting 3s for controller to initialize flows…\n")
    time.sleep(3)

    # ── Test Scenarios ──────────────────────────────────────────────────────

    if test_mode in ("ping", "both"):
        scenario_ping(net)

    if test_mode in ("iperf", "both"):
        scenario_iperf(net)

    if test_mode == "cli":
        info("\n*** Entering Mininet CLI  (type 'exit' or Ctrl-D to quit)\n")
        CLI(net)

    info("\n*** Stopping network\n")
    net.stop()


# ── Test Scenario 1: Ping (Latency & Reachability) ──────────────────────────

def scenario_ping(net):
    """
    Test Scenario 1 — Ping Reachability
    ------------------------------------
    • pingAll        : every host pings every other host
    • Selected pairs : same-switch (h1↔h2) and cross-switch (h1↔h6)
    Expected: 0% packet loss; latency ~10ms same-switch, ~20ms cross-switch
    """
    info("\n" + "=" * 60 + "\n")
    info("TEST SCENARIO 1: Ping — Reachability & Latency\n")
    info("=" * 60 + "\n")

    info("--- pingAll (all hosts) ---\n")
    net.pingAll()

    h1 = net.get("h1")
    h2 = net.get("h2")
    h6 = net.get("h6")

    info("\n--- Same-switch latency: h1 → h2 ---\n")
    h1.cmdPrint("ping -c 5 10.0.0.2")

    info("\n--- Cross-switch latency: h1 → h6 ---\n")
    h1.cmdPrint("ping -c 5 10.0.0.6")


# ── Test Scenario 2: iperf (Throughput) ─────────────────────────────────────

def scenario_iperf(net):
    """
    Test Scenario 2 — iperf Throughput
    ------------------------------------
    • Same-switch  : h1 ↔ h2  (expected ≈ 10 Mbps, link capacity)
    • Cross-switch : h1 ↔ h6  (expected slightly lower due to switch hops)
    """
    info("\n" + "=" * 60 + "\n")
    info("TEST SCENARIO 2: iperf — Throughput Measurement\n")
    info("=" * 60 + "\n")

    h1 = net.get("h1")
    h2 = net.get("h2")
    h6 = net.get("h6")

    info("--- Same-switch throughput: h1 ↔ h2 ---\n")
    net.iperf([h1, h2], seconds=10)

    info("\n--- Cross-switch throughput: h1 ↔ h6 ---\n")
    net.iperf([h1, h6], seconds=10)


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mininet Traffic Monitor Topology")
    parser.add_argument("--test",
                        choices=["cli", "ping", "iperf", "both"],
                        default="cli",
                        help="Test mode to run after topology starts (default: cli)")
    args = parser.parse_args()
    run_topology(test_mode=args.test)

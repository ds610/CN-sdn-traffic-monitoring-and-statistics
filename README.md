# SDN Traffic Monitoring and Statistics
### Mininet + POX Controller | OpenFlow 1.0

---

## Problem Statement

Modern networks generate massive amounts of traffic that administrators need to monitor in real time. Traditional networks require per-device SNMP polling with limited visibility. Software-Defined Networking (SDN) enables a **centralized controller** to collect fine-grained, per-flow statistics directly from OpenFlow-enabled switches — giving operators deep visibility into packet counts, byte counts, flow durations, and port-level metrics without touching individual devices.

**This project implements an SDN-based Traffic Monitoring solution using:**
- **Mininet** — for emulating a multi-switch, multi-host network topology
- **POX** — as the OpenFlow controller
- **OpenFlow 1.0** — for explicit flow rule installation and statistics collection

---

## Objectives

| # | Goal |
|---|------|
| 1 | Implement a **learning switch** using MAC address learning and explicit flow rules |
| 2 | Periodically **retrieve flow statistics** (packet count, byte count, duration) from each switch |
| 3 | Retrieve **port-level statistics** (TX/RX bytes and packets per port) |
| 4 | **Log statistics** to console and CSV for offline analysis |
| 5 | Validate behavior with **ping** (latency) and **iperf** (throughput) tests |

---

## Topology

```
              [POX Controller @ 127.0.0.1:6633]
                           |
         +-----------------+-----------------+
         |                 |                 |
       [s1]             [s2]             [s3]
       /   \            /   \            /   \
     h1     h2        h3     h4        h5     h6

  IP:  10.0.0.1  .2     .3    .4      .5    .6
```

- **3 OpenFlow switches** (OVS) connected in a partial mesh
- **6 hosts**, 2 per switch
- Host–switch links: 10 Mbps, 5ms delay
- Switch–switch links: 100 Mbps, 2ms delay

**Design justification:** The partial-mesh topology allows testing both same-switch and cross-switch traffic paths, providing diverse flow patterns for meaningful statistics collection.

---

## SDN Logic & Flow Rule Design

### packet_in Handling
When a packet arrives at a switch with no matching rule, it is sent to the POX controller via a `packet_in` event. The controller:

1. **Learns** the source MAC → input port mapping
2. **Installs a flow rule** if the destination MAC is already known:
   - **Match**: `dl_src` + `dl_dst` + `in_port`
   - **Action**: `output(out_port)`
   - **Idle timeout**: 60s | **Hard timeout**: 300s | **Priority**: 10
3. **Floods** if destination is unknown (standard learning switch behavior)

### Statistics Collection (Periodic Monitoring)
Every **10 seconds**, the controller sends `ofp_stats_request` messages to each connected switch:
- `ofp_flow_stats_request` → per-flow packet/byte/duration counters
- `ofp_port_stats_request` → per-port TX/RX counters

Results are printed to the console and appended to `flow_stats.csv`.

---

## Project Structure

```
sdn-traffic-monitor/
├── traffic_monitor.py   # POX controller (learning switch + stats collection)
├── topology.py          # Mininet custom topology + test scenarios
├── analyze_stats.py     # Offline CSV stats analyzer
├── flow_stats.csv       # Auto-generated during runtime (git-ignored)
└── README.md
```

---

## Setup & Installation

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Ubuntu | 20.04 / 22.04 | — |
| Python | 3.8+ | `sudo apt install python3` |
| Mininet | 2.3+ | See below |
| POX | latest | See below |
| Open vSwitch | 2.13+ | bundled with Mininet |

### Step 1 — Install Mininet

```bash
# Option A: From package (Ubuntu 20.04+)
sudo apt update
sudo apt install mininet

# Option B: From source (recommended)
git clone https://github.com/mininet/mininet.git
cd mininet
sudo util/install.sh -a
```

Verify:
```bash
sudo mn --version
```

### Step 2 — Install POX

```bash
cd ~
git clone https://github.com/noxrepo/pox.git
cd pox
```

### Step 3 — Clone This Repository

```bash
git clone https://github.com/<YOUR_USERNAME>/sdn-traffic-monitor.git
cd sdn-traffic-monitor
```

---

## Execution Steps

> **Important:** You need **two terminal windows** — one for the controller, one for Mininet.

### Terminal 1 — Start the POX Controller

```bash
cd ~/pox
python3 pox.py log.level --DEBUG misc.traffic_monitor
```

> **Note:** Copy `traffic_monitor.py` into `~/pox/pox/misc/` first:
> ```bash
> cp ~/sdn-traffic-monitor/traffic_monitor.py ~/pox/pox/misc/
> ```

You should see:
```
INFO:traffic_monitor:Traffic Monitor launched  (stats interval = 10s)
INFO:traffic_monitor:Traffic Monitor Controller started — waiting for switches…
```

### Terminal 2 — Start the Mininet Topology

**Option A: Interactive CLI mode**
```bash
cd ~/sdn-traffic-monitor
sudo python3 topology.py
```

**Option B: Auto-run ping test**
```bash
sudo python3 topology.py --test ping
```

**Option C: Auto-run iperf test**
```bash
sudo python3 topology.py --test iperf
```

**Option D: Run both test scenarios**
```bash
sudo python3 topology.py --test both
```

---

## Test Scenarios

### Scenario 1 — Ping: Reachability & Latency

**Purpose:** Verify that all hosts can reach each other and measure latency.

**Commands (from Mininet CLI):**
```bash
mininet> pingall
mininet> h1 ping -c 5 h2       # same-switch
mininet> h1 ping -c 5 h6       # cross-switch
```

**Expected Results:**

| Test | Expected Latency | Expected Loss |
|------|-----------------|---------------|
| h1 → h2 (same switch s1) | ~10–15ms | 0% |
| h1 → h6 (cross switch s1→s3) | ~20–25ms | 0% |
| pingAll (36 pairs) | < 30ms avg | 0% |

---

### Scenario 2 — iperf: Throughput Measurement

**Purpose:** Measure TCP throughput between host pairs.

**Commands (from Mininet CLI):**
```bash
mininet> iperf h1 h2    # same-switch
mininet> iperf h1 h6    # cross-switch
```

**Or manually:**
```bash
mininet> h2 iperf -s &
mininet> h1 iperf -c 10.0.0.2 -t 10
```

**Expected Results:**

| Test | Expected Throughput |
|------|-------------------|
| h1 ↔ h2 (same switch) | ~9–10 Mbps (link limit) |
| h1 ↔ h6 (cross switch) | ~8–9 Mbps |

---

## Flow Table Inspection

From Mininet CLI, dump the flow table of any switch:

```bash
mininet> sh ovs-ofctl dump-flows s1
mininet> sh ovs-ofctl dump-flows s2
mininet> sh ovs-ofctl dump-flows s3
```

Sample output:
```
cookie=0x0, duration=12.3s, table=0, n_packets=42, n_bytes=3864,
  idle_timeout=60, hard_timeout=300, priority=10,
  in_port=1,dl_src=00:00:00:00:00:01,dl_dst=00:00:00:00:00:02
  actions=output:2
```

---

## Controller Statistics Output

Every 10 seconds, the controller prints:

```
=================================================================
FLOW STATISTICS  |  Switch 1          |  2025-01-15 14:32:10
=================================================================
Table   Src MAC             Dst MAC             Packets    Bytes        Duration(s)
-----------------------------------------------------------------
0       00:00:00:00:00:01   00:00:00:00:00:02   42         3864         12
0       00:00:00:00:00:02   00:00:00:00:00:01   38         3496         11
=================================================================
----- PORT STATS  |  Switch 1  |  2025-01-15 14:32:10 -----
Port    RX Packets      TX Packets      RX Bytes        TX Bytes
-----------------------------------------------------------------
1       125             120             11500           11040
2       120             125             11040           11500
-----------------------------------------------------------------
```

Statistics are also written to `flow_stats.csv`.

---

## Offline Analysis

After running the network, analyze the CSV log:

```bash
python3 analyze_stats.py
python3 analyze_stats.py --file flow_stats.csv
```

Sample output:
```
Switch: 00-00-00-00-00-01
  Src MAC               Dst MAC               Packets       Bytes     Duration(s)
  ------------------------------------------------------------------------------
  00:00:00:00:00:01     00:00:00:00:00:02         42        3864             12
  00:00:00:00:00:02     00:00:00:00:00:01         38        3496             11
  TOTAL                                           80        7360
```

---

## Proof of Execution

<img width="940" height="509" alt="image" src="https://github.com/user-attachments/assets/2ef1b90d-f3a1-47ff-86f2-37fc607393a6" />
<img width="651" height="379" alt="image" src="https://github.com/user-attachments/assets/d4b16180-1486-495f-adac-0b16192dd587" />
<img width="940" height="174" alt="image" src="https://github.com/user-attachments/assets/9c736838-55e3-4743-aea0-1fb7ac131e94" />




---

## Tools Used

| Tool | Purpose |
|------|---------|
| Mininet | Network emulation |
| POX | OpenFlow SDN controller |
| Open vSwitch (OVS) | Software OpenFlow switch |
| `ovs-ofctl` | Flow table inspection |
| `ping` | Latency & reachability testing |
| `iperf` | Throughput measurement |
| Wireshark | Packet-level inspection (optional) |

---

## References

1. Mininet Documentation — http://mininet.org/
2. POX Wiki — https://noxrepo.github.io/pox-doc/html/
3. OpenFlow 1.0 Specification — https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf
4. Open vSwitch Documentation — https://docs.openvswitch.org/
5. Lantz, B., Heller, B., & McKeown, N. (2010). *A network in a laptop: rapid prototyping for software-defined networks.* HotNets-IX. ACM.
6. Feamster, N., Rexford, J., & Zegura, E. (2014). *The road to SDN.* ACM Queue, 11(12).

---

## License

This project is submitted as coursework. All code is original unless cited above.

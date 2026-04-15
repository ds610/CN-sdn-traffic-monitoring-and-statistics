"""
traffic_monitor.py — POX SDN Controller: Traffic Monitoring & Statistics
=========================================================================
Assignment: SDN Mininet-based Simulation — Traffic Monitoring and Statistics
Controller : POX (OpenFlow 1.0)

Description:
  - Acts as a learning switch (MAC learning) to forward packets
  - Installs explicit OpenFlow flow rules (match-action)
  - Periodically polls all connected switches for flow/port statistics
  - Displays per-flow packet counts, byte counts, and duration
  - Logs all statistics to console and to a CSV file for analysis

Author  : [Your Name]
Date    : 2025
"""

from pox.core import core
from pox.lib.util import dpidToStr
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import EthAddr
from pox.lib.recoco import Timer
import datetime
import csv
import os

log = core.getLogger()

# ── Configuration ──────────────────────────────────────────────────────────────
STATS_INTERVAL   = 10          # seconds between each statistics poll
FLOW_IDLE_TIMEOUT = 60         # idle timeout for installed flow rules (seconds)
FLOW_HARD_TIMEOUT = 300        # hard timeout for installed flow rules (seconds)
CSV_LOG_FILE     = "flow_stats.csv"   # CSV output file name
# ───────────────────────────────────────────────────────────────────────────────


class TrafficMonitor(object):
    """
    Per-switch handler.
    Manages MAC table, installs flow rules, and collects statistics.
    """

    def __init__(self, connection, dpid):
        self.connection = connection
        self.dpid       = dpid
        self.mac_table  = {}          # { EthAddr → port_number }
        self.flow_stats = []          # latest flow stats snapshot
        self.port_stats = []          # latest port stats snapshot

        # Listen to messages from this switch
        connection.addListeners(self)

        log.info("[Switch %s] Connected — starting traffic monitor", dpidToStr(dpid))

        # Start periodic statistics polling
        Timer(STATS_INTERVAL, self._request_stats, recurring=True)

    # ── OpenFlow Event Handlers ─────────────────────────────────────────────

    def _handle_PacketIn(self, event):
        """
        Called whenever the switch sends a packet to the controller
        (no matching flow rule found).

        Steps:
          1. Learn source MAC → input port mapping
          2. If destination MAC is known → install a flow rule and forward
          3. If destination MAC is unknown → flood the packet
        """
        packet   = event.parsed
        src_mac  = packet.src
        dst_mac  = packet.dst
        in_port  = event.port

        if not packet.parsed:
            log.warning("[Switch %s] Ignoring unparsed packet", dpidToStr(self.dpid))
            return

        # Step 1: Learn source MAC
        self.mac_table[src_mac] = in_port
        log.debug("[Switch %s] Learned  %s → port %s", dpidToStr(self.dpid), src_mac, in_port)

        # Step 2: Unicast if destination known
        if dst_mac in self.mac_table:
            out_port = self.mac_table[dst_mac]
            log.info("[Switch %s] Installing flow  %s → %s  (port %s → port %s)",
                     dpidToStr(self.dpid), src_mac, dst_mac, in_port, out_port)
            self._install_flow(src_mac, dst_mac, in_port, out_port)
            self._send_packet(event, out_port)

        else:
            # Step 3: Flood — destination unknown
            log.info("[Switch %s] Flooding packet from %s (dst %s unknown)",
                     dpidToStr(self.dpid), src_mac, dst_mac)
            self._send_packet(event, of.OFPP_FLOOD)

    def _handle_FlowStatsReceived(self, event):
        """
        Handles flow statistics reply from the switch.
        Prints and logs per-flow counters.
        """
        self.flow_stats = event.stats
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log.info("=" * 65)
        log.info("FLOW STATISTICS  |  Switch %-10s  |  %s", dpidToStr(self.dpid), timestamp)
        log.info("=" * 65)
        log.info("%-6s  %-18s  %-18s  %-10s  %-12s  %s",
                 "Table", "Src MAC", "Dst MAC", "Packets", "Bytes", "Duration(s)")
        log.info("-" * 65)

        rows = []
        for stat in event.stats:
            src = str(stat.match.dl_src) if stat.match.dl_src else "ANY"
            dst = str(stat.match.dl_dst) if stat.match.dl_dst else "ANY"
            log.info("%-6s  %-18s  %-18s  %-10s  %-12s  %s",
                     stat.table_id, src, dst,
                     stat.packet_count, stat.byte_count, stat.duration_sec)
            rows.append([timestamp, dpidToStr(self.dpid), stat.table_id,
                         src, dst, stat.packet_count, stat.byte_count, stat.duration_sec])

        log.info("=" * 65)
        self._write_csv(rows)

    def _handle_PortStatsReceived(self, event):
        """
        Handles port statistics reply from the switch.
        Prints per-port TX/RX counters.
        """
        self.port_stats = event.stats
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log.info("----- PORT STATS  |  Switch %s  |  %s -----",
                 dpidToStr(self.dpid), timestamp)
        log.info("%-6s  %-14s  %-14s  %-14s  %-14s",
                 "Port", "RX Packets", "TX Packets", "RX Bytes", "TX Bytes")
        log.info("-" * 65)
        for stat in event.stats:
            log.info("%-6s  %-14s  %-14s  %-14s  %-14s",
                     stat.port_no,
                     stat.rx_packets, stat.tx_packets,
                     stat.rx_bytes,   stat.tx_bytes)
        log.info("-" * 65)

    # ── Helper Methods ──────────────────────────────────────────────────────

    def _install_flow(self, src_mac, dst_mac, in_port, out_port):
        """
        Install an explicit OpenFlow flow rule on the switch.

        Match  : source MAC + destination MAC + input port
        Action : output to out_port
        """
        msg = of.ofp_flow_mod()

        # Match fields
        msg.match.dl_src  = EthAddr(src_mac)
        msg.match.dl_dst  = EthAddr(dst_mac)
        msg.match.in_port = in_port

        # Timeouts
        msg.idle_timeout = FLOW_IDLE_TIMEOUT
        msg.hard_timeout = FLOW_HARD_TIMEOUT

        # Priority (higher than default table-miss)
        msg.priority = 10

        # Action: forward out the learned port
        msg.actions.append(of.ofp_action_output(port=out_port))

        self.connection.send(msg)

    def _send_packet(self, event, out_port):
        """Send a packet_out message to the switch."""
        msg = of.ofp_packet_out()
        msg.data    = event.ofp
        msg.in_port = event.port
        msg.actions.append(of.ofp_action_output(port=out_port))
        self.connection.send(msg)

    def _request_stats(self):
        """
        Periodically send stats request messages to the switch.
        Requests both flow-level and port-level statistics.
        """
        if not self.connection.connected:
            return
        log.debug("[Switch %s] Requesting statistics…", dpidToStr(self.dpid))

        # Flow statistics request
        self.connection.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))

        # Port statistics request
        self.connection.send(of.ofp_stats_request(body=of.ofp_port_stats_request()))

    def _write_csv(self, rows):
        """Append flow statistics rows to a CSV log file."""
        file_exists = os.path.isfile(CSV_LOG_FILE)
        with open(CSV_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Switch", "TableID",
                                 "SrcMAC", "DstMAC",
                                 "PacketCount", "ByteCount", "DurationSec"])
            writer.writerows(rows)


# ── Controller Entry Point ───────────────────────────────────────────────────

class TrafficMonitorController(object):
    """
    Top-level controller component.
    Listens for new switch connections and spawns a TrafficMonitor per switch.
    """

    def __init__(self):
        self.monitors = {}   # dpid → TrafficMonitor
        core.openflow.addListeners(self)
        log.info("Traffic Monitor Controller started — waiting for switches…")

    def _handle_ConnectionUp(self, event):
        """Called when a switch connects to the controller."""
        dpid = event.dpid
        log.info("[Switch %s] Connection established", dpidToStr(dpid))
        monitor = TrafficMonitor(event.connection, dpid)
        self.monitors[dpid] = monitor

    def _handle_ConnectionDown(self, event):
        """Called when a switch disconnects from the controller."""
        dpid = event.dpid
        log.info("[Switch %s] Disconnected", dpidToStr(dpid))
        if dpid in self.monitors:
            del self.monitors[dpid]


def launch():
    """POX launch function — registers the controller component."""
    core.registerNew(TrafficMonitorController)
    log.info("Traffic Monitor launched  (stats interval = %ds)", STATS_INTERVAL)

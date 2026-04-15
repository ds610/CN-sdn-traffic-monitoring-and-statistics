from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.recoco import Timer

log = core.getLogger()


class TrafficMonitor(EventMixin):

    def __init__(self):
        self.connections = []

        # Listen to OpenFlow events
        core.openflow.addListeners(self)

        # Run monitoring every 5 seconds
        Timer(5, self._monitor, recurring=True)

    # -----------------------------
    # Switch connection handler
    # -----------------------------
    def _handle_ConnectionUp(self, event):
        log.info("Switch connected: %s", event.dpid)
        self.connections.append(event.connection)

    # -----------------------------
    # Packet-In handler (Learning Switch)
    # -----------------------------
    def _handle_PacketIn(self, event):

        packet = event.parsed
        in_port = event.port
        connection = event.connection

        # Learn + Flood
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        connection.send(msg)

        # Install flow rule (match-action)
        fm = of.ofp_flow_mod()
        fm.match.in_port = in_port
        fm.idle_timeout = 10
        fm.hard_timeout = 30
        fm.priority = 10
        fm.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))

        connection.send(fm)

        log.info("Installed flow for in_port %s", in_port)

    # -----------------------------
    # Periodic monitoring trigger
    # -----------------------------
    def _monitor(self):

        log.info("Requesting flow statistics...")

        for con in self.connections:
            req = of.ofp_stats_request(body=of.ofp_flow_stats_request())
            con.send(req)

    # -----------------------------
    # Flow statistics reply handler
    # -----------------------------
    def _handle_FlowStatsReceived(self, event):

        log.info("========== FLOW STATS ==========")

        for stat in event.stats:

            log.info("Match: %s", stat.match)
            log.info("Packets: %s", stat.packet_count)
            log.info("Bytes: %s", stat.byte_count)
            log.info("--------------------------------")


# -----------------------------
# Launch function (IMPORTANT)
# -----------------------------
def launch():
    core.registerNew(TrafficMonitor)

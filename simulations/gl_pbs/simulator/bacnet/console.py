"""
console — WhoIsIAmConsoleCmd: interactive BACnet console commands.

SRP: Only handles console user input and delegates to the injected application.
DIP: Receives SimulatorApplication at construction instead of using a global.

Port of WhoIsIAmConsoleCmd in bacnet_simulator.py.
"""
from __future__ import annotations

import logging

from bacpypes.apdu import WhoIsRequest
from bacpypes.consolecmd import ConsoleCmd
from bacpypes.debugging import ModuleLogger, bacpypes_debugging
from bacpypes.pdu import Address, GlobalBroadcast

from simulator.bacnet.application import SimulatorApplication

logger = logging.getLogger(__name__)
_debug = 0
_log = ModuleLogger(globals())


@bacpypes_debugging
class WhoIsIAmConsoleCmd(ConsoleCmd):
    """
    Console command handler for BACnet discovery.
    Delegates all BACnet calls to the injected SimulatorApplication.

    Port of WhoIsIAmConsoleCmd with global `this_application` replaced
    by an injected dependency.
    """

    def __init__(self, application: SimulatorApplication) -> None:
        ConsoleCmd.__init__(self)
        self._app = application

    def do_whois(self, args: str) -> None:
        """whois [ <addr> ] [ <lolimit> <hilimit> ]"""
        parts = args.split()
        if _debug:
            WhoIsIAmConsoleCmd._debug('do_whois %r', parts)
        try:
            if len(parts) in (1, 3):
                addr = Address(parts[0])
                parts = parts[1:]
            else:
                addr = GlobalBroadcast()

            lolimit = hilimit = None
            if len(parts) == 2:
                lolimit, hilimit = int(parts[0]), int(parts[1])

            self._app.who_is(lolimit, hilimit, addr)
            self._app.i_am()
        except Exception as exc:
            WhoIsIAmConsoleCmd._exception('exception: %r', exc)

    def do_any(self, args: str) -> None:
        """any — print all I-Am responses as if an unconstrained Who-Is was sent."""
        self._app._request = WhoIsRequest()
        self._app._request.deviceInstanceRangeLowLimit = 0
        self._app._request.deviceInstanceRangeHighLimit = 4194303

    def do_iam(self, args: str) -> None:
        """iam — broadcast an I-Am from this device."""
        if _debug:
            WhoIsIAmConsoleCmd._debug('do_iam %r', args.split())
        self._app.i_am()

    def do_rtn(self, args: str) -> None:
        """rtn <addr> <net> ...  — update router table entries."""
        parts = args.split()
        if _debug:
            WhoIsIAmConsoleCmd._debug('do_rtn %r', parts)
        router_address = Address(parts[0])
        network_list = [int(p) for p in parts[1:]]
        self._app.nsap.update_router_references(None, router_address, network_list)

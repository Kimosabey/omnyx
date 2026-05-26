"""
sim_config — SimulatorConfig dataclass.

SRP: Only holds configuration values parsed from sys.argv.
     No BACnet I/O, no file loading, no HTTP.

Replaces the large manual sys.argv parsing block in main().
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SimulatorConfig:
    """
    Typed configuration for the BACnet plant simulator.

    Maps to the sys.argv parsing logic in the original main().
    """
    # Deployment config files
    deployment_file: str = 'data/CBDeploymentDetails.json'
    gls_file: str = 'data/GLSDeploymentDetails.json'
    site_objects_file: Optional[str] = None

    # BACnet network
    bacnet_port: str = '2001'
    use_ethernet: bool = False
    default_ip: Optional[str] = None

    # Web UI
    web_ui_port: int = 7090

    # Equipment simulation
    use_full_gl_code: bool = True
    eqp_type: str = ''
    eqp_index: int = 27
    n_eqp: int = 1
    param_start_id: int = 100

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_argv(cls, argv: List[str]) -> 'SimulatorConfig':
        """
        Port of the sys.argv parsing logic in main().

        Argument patterns (positional, no argparse):
          7 args: eqpType eqpIndex bacnetPort devObjId nEqp paramStartId
          6 args: deploymentFile bacnetPort webPort defaultIp siteObjectsFile
          5 args: deploymentFile bacnetPort webPort defaultIp
          4 args: deploymentFile bacnetPort webPort
          else:   defaults (dev mode)
        """
        n = len(argv)

        if n == 7:
            return cls(
                use_full_gl_code=True,
                eqp_type=argv[1],
                eqp_index=int(argv[2]),
                bacnet_port=argv[3],
                n_eqp=int(argv[5]),
                param_start_id=int(argv[6]),
            )

        if n == 6:
            sof = argv[5] if _file_exists(argv[5]) else None
            return cls(
                deployment_file=argv[1],
                bacnet_port=argv[2],
                web_ui_port=int(argv[3]),
                use_ethernet=True,
                default_ip=argv[4],
                site_objects_file=sof,
            )

        if n == 5:
            return cls(
                deployment_file=argv[1],
                bacnet_port=argv[2],
                web_ui_port=int(argv[3]),
                use_ethernet=True,
                default_ip=argv[4],
            )

        if n == 4:
            return cls(
                deployment_file=argv[1],
                bacnet_port=argv[2],
                web_ui_port=int(argv[3]),
            )

        # Default / dev mode
        return cls()

    @property
    def device_object_id(self) -> int:
        """BACnet device object identifier (derived from bacnet_port)."""
        return int(self.bacnet_port)

    @property
    def device_name(self) -> str:
        return 'MySimulator' + self.bacnet_port


def _file_exists(path: str) -> bool:
    import os
    return os.path.isfile(path)

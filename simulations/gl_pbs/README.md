# gl_pbs — BACnet Simulator (Graylinx PBS)

This folder contains the gl_pbs BACnet simulator source that feeds the OMNYX POC.

## Setup

Copy your gl_pbs Python source files here from `D:\Harshan\simulations\gl_pbs`:

```
simulations/gl_pbs/
├── bacnet_name_launcher.py   ← main entry point (spawns one sim per DDC)
├── bacnet_name_simulator.py  ← per-DDC BACnet application
├── bacnet_reader.py
├── bacnet_writer.py
├── glDASLibrary.py
├── glObjectNameHandler.py
├── config/
│   └── GLBACpypes.ini        ← written by launcher; read by dal-bacnet
├── data/
│   └── eqp_name_handling.csv ← 363 points, 11 DDCs
├── Dockerfile.sim            ← already here
└── requirements-sim.txt      ← already here
```

## Start

```bash
# From omnyx root:
make up-sim
# or
docker compose -f infra/compose/docker-compose.yml --profile simulator up -d bacnet-sim
```

The simulator runs with `network_mode: host` so BACnet UDP is directly on ports 2001–2011.
`dal-bacnet` (profile: app) reads from those ports.

"""
AppConfig — typed configuration container replacing the GL_GLOBALS dict.

Load via:
    raw = setConfigurationDetails(args.ini)  # from glDASLibrary
    config = AppConfig.from_ini_dict(raw)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


def _parse_json_field(value):
    """Return *value* as a dict; parse it from JSON if it's a string."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


@dataclass
class AppConfig:
    """
    Single source of truth for all runtime configuration.

    Replaces the GL_GLOBALS dict so that configuration is:
      - Typed and discoverable (IDE auto-complete)
      - Validated at construction (type converters in from_ini_dict)
      - Passed explicitly rather than accessed as a global
    """

    # ── BACnet / network ──────────────────────────────────────────────────
    rpm_requests_file: str = 'data/eqp_name_handling.csv'
    deployment_config_file: str = 'glIBMSDeployment.json'
    use_read_property_multiple: bool = True
    my_bacnet_port: int = 1928
    use_local_ddc_simulators: bool = True
    discover_device_ip_address: bool = True
    use_ethernet: bool = False
    default_ip_address: str = '127.0.0.1'
    auto_detect_ip: bool = True
    controller_map: dict = field(default_factory=lambda: {"DDC1": "127.0.0.1:7090"})
    mstp_networks_map: dict = field(default_factory=dict)
    use_object_name_handler: bool = False

    # ── Acquisition timing ────────────────────────────────────────────────
    inter_batch_interval: float = 0.2           # minutes between batches
    data_acquisition_timeout_secs: float = 15.0
    data_acquisition_max_retry_attempts: int = 3
    data_acquisition_heartbeat_minutes: float = 15.0
    recurring_data_load: bool = True
    number_of_read_cycles: int = -1             # -1 = run forever
    allow_multiple_sampling_rates: bool = False
    counter_limit: int = 13
    number_of_reading_threads: int = 250
    rpm_batch_size: int = 15            # max points per RPM request per device

    # ── Change-of-Value ───────────────────────────────────────────────────
    check_cov: bool = True
    cov_threshold_percent: float = 12.0
    cov_computation_within_thread: bool = True
    use_in_thread_cov_check: bool = True        # DO NOT change in production

    # ── Notification ──────────────────────────────────────────────────────
    notify_read_data: str = 'ONLY_COV'          # ALL_RM | ONLY_COV | DONOT_NOTIFY
    post_url: str = 'https://localhost:8443/v1/newapis/mypost/'
    web_post_timeout_secs: float = 2.5

    # ── Database ──────────────────────────────────────────────────────────
    insert_rm_data_into_db: bool = True
    db_connection_pool: Optional[Any] = None
    ibms_database_name: str = 'tepldb'
    database_table_name: str = ''
    database_host: str = 'localhost'
    database_user: str = 'ibms_db'
    database_password: str = '1234'
    database_table_name_length: int = 12
    use_per_equipment_table: bool = True
    use_multiple_tables: bool = True
    create_equipment_table: bool = True

    # ── Deployment / codebook ─────────────────────────────────────────────
    gl_codebook_csv: str = './data/CBParameters.csv'
    deployment_details_file: str = './data/GLSDeploymentDetails.json'
    store_equipment_parameter_data: bool = True

    # ── Web server ────────────────────────────────────────────────────────
    enable_pbs2_web: bool = True
    pbs2_web_port: int = 7061

    # ── Thread dump / logging ─────────────────────────────────────────────
    thread_dump_file_prefix: str = 'tdout_'

    # ── Internal interval counter (mutable at runtime) ────────────────────
    time_interval_counter: int = -1

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def from_ini_dict(cls, ini: dict) -> 'AppConfig':
        """
        Build an AppConfig from the dict returned by
        glDASLibrary.setConfigurationDetails(args.ini).

        All keys in that dict are camelCase (as produced by
        setConfigurationDetails); we map them to snake_case fields here.
        """
        b = lambda v: v is True or str(v).strip() == 'True'

        return cls(
            # BACnet / network
            rpm_requests_file=ini.get('rpmRequestsFile', 'data/eqp_name_handling.csv'),
            deployment_config_file=ini.get('deploymentConfigFile', 'glIBMSDeployment.json'),
            use_read_property_multiple=b(ini.get('useReadPropertyMultiple', True)),
            my_bacnet_port=int(ini.get('myBACnetPort', 1928)),
            use_local_ddc_simulators=b(ini.get('useLocalDDCSimulators', True)),
            discover_device_ip_address=b(ini.get('discoverDeviceIPAddress', True)),
            use_ethernet=b(ini.get('useEthernet', False)),
            default_ip_address=ini.get('defaultIPAddress', '127.0.0.1'),
            auto_detect_ip=b(ini.get('autoDetectIP', True)),
            controller_map=_parse_json_field(
                ini.get('controllermap', {"DDC1": "127.0.0.1:7090"})
            ),
            mstp_networks_map=ini.get('mstpNetworksMap', {}),
            use_object_name_handler=b(ini.get('USE_OBJECT_NAME_HANDLER', False)),

            # Acquisition timing
            inter_batch_interval=float(ini.get('interBatchInterval', 0.2)),
            data_acquisition_timeout_secs=float(ini.get('dataAcquisitionTimeoutSecs', 15.0)),
            data_acquisition_max_retry_attempts=int(ini.get('dataAcquisitionMaximumRetryAttempts', 3)),
            data_acquisition_heartbeat_minutes=float(ini.get('dataAcquisitionHeartbeatMinutes', 15.0)),
            recurring_data_load=b(ini.get('recurringDataLoad', True)),
            number_of_read_cycles=int(ini.get('numberOfReadCycles', -1)),
            allow_multiple_sampling_rates=b(ini.get('allowMultipleSamplingRates', False)),
            counter_limit=int(ini.get('counterLimit', 13)),
            number_of_reading_threads=int(ini.get('numberOfReadingThreads', 250)),
            rpm_batch_size=int(ini.get('rpmBatchSize', 15)),

            # CoV
            check_cov=b(ini.get('checkCoV', True)),
            cov_threshold_percent=float(ini.get('CoVThresholdPercent', 12.0)),
            cov_computation_within_thread=b(ini.get('CoVComputationWithinThread', True)),
            use_in_thread_cov_check=b(ini.get('useInThreadCoVCheck', True)),

            # Notification
            notify_read_data=ini.get('notifyReadData', 'ONLY_COV'),
            post_url=ini.get('postURL', 'https://localhost:8443/v1/newapis/mypost/'),
            web_post_timeout_secs=float(ini.get('webPostTimeoutSecs', 2.5)),

            # Database
            insert_rm_data_into_db=b(ini.get('insertRMDataintoDB', True)),
            ibms_database_name=ini.get('ibms_database_name', 'tepldb'),
            database_table_name=ini.get('database_table_name', ''),
            database_host=ini.get('databasehost', 'localhost'),
            database_user=ini.get('databaseuser', 'ibms_db'),
            database_password=ini.get('databasePassword', '1234'),
            database_table_name_length=int(ini.get('databaseTableNameLength', 12)),
            use_per_equipment_table=b(ini.get('usePerEquipmentTable', True)),
            use_multiple_tables=b(ini.get('useMultipleTables', True)),
            create_equipment_table=b(ini.get('createEquipmentTable', True)),

            # Deployment
            gl_codebook_csv=ini.get('GLCodeBookCSV', './CBParameters.csv'),
            deployment_details_file=ini.get('deploymentDetailsFile', './GLSDeploymentDetails.json'),
            store_equipment_parameter_data=b(ini.get('storeEquipmentParameterData', True)),

            # Web server
            enable_pbs2_web=b(ini.get('enablePBS2web', True)),
            pbs2_web_port=int(ini.get('PBS2Webport', 7061)),

            # Thread dump
            thread_dump_file_prefix=ini.get('threadDumpFilePrefix', 'tdout_'),
        )

    def to_legacy_dict(self) -> dict:
        """
        Return a dict in the old GL_GLOBALS shape for compatibility with
        any glDASLibrary calls that still read from it directly.
        """
        return {
            'rpmRequestsFile': self.rpm_requests_file,
            'deploymentConfigFile': self.deployment_config_file,
            'useReadPropertyMultiple': self.use_read_property_multiple,
            'myBACnetPort': self.my_bacnet_port,
            'useLocalDDCSimulators': self.use_local_ddc_simulators,
            'discoverDeviceIPAddress': self.discover_device_ip_address,
            'useEthernet': self.use_ethernet,
            'defaultIPAddress': self.default_ip_address,
            'autoDetectIP': self.auto_detect_ip,
            'controllermap': self.controller_map,
            'mstpNetworksMap': self.mstp_networks_map,
            'USE_OBJECT_NAME_HANDLER': self.use_object_name_handler,
            'interBatchInterval': self.inter_batch_interval,
            'dataAcquisitionTimeoutSecs': self.data_acquisition_timeout_secs,
            'dataAcquisitionMaximumRetryAttempts': self.data_acquisition_max_retry_attempts,
            'dataAcquisitionHeartbeatMinutes': self.data_acquisition_heartbeat_minutes,
            'recurringDataLoad': self.recurring_data_load,
            'numberOfReadCycles': self.number_of_read_cycles,
            'allowMultipleSamplingRates': self.allow_multiple_sampling_rates,
            'counterLimit': self.counter_limit,
            'numberOfReadingThreads': self.number_of_reading_threads,
            'checkCoV': self.check_cov,
            'CoVThresholdPercent': self.cov_threshold_percent,
            'CoVComputationWithinThread': self.cov_computation_within_thread,
            'useInThreadCoVCheck': self.use_in_thread_cov_check,
            'notifyReadData': self.notify_read_data,
            'postURL': self.post_url,
            'webPostTimeoutSecs': self.web_post_timeout_secs,
            'insertRMDataintoDB': self.insert_rm_data_into_db,
            'dbConnectionPool': self.db_connection_pool,
            'ibms_database_name': self.ibms_database_name,
            'database_table_name': self.database_table_name,
            'databasehost': self.database_host,
            'databaseuser': self.database_user,
            'databasePassword': self.database_password,
            'databaseTableNameLength': self.database_table_name_length,
            'usePerEquipmentTable': self.use_per_equipment_table,
            'useMultipleTables': self.use_multiple_tables,
            'createEquipmentTable': self.create_equipment_table,
            'GLCodeBookCSV': self.gl_codebook_csv,
            'deploymentDetailsFile': self.deployment_details_file,
            'storeEquipmentParameterData': self.store_equipment_parameter_data,
            'enablePBS2web': self.enable_pbs2_web,
            'PBS2Webport': self.pbs2_web_port,
            'threadDumpFilePrefix': self.thread_dump_file_prefix,
            'timeIntervalCounter': self.time_interval_counter,
        }

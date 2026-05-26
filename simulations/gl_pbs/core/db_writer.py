"""
DatabaseWriter — prepares and executes database insertions for BACnet data.

SRP: Only responsible for building DB row tuples and writing them to
     the database via glDASLibrary.insertDataIntoDatabase().

Extracted from ReadPointListThread.prepareDBInsertionData() and the
insertDataIntoDatabase() call in postProcessResults().
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from glDASLibrary import myprint, printTrace, getDeepObject, insertDataIntoDatabase, getstrTimeNow

if TYPE_CHECKING:
    from core.cov_checker import CoVChecker

# Row shape: (e_id, measured_time, p_name, value [, eqp_tableName])
InsertRow = Tuple


class DatabaseWriter:
    """
    Prepares and executes DB insertions.

    No BACnet, no CoV logic, no HTTP — only database concerns.
    """

    def __init__(
        self,
        connection_pool,
        use_per_equipment_table: bool = True,
        database_table_name: str = '',
        use_multiple_tables: bool = True,
        create_equipment_table: bool = True,
    ) -> None:
        self.connection_pool = connection_pool
        self.use_per_equipment_table = use_per_equipment_table
        self.database_table_name = database_table_name
        self.use_multiple_tables = use_multiple_tables
        self.create_equipment_table = create_equipment_table

    # ── data preparation ─────────────────────────────────────────────────

    def build_insertion_data(
        self,
        device_address: str,
        point_values: dict,
        cov_checker: 'CoVChecker',
        data_time: Optional[str] = None,
    ) -> List[InsertRow]:
        """
        Build a list of DB row tuples from point_values using CoVChecker
        state records for parameter metadata.

        Port of ReadPointListThread.prepareDBInsertionData() — uses
        cov_checker.get_record() instead of direct previous_values access.

        Row shape (mirrors original):
          (e_id, measured_time, p_name, value, eqp_tableName)  when len >= 6
          (e_id, measured_time, p_name, value)                  when len >= 5
          (addr_prefix, measured_time, obj_name, value)         when len >= 3
          (device_address, measured_time, obj_id, value)        fallback
        """
        measured_time = data_time or getstrTimeNow()
        rows: List[InsertRow] = []

        for obj_id, props in point_values.items():
            if 'presentValue' not in props:
                continue
            pv_entry = props['presentValue']
            if 'propertyValue' not in pv_entry:
                # Read failed for this point — never write a default/zero value
                continue
            value = pv_entry['propertyValue']
            record = cov_checker.get_record(device_address, obj_id)
            myprint('To write to Database - {}'.format(record))

            if record:
                if len(record) >= 7:
                    rows.append((record[5], measured_time, record[3], value, record[6]))
                elif len(record) >= 6:
                    rows.append((record[5], measured_time, record[3], value))
                elif len(record) >= 3:
                    rows.append((record[0][:-6], measured_time, record[0], value))
                else:
                    rows.append((device_address, measured_time, obj_id, value))
            else:
                rows.append((device_address, measured_time, obj_id, value))

        return rows

    # ── DB write ─────────────────────────────────────────────────────────

    def write(self, device_address: str, insertion_data: List[InsertRow]) -> bool:
        """
        Route insertion_data to insertDataIntoDatabase() using the
        correct table strategy.

        Returns True on success, False on failure.
        """
        if not self.connection_pool or not insertion_data:
            return False

        # Warn about rows with empty eqp_table_name when using per-equipment tables
        if self.use_per_equipment_table:
            empty_tbl = [r for r in insertion_data if len(r) >= 5 and not r[4]]
            if empty_tbl:
                printTrace(
                    'db_writer.write WARNING — {} row(s) have empty eqp_table_name and '
                    'will be skipped by insertDataIntoDatabase. '
                    'Check processEquipmentCode output for device {}'.format(
                        len(empty_tbl), device_address
                    )
                )

        try:
            if self.use_per_equipment_table:
                insertDataIntoDatabase(
                    self.connection_pool,
                    myvalues=insertion_data,
                    usePerEquipmentTable=True,
                )
            elif self.database_table_name:
                insertDataIntoDatabase(
                    self.connection_pool,
                    myvalues=insertion_data,
                    mytable=self.database_table_name,
                )
            else:
                insertDataIntoDatabase(
                    self.connection_pool,
                    myvalues=insertion_data,
                    useMultipleTables=self.use_multiple_tables,
                    device_Address=device_address,
                    createEquipmentTable=self.create_equipment_table,
                )
            return True
        except Exception as exc:
            printTrace('db_writer.write ERROR for {} — {}'.format(device_address, exc))
            return False

# -*- coding: utf-8 -*-
from collections import namedtuple

from PySide2 import QtWidgets
from PySide2.QtCore import Slot, Qt
from brightway2 import calculation_setups
import pandas as pd

from ...bwutils.superstructure import (
    SuperstructureManager, import_from_excel, scenario_names_from_df,
    SUPERSTRUCTURE,
)
from ...signals import signals
from ...ui.icons import qicons
from ...ui.style import horizontal_line, header, style_group_box
# from ...ui.tables import (
#     CSActivityTable, CSList, CSMethodsTable, PresamplesList, ScenarioImportTable
# ) #TODO ps
from ...ui.tables import (
    CSActivityTable, CSList, CSMethodsTable, ScenarioImportTable
) #TODO ps
from ...ui.widgets import ExcelReadDialog
from .base import BaseRightTab

"""
Lifecycle of a calculation setup
================================

Data format
-----------

{name: {'inv': [{key: amount}], 'ia': [method]}}

Responsibilities
----------------

``CalculationSetupTab`` manages whether the activities and methods tables are shown, and which buttons are shown.

``CSActivityTableWidget`` and ``CSMethodsTableWidget`` mangage drag and drop events, and use signals to communicate data changes with the controller.

Initiation
----------

The app is started, a default project is loaded. ``CalculationSetupTab`` is initiated. If a calculation setup is present, the first one in a sorted list is selected. The signal ``calculation_setup_selected`` is emitted. Activity and methods tables are shown, as well as the full button row. If no calculation setup is available, all tables and most buttons are hidden, only the ``new_cs_button`` is shown.

``calculation_setup_selected`` is received by ``CSList``, which sets the list index correctly.

``calculation_setup_selected`` is received by ``CSActivityTableWidget`` and ``CSMethodsTableWidget``, and data is displayed.

Selecting a new project
-----------------------

When a new project is selected, the signal ``project_selected`` is received by ``CalculationSetupTab``, which follows the same procedure: emit ``calculation_setup_selected`` is possible, otherwise hide tables and buttons.

Selecting a different calculation setup
---------------------------------------

When a new calculation setup is selected in ``CSList``, the event ``itemSelectionChanged`` calls a function that emits ``calculation_setup_selected``.

Altering the current calculation setup
--------------------------------------

When new activities or methods are dragged into the activity or methods tables, the signal ``calculation_setup_changed`` is emitted. ``calculation_setup_changed`` is received by a controller method ``write_current_calculation_setup`` which saves the current data.

When the amount of an activity is changed, the event ``cellChanged`` is caught by ``CSActivityTableWidget``, which emits ``calculation_setup_changed``.

Creating a new calculation setup
--------------------------------

The button ``new_cs_button`` is connected to the controller method ``new_calculation_setup``, which creates the new controller setup and in turn emits ``calculation_setup_selected``. Note that ``CSList`` rebuilds the list of all calculation setups when receiving ``calculation_setup_selected``, so the new setup is listed.

Renaming a calculation setup
----------------------------

The button ``rename_cs_button`` is connected to the controller method ``rename_calculation_setup``, which changes the calculation setup name and in turn emits ``calculation_setup_selected``.

Deleting a calculation setup
----------------------------

The button ``delete_cs_button`` is connected to the controller method ``delete_calculation_setup``, which deletes the calculation setup name and in turn emits ``calculation_setups_changed``.

State data
----------

The currently selected calculation setup is retrieved by getting the currently selected value in ``CSList``.

"""
#PresamplesTuple = namedtuple("presamples", ["label", "list", "button", "remove"]) #TODO ps


class LCASetupTab(QtWidgets.QWidget):
    DEFAULT = 0
    SCENARIOS = 1
    #PRESAMPLES = 2 #TODO ps

    def __init__(self, parent=None):
        super().__init__(parent)

        self.cs_panel = QtWidgets.QWidget(self)
        cs_panel_layout = QtWidgets.QVBoxLayout()
        self.scenario_panel = ScenarioImportPanel(self)
        self.scenario_panel.hide()

        self.activities_table = CSActivityTable(self)
        self.methods_table = CSMethodsTable(self)
        self.list_widget = CSList(self)

        self.new_cs_button = QtWidgets.QPushButton(qicons.add, "New")
        self.copy_cs_button = QtWidgets.QPushButton(qicons.copy, "Copy")
        self.rename_cs_button = QtWidgets.QPushButton(qicons.edit, "Rename")
        self.delete_cs_button = QtWidgets.QPushButton(qicons.delete, "Delete")

        self.calculate_button = QtWidgets.QPushButton(qicons.calculate, "Calculate")
        self.calculation_type = QtWidgets.QComboBox()
        # self.calculation_type.addItems(["Standard LCA", "Scenario LCA", "Presamples LCA"]) #TODO ps
        self.calculation_type.addItems(["Standard LCA", "Scenario LCA"])  # TODO ps

        # self.presamples = PresamplesTuple(
        #     QtWidgets.QLabel("Prepared scenarios:"),
        #     PresamplesList(self),
        #     QtWidgets.QPushButton(qicons.calculate, "Calculate"),
        #     QtWidgets.QPushButton(qicons.delete, "Remove"),
        # ) #TODO ps
        # for obj in self.presamples: #TODO ps
        #     obj.hide()
        self.scenario_calc_btn = QtWidgets.QPushButton(qicons.calculate, "Calculate")
        self.scenario_calc_btn.hide()

        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(header('Calculation Setup:'))
        name_row.addWidget(self.list_widget)
        name_row.addWidget(self.new_cs_button)
        name_row.addWidget(self.copy_cs_button)
        name_row.addWidget(self.rename_cs_button)
        name_row.addWidget(self.delete_cs_button)
        name_row.addStretch(1)

        calc_row = QtWidgets.QHBoxLayout()
        calc_row.addWidget(self.calculate_button)
        # calc_row.addWidget(self.presamples.button) #TODO ps
        calc_row.addWidget(self.scenario_calc_btn)
        calc_row.addWidget(self.calculation_type)
        # calc_row.addWidget(self.presamples.label) #TODO ps
        # calc_row.addWidget(self.presamples.list) #TODO ps
        # calc_row.addWidget(self.presamples.remove) #TODO ps
        calc_row.addStretch(1)

        container = QtWidgets.QVBoxLayout()
        container.addLayout(name_row)
        container.addLayout(calc_row)
        container.addWidget(horizontal_line())

        # widget for the reference flows
        self.reference_flow_widget = QtWidgets.QWidget()
        reference_flow_layout = QtWidgets.QVBoxLayout()
        reference_flow_layout.addWidget(header('Reference flows:'))
        reference_flow_layout.addWidget(self.activities_table)
        self.reference_flow_widget.setLayout(reference_flow_layout)

        # widget for the impact categories
        self.impact_categories_widget = QtWidgets.QWidget()
        impact_categories_layout = QtWidgets.QVBoxLayout()
        impact_categories_layout.addWidget(header('Impact categories:'))
        impact_categories_layout.addWidget(self.methods_table)
        self.impact_categories_widget.setLayout(impact_categories_layout)

        # splitter widget to combine the two above widgets
        self.splitter = QtWidgets.QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.reference_flow_widget)
        self.splitter.addWidget(self.impact_categories_widget)

        self.no_setup_label = QtWidgets.QLabel("To do an LCA, create a new calculation setup first by pressing 'New'.")
        cs_panel_layout.addWidget(self.no_setup_label)
        cs_panel_layout.addWidget(self.splitter)

        self.cs_panel.setLayout(cs_panel_layout)
        container.addWidget(self.cs_panel)
        container.addWidget(self.scenario_panel)

        self.setLayout(container)

        self.connect_signals()

    def connect_signals(self):
        # Signals
        self.calculate_button.clicked.connect(self.start_calculation)
        # self.presamples.button.clicked.connect(self.presamples_calculation) #TODO ps
        # self.presamples.remove.clicked.connect(self.remove_presamples_package) #TODO ps
        self.scenario_calc_btn.clicked.connect(self.scenario_calculation)

        self.new_cs_button.clicked.connect(signals.new_calculation_setup.emit)
        self.copy_cs_button.clicked.connect(
            lambda: signals.copy_calculation_setup.emit(self.list_widget.name)
        )
        self.delete_cs_button.clicked.connect(
            lambda x: signals.delete_calculation_setup.emit(
                self.list_widget.name
        ))
        self.rename_cs_button.clicked.connect(
            lambda x: signals.rename_calculation_setup.emit(
                self.list_widget.name
        ))
        signals.calculation_setup_changed.connect(self.save_cs_changes)
        self.calculation_type.currentIndexChanged.connect(self.select_calculation_type)

        # Slots
        signals.set_default_calculation_setup.connect(self.set_default_calculation_setup)
        # signals.set_default_calculation_setup.connect(self.valid_presamples) #TODO ps
        signals.project_selected.connect(self.set_default_calculation_setup)
        # signals.project_selected.connect(self.valid_presamples) #TODO ps
        signals.calculation_setup_selected.connect(lambda: self.show_details())
        signals.calculation_setup_selected.connect(self.enable_calculations)
        signals.calculation_setup_changed.connect(self.enable_calculations)
        # signals.calculation_setup_changed.connect(self.valid_presamples) #TODO ps
        # signals.presample_package_created.connect(self.valid_presamples) #TODO ps

    def save_cs_changes(self):
        name = self.list_widget.name
        if name:
            calculation_setups[name] = {
                'inv': self.activities_table.to_python(),
                'ia': self.methods_table.to_python()
            }

    @Slot(name="calculationDefault")
    def start_calculation(self):
        data = {
            'cs_name': self.list_widget.name,
            'calculation_type': 'simple',
        }
        signals.lca_calculation.emit(data)

    # @Slot(name="calculationPresamples")
    # def presamples_calculation(self): #TODO ps
    #     data = {
    #         'cs_name': self.list_widget.name,
    #         'calculation_type': 'presamples',
    #         'data': self.presamples.list.selection,
    #     }
    #     signals.lca_calculation.emit(data)

    # @Slot(name="removePresamplesPackage")
    # def remove_presamples_package(self): #TODO ps
    #     """Removes the current presamples package selected from the list."""
    #     name_id = self.presamples.list.selection
    #     do_remove = QtWidgets.QMessageBox.question(
    #         self, "Removing presample package",
    #         "Are you sure you want to remove presample package '{}'?".format(name_id),
    #         QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
    #         QtWidgets.QMessageBox.No
    #     )
    #     if do_remove == QtWidgets.QMessageBox.Yes:
    #         signals.presample_package_delete.emit(name_id)

    @Slot(name="calculationScenario")
    def scenario_calculation(self) -> None:
        """Construct index / value array and begin LCA calculation."""
        data = {
            'cs_name': self.list_widget.name,
            'calculation_type': 'scenario',
            'data': self.scenario_panel.combined_dataframe(),
        }
        signals.lca_calculation.emit(data)

    @Slot(name="toggleDefaultCalculation")
    def set_default_calculation_setup(self):
        self.calculation_type.setCurrentIndex(0)
        if not len(calculation_setups):
            self.show_details(False)
            self.calculate_button.setEnabled(False)
            self.scenario_calc_btn.setEnabled(False)
        else:
            signals.calculation_setup_selected.emit(
                sorted(calculation_setups)[0]
            )

    # @Slot(name="togglePresampleCalculation")
    # def valid_presamples(self): #TODO ps
    #     """ Determine if calculate with presamples is active.
    #     """
    #     valid = self.calculate_button.isEnabled() and self.presamples.list.has_packages
    #     if valid:
    #         self.presamples.list.sync()
    #     self.presamples.list.setEnabled(valid)
    #     self.presamples.button.setEnabled(valid)

    def show_details(self, show: bool = True):
        # show/hide items from name_row
        self.rename_cs_button.setVisible(show)
        self.delete_cs_button.setVisible(show)
        self.copy_cs_button.setVisible(show)
        self.list_widget.setVisible(show)
        # show/hide items from calc_row
        if not show:
            self.calculate_button.setVisible(show)
            # self.presamples.button.setVisible(show) #TODO ps
            self.scenario_calc_btn.setVisible(show)
            self.calculation_type.setVisible(show)
            # self.presamples.label.setVisible(show) #TODO ps
            # self.presamples.list.setVisible(show) #TODO ps
            # self.presamples.remove.setVisible(show) #TODO ps
        else:
            self.calculation_type.setVisible(show)
            calc_type = self.calculation_type.currentText()
            if calc_type == "Standard LCA":
                self.calculate_button.setVisible(show)
            elif calc_type == "Scenario LCA":
                self.scenario_calc_btn.setVisible(show)
            # elif calc_type == "Presamples LCA": #TODO ps
            #     self.presamples.button.setVisible(show)
            #     self.presamples.label.setVisible(show)
            #     self.presamples.list.setVisible(show)
            #     self.presamples.remove.setVisible(show)

        # show/hide tables widgets
        self.splitter.setVisible(show)
        self.no_setup_label.setVisible(not(show))

    @Slot(int, name="changeCalculationType")
    def select_calculation_type(self, index: int):
        if index == self.DEFAULT:
            # Standard LCA.
            self.calculate_button.show()
            # for obj in self.presamples: #TODO ps
            #     obj.hide()
            self.scenario_calc_btn.hide()
            self.scenario_panel.hide()
        elif index == self.SCENARIOS:
            self.calculate_button.hide()
            # for obj in self.presamples: #TODO ps
            #     obj.hide()
            self.scenario_calc_btn.show()
            self.scenario_panel.show()
        # elif index == self.PRESAMPLES: #TODO ps
        #     # Presamples / Scenarios LCA.
        #     self.calculate_button.hide()
        #     for obj in self.presamples:
        #         obj.show()
        #     self.scenario_calc_btn.hide()
        #     self.scenario_panel.hide()
        self.cs_panel.updateGeometry()

    def enable_calculations(self):
        valid_cs = all([self.activities_table.rowCount(), self.methods_table.rowCount()])
        self.calculate_button.setEnabled(valid_cs)
        self.scenario_calc_btn.setEnabled(valid_cs)


class ScenarioImportPanel(BaseRightTab):
    MAX_TABLES = 5

    """Special kind of QWidget that contains one or more tables side by side."""
    def __init__(self, parent=None):
        super().__init__(parent)

        self.explain_text = """
        <p>You can import two different scenario types here:</p>
        <p>1. <b>flow-scenarios</b>: flow scenarios are alternative values for exchanges (flows between processes or between processes and the environment)</p>
        <p>2. <b>parameter-scenarios</b>: alternative values for parameters you use within a project</p>
        <p>If you do not know how such files look like, you can go to the Parameters --> Scenarios tab.
         Then click "Export parameter-scenarios" to obtain a parameter-scenarios file or  
         "Export as flow-scenarios" to obtain a flow-scenarios file. 
         Note that you need to have at least one parameterized activity to obtain flow-scenarios</p>
        """

        self.tables = []
        layout = QtWidgets.QVBoxLayout()

        self.scenario_tables = QtWidgets.QHBoxLayout()
        self.table_btn = QtWidgets.QPushButton(qicons.add, "Add")

        self.combine_label = QtWidgets.QLabel("Combine tables by:")
        self.group_box = QtWidgets.QGroupBox()
        self.group_box.setStyleSheet(style_group_box.border_title)
        input_field_layout = QtWidgets.QHBoxLayout()
        self.group_box.setLayout(input_field_layout)
        self.combine_group = QtWidgets.QButtonGroup()
        self.combine_group.setExclusive(True)
        self.product_choice = QtWidgets.QCheckBox("Product")
        self.product_choice.setChecked(True)
        self.addition_choice = QtWidgets.QCheckBox("Addition")
        self.combine_group.addButton(self.product_choice)
        self.combine_group.addButton(self.addition_choice)
        input_field_layout.addWidget(self.combine_label)
        input_field_layout.addWidget(self.product_choice)
        input_field_layout.addWidget(self.addition_choice)
        self.group_box.setHidden(True)

        row = QtWidgets.QToolBar()
        row.addWidget(header("Scenarios:"))
        row.addAction(
            qicons.question, "Scenarios help",
            self.explanation
        )
        row.addWidget(self.table_btn)
        tool_row = QtWidgets.QHBoxLayout()
        tool_row.addWidget(row)
        tool_row.addWidget(self.group_box)
        tool_row.addStretch(1)
        layout.addLayout(tool_row)
        layout.addLayout(self.scenario_tables)
        layout.addStretch(1)
        self.setLayout(layout)
        self._connect_signals()

    def _connect_signals(self) -> None:
        self.table_btn.clicked.connect(self.add_table)
        self.table_btn.clicked.connect(self.can_add_table)
        signals.project_selected.connect(self.clear_tables)
        signals.project_selected.connect(self.can_add_table)
        signals.parameter_superstructure_built.connect(self.handle_superstructure_signal)

    def scenario_names(self, idx: int) -> list:
        if idx > len(self.tables):
            return []
        return scenario_names_from_df(self.tables[idx])

    def combined_dataframe(self) -> pd.DataFrame:
        """Return a dataframe that combines the scenarios of multiple tables.
        """
        if not self.tables:
            # Return an empty dataframe, will almost immediately cause a
            # validation exception.
            return pd.DataFrame()
        data = [df for df in (t.dataframe for t in self.tables) if not df.empty]
        if not data:
            return pd.DataFrame()
        manager = SuperstructureManager(*data)
        if self.product_choice.isChecked():
            kind = "product"
        elif self.addition_choice.isChecked():
            kind = "addition"
        else:
            kind = "none"
        return manager.combined_data(kind)

    @Slot(name="addTable")
    def add_table(self) -> None:
        new_idx = len(self.tables)
        widget = ScenarioImportWidget(new_idx, self)
        self.tables.append(widget)
        self.scenario_tables.addWidget(widget)
        self.updateGeometry()

    @Slot(int, name="removeTable")
    def remove_table(self, idx: int) -> None:
        w = self.tables.pop(idx)
        self.scenario_tables.removeWidget(w)
        w.deleteLater()
        self.updateGeometry()
        # Do not forget to update indexes!
        for i, w in enumerate(self.tables):
            w.index = i

    @Slot(name="clearTables")
    def clear_tables(self) -> None:
        """Clear all scenario tables in certain cases (eg. project change)."""
        for w in self.tables:
            self.scenario_tables.removeWidget(w)
            w.deleteLater()
        self.tables = []
        self.updateGeometry()

    def updateGeometry(self):
        self.group_box.setHidden(len(self.tables) <= 1)
        # Make sure that scenario tables are equally balanced within the box.
        if self.tables:
            table_width = self.width() / len(self.tables)
            for table in self.tables:
                table.setMaximumWidth(table_width)
        super().updateGeometry()

    @Slot(name="canAddTable")
    def can_add_table(self) -> None:
        """Use this to set a hardcoded limit on the amount of scenario tables
        a user can add.
        """
        self.table_btn.setEnabled(len(self.tables) < self.MAX_TABLES)

    @Slot(int, object, name="handleSuperstructureSignal")
    def handle_superstructure_signal(self, table_idx: int, df: pd.DataFrame) -> None:
        table = self.tables[table_idx]
        table.sync_superstructure(df)


class ScenarioImportWidget(QtWidgets.QWidget):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)

        self.index = index
        self.scenario_name = QtWidgets.QLabel("<filename>", self)
        self.load_btn = QtWidgets.QPushButton(qicons.import_db, "Load")
        self.load_btn.setToolTip("Load (new) data for this scenario table")
        self.remove_btn = QtWidgets.QPushButton(qicons.delete, "Delete")
        self.remove_btn.setToolTip("Remove this scenario table")
        self.table = ScenarioImportTable(self)
        self.scenario_df = pd.DataFrame(columns=SUPERSTRUCTURE)

        layout = QtWidgets.QVBoxLayout()

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.scenario_name)
        row.addWidget(self.load_btn)
        row.addStretch(1)
        row.addWidget(self.remove_btn)

        layout.addLayout(row)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self._connect_signals()

    def _connect_signals(self):
        self.load_btn.clicked.connect(self.load_action)
        parent = self.parent()
        if parent and isinstance(parent, ScenarioImportPanel):
            self.remove_btn.clicked.connect(
                lambda: parent.remove_table(self.index)
            )
            self.remove_btn.clicked.connect(parent.can_add_table)

    @Slot(name="loadScenarioFile")
    def load_action(self) -> None:
        dialog = ExcelReadDialog(self)
        if dialog.exec_() == ExcelReadDialog.Accepted:
            path = dialog.path
            idx = dialog.import_sheet.currentIndex()
            QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
            print('Loading Scenario file. This may take a while for large files')
            try:
                # Try and read as a superstructure file
                df = import_from_excel(path, idx)
                self.sync_superstructure(df)
            except (IndexError, ValueError) as e:
                # Try and read as parameter scenario file.
                print("Superstructure: {}\nAttempting to read as parameter scenario file.".format(e))
                df = pd.read_excel(path, sheet_name=idx, engine="openpyxl")
                include_default = True
                if "default" not in df.columns:
                    query = QtWidgets.QMessageBox.question(
                        self, "Default column not found",
                        "Attempt to load and include the 'default' scenario column?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No
                    )
                    if query == QtWidgets.QMessageBox.No:
                        include_default = False
                signals.parameter_scenario_sync.emit(self.index, df, include_default)
            finally:
                self.scenario_name.setText(path.name)
                self.scenario_name.setToolTip(path.name)
            QtWidgets.QApplication.restoreOverrideCursor()

    def sync_superstructure(self, df: pd.DataFrame) -> None:
        # TODO: Move the 'scenario_df' into the model itself.
        self.scenario_df = df
        cols = scenario_names_from_df(self.scenario_df)
        self.table.model.sync(cols)

    @property
    def dataframe(self) -> pd.DataFrame:
        if self.scenario_df.empty:
            print("No data in scenario table {}, skipping".format(self.index + 1))
        return self.scenario_df

from typing import Sequence

import PySAM.BatteryStateful as BatteryModel
import PySAM.BatteryTools as BatteryTools
import PySAM.Singleowner as Singleowner

from hybrid.power_source import *

class Battery_Outputs:
    def __init__(self, n_timesteps):
        """ Class of stateful battery outputs

        """
        self.stateful_attributes = ['I', 'P', 'Q', 'SOC', 'T_batt', 'gen']
        for attr in self.stateful_attributes:
            setattr(self, attr, [0.0]*n_timesteps)

        # dispatch output storage
        dispatch_attributes = ['I', 'P', 'SOC']
        for attr in dispatch_attributes:
            setattr(self, 'dispatch_'+attr, [0.0]*n_timesteps)


class Battery(PowerSource):
    _system_model: BatteryModel.BatteryStateful
    _financial_model: Singleowner.Singleowner

    module_specs = {'capacity': 400, 'surface_area': 30} # 400 [kWh] -> 30 [m^2]

    def __init__(self,
                 site: SiteInfo,
                 system_capacity_kwh: float,
                 chemistry: str = 'lfpgraphite',
                 system_voltage_volts: float = 500,
                 system_capacity_kw: float = None):
        """

        :param system_capacity_kwh:
        :param system_voltage_volts:
        """
        system_model = BatteryModel.default(chemistry)
        self.Outputs = Battery_Outputs(n_timesteps=site.n_timesteps)
        BatteryTools.battery_model_sizing(system_model,
                                          0.,
                                          system_capacity_kwh,
                                          system_voltage_volts,
                                          module_specs=Battery.module_specs)

        financial_model = Singleowner.from_existing(system_model, "GenericBatterySingleOwner")
        super().__init__("Battery", site, system_model, financial_model)

        if system_capacity_kw is not None:
            self.system_capacity_kw = system_capacity_kw

        # Minimum set of parameters to set to get statefulBattery to work
        self._system_model.value("control_mode", 0.0)
        self._system_model.value("input_current", 0.0)
        self._system_model.value("dt_hr", 1.0)
        self._system_model.value("minimum_SOC", 10.0)
        self._system_model.value("maximum_SOC", 90.0)
        self._system_model.value("initial_SOC", 10.0)
        self._system_model.setup()

        self._dispatch = None   # TODO: this could be the union of the models

    @property
    def system_capacity_voltage(self) -> tuple:
        return self._system_model.ParamsPack.nominal_energy, self._system_model.ParamsPack.nominal_voltage

    @system_capacity_voltage.setter
    def system_capacity_voltage(self, capacity_voltage: tuple):
        """
        Sets the system capacity and voltage, and updates the system, cost and financial model
        :param capacity_voltage:
        :return:
        """
        size_kwh = capacity_voltage[0]
        voltage_volts = capacity_voltage[1]

        BatteryTools.battery_model_sizing(self._system_model,
                                          0.,
                                          size_kwh,
                                          voltage_volts,
                                          module_specs=Battery.module_specs)
        logger.info("Battery set system_capacity to {} kWh".format(size_kwh))
        logger.info("Battery set system_voltage to {} volts".format(voltage_volts))

    @property
    def system_capacity_kwh(self) -> float:
        return self._system_model.ParamsPack.nominal_energy

    @system_capacity_kwh.setter
    def system_capacity_kwh(self, size_kwh: float):
        """
        Sets the system capacity and updates the system, cost and financial model
        :param size_kwh:
        :return:
        """
        self.system_capacity_voltage = (size_kwh, self.system_voltage_volts)

    @property
    def system_capacity_kw(self) -> float:
        return self._system_model.ParamsPack.nominal_energy * self._system_model.ParamsCell.C_rate

    @system_capacity_kw.setter
    def system_capacity_kw(self, size_kw: float):
        """
        Sets the system capacity and updates the system, cost and financial model
        :param size_kw:
        :return:
        """
        self._system_model.value("C_rate", size_kw/self._system_model.ParamsPack.nominal_energy)

    @property
    def system_voltage_volts(self) -> float:
        return self._system_model.ParamsPack.nominal_voltage

    @system_voltage_volts.setter
    def system_voltage_volts(self, voltage_volts: float):
        """
        Sets the system voltage and updates the system, cost and financial model
        :param voltage_volts:
        :return:
        """
        self.system_capacity_voltage = (self.system_capacity_kwh, voltage_volts)

    @property
    def chemistry(self) -> str:
        model_type = self._system_model.ParamsCell.chem
        if model_type == 0:
            return "0 [LeadAcid]"
        elif model_type == 1:
            return "1 [nmcgraphite or lfpgraphite]"
            # TODO: Currently, there is no way to tell the difference...
        else:
            raise ValueError("chemistry model type unrecognized")

    @chemistry.setter
    def chemistry(self, battery_chemistry: str):
        """
        Sets the system chemistry and updates the system, cost and financial model
        :param battery_chemistry:
        :return:
        """
        BatteryTools.battery_model_change_chemistry(self._system_model, battery_chemistry)
        logger.info("Battery chemistry set to {}".format(battery_chemistry))

    def simulate_with_dispatch(self, n_periods: int, sim_start_time: int = None):
        """
        Step through dispatch solution for battery and simulate battery
        """
        # TODO: This is specific to the Stateful battery model
        # Set stateful control value [Discharging (+) + Charging (-)]
        if self.value("control_mode") == 1.0:
            control = [pow_MW*1e3 for pow_MW in self.dispatch.power]    # MW -> kW
        elif self.value("control_mode") == 0.0:
            control = [cur_MA * 1e6 for cur_MA in self.dispatch.current]    # MA -> A
        else:
            raise ValueError("Stateful battery module 'control_mode' invalid value.")

        time_step_duration = self.dispatch.time_duration
        for t in range(n_periods):
            self.value('dt_hr', time_step_duration[t])
            self.value(self.dispatch.control_variable, control[t])

            # Only store information if passed the previous day simulations (used in clustering)
            try:
                index_time_step = sim_start_time + t  # Store information
            except TypeError:
                index_time_step = None  # Don't store information
            self.simulate(time_step=index_time_step)

        # Store Dispatch model values
        if sim_start_time is not None:
            time_slice = slice(sim_start_time, sim_start_time + n_periods)
            self.Outputs.dispatch_SOC[time_slice] = self.dispatch.soc[0:n_periods]
            self.Outputs.dispatch_P[time_slice] = self.dispatch.power[0:n_periods]
            self.Outputs.dispatch_I[time_slice] = self.dispatch.current[0:n_periods]

    def simulate(self, time_step=None):
        """
        Runs battery simulate stores values if time step is provided
        """
        if not self._system_model:
            return
        self._system_model.execute(0)

        if time_step is not None:
            self.update_battery_stored_values(time_step)

        # TODO: Do we need to update financial model after battery simulation is complete?

    def update_battery_stored_values(self, time_step):
        # Physical model values
        for attr in self.Outputs.stateful_attributes:
            if hasattr(self._system_model.StatePack, attr):
                getattr(self.Outputs, attr)[time_step] = self.value(attr)
            else:
                if attr == 'gen':
                    getattr(self.Outputs, attr)[time_step] = self.value('P')

    def simulate_financials(self, project_life):
        # TODO: updated replacement values -> based on usage...
        self._financial_model.value('batt_bank_replacement', [0]*project_life)

        if project_life > 1:
            self._financial_model.Lifetime.system_use_lifetime_output = 1
        else:
            self._financial_model.Lifetime.system_use_lifetime_output = 0
        self._financial_model.FinancialParameters.analysis_period = project_life

        self._financial_model.value("construction_financing_cost", self.get_construction_financing_cost())
        self._financial_model.Revenue.ppa_soln_mode = 1
        # TODO: out to get SystemOutput.gen to populate?
        # if len(self._financial_model.SystemOutput.gen) == self.site.n_timesteps:
        if len(self.Outputs.gen) == self.site.n_timesteps:
            single_year_gen = self.Outputs.gen
            self._financial_model.SystemOutput.gen = list(single_year_gen) * project_life

            self._financial_model.SystemOutput.system_pre_curtailment_kwac = list(single_year_gen) * project_life
            self._financial_model.SystemOutput.annual_energy_pre_curtailment_ac = sum(single_year_gen)

        self._financial_model.execute(0)
        logger.info("{} simulation executed".format('battery'))

    def generation_profile(self) -> Sequence:
        if self.system_capacity_kwh:
            return self.Outputs.gen
        else:
            return [0] * self.site.n_timesteps

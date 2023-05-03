from typing import Union, Optional, Sequence, Any
import PySAM.Pvsamv1 as Pvsam
import PySAM.Singleowner as Singleowner

from hybrid.power_source import *
from hybrid.layout.pv_design_utils import *
from hybrid.layout.pv_layout import PVLayout, PVGridParameters
from hybrid.dispatch.power_sources.pv_dispatch import PvDispatch


class DetailedPVPlant(PowerSource):
    _system_model: Pvsam.Pvsamv1
    _financial_model: Union[Any, Singleowner.Singleowner]
    _layout: Union[Any, PVLayout]
    _dispatch: PvDispatch

    def __init__(self,
                 site: SiteInfo,
                 pv_config: dict):
        """

        :param pv_config: dict, with following keys:
            'tech_config': dict, contains parameters for pvsamv1 technology model
            'fin_model': optional financial model object to use instead of singleowner model
            'layout_model': optional layout model object to use instead of the PVLayout model
            'layout_params': optional DetailedPVParameters, the design vector w/ values. Required for layout modeling
        """
        system_model = Pvsam.default("FlatPlatePVSingleOwner")

        if 'fin_model' in pv_config.keys():
            financial_model = pv_config['fin_model']
        else:
            financial_model = Singleowner.from_existing(system_model, "FlatPlatePVSingleOwner")

        super().__init__("SolarPlant", site, system_model, financial_model)

        self._system_model.SolarResource.solar_resource_data = self.site.solar_resource.data
        self.dc_degradation = [0]

        if 'layout_model' in pv_config.keys():
            self._layout = pv_config['layout_model']
            self._layout._system_model = self._system_model
        else:
            if 'layout_params' in pv_config.keys():
                params: PVGridParameters = pv_config['layout_params']
            else:
                params = None
            self._layout = PVLayout(site, system_model, params)

        self._dispatch: PvDispatch = None
        self.processed_assign(pv_config)

    def processed_assign(self, params):
        """
        Assign attributes from dictionaries with additional processing
        to enforce coherence between attributes
        """
        if 'tech_config' in params.keys():
            config = params['tech_config']
            
            if 'subarray2_enable' in config.keys() and config['subarray2_enable'] == 1 \
              or 'subarray3_enable' in config.keys() and config['subarray3_enable'] == 1 \
              or 'subarray4_enable' in config.keys() and config['subarray4_enable'] == 1:
                raise Exception('Detailed PV plant currently only supports one subarray.')

            # Get PV module attributes
            system_params = flatten_dict(self._system_model.export())
            system_params.update(config)
            module_attribs = get_module_attribs(system_params)

            # Verify system capacity is cohesive with interdependent parameters if all are specified
            nstrings_keys = [f'subarray{i}_nstrings' for i in range(1, 5)]
            if 'system_capacity' in config.keys() and any(nstrings in config.keys() for nstrings in nstrings_keys):               
                # Build subarray electrical configuration input lists
                n_strings = []
                modules_per_string = []
                for i in range(1, 5):
                    if i == 1:
                        subarray_enabled = True
                    else:
                        subarray_enabled = config[f'subarray{i}_enable'] \
                                           if f'subarray{i}_enable' in config.keys() \
                                           else self.value(f'subarray{i}_enable')

                    if not subarray_enabled:
                        n_strings.append(0)
                    elif f'subarray{i}_nstrings' in config.keys():
                        n_strings.append(config[f'subarray{i}_nstrings'])
                    else:
                        try:
                            n_strings.append(self.value(f'subarray{i}_nstrings'))
                        except:
                            n_strings.append(0)

                    if f'subarray{i}_modules_per_string' in config.keys():
                        modules_per_string.append(config[f'subarray{i}_modules_per_string'])
                    else:
                        try:
                            modules_per_string.append(self.value(f'subarray{i}_modules_per_string'))
                        except:
                            modules_per_string.append(0)

                config['system_capacity'] = verify_capacity_from_electrical_parameters(
                    system_capacity_target=config['system_capacity'],
                    n_strings=n_strings,
                    modules_per_string=modules_per_string,
                    module_power=module_attribs['P_mp_ref']
                )
            
                # Set all interdependent parameters directly and at once to avoid interdependent changes with existing values via properties
                if 'system_capacity' in config.keys():
                    self._system_model.value('system_capacity', config['system_capacity'])
                for i in range(1, 5):
                    if f'subarray{i}_nstrings' in config.keys():
                        self._system_model.value(f'subarray{i}_nstrings', config[f'subarray{i}_nstrings'])
                    if f'subarray{i}_modules_per_string' in config.keys():
                        self._system_model.value(f'subarray{i}_modules_per_string', config[f'subarray{i}_modules_per_string'])
                if 'module_model' in config.keys():
                    self._system_model.value('module_model', config['module_model'])
                if 'module_aspect_ratio' in config.keys():
                    self._system_model.value('module_aspect_ratio', config['module_aspect_ratio'])
                for key in config.keys():
                    # set module parameters:
                    if key.startswith('spe_') \
                      or key.startswith('cec_') \
                      or key.startswith('sixpar_') \
                      or key.startswith('snl_') \
                      or key.startswith('sd11par_') \
                      or key.startswith('mlm_'):
                        self._system_model.value(key, config[key])

            # Set all parameters
            self.assign(config)

        self._layout.set_layout_params(self.system_capacity, self._layout.parameters)

    def simulate_financials(self, interconnect_kw: float, project_life: int):
        """
        Runs the finanical model
        
        :param interconnect_kw: ``float``,
            Hybrid interconnect limit [kW]
        :param project_life: ``int``,
            Number of year in the analysis period (execepted project lifetime) [years]
        :return:
        """   
        if not self._financial_model:
            return
        if self.system_capacity_kw <= 0:
            return

        self._financial_model.value('batt_replacement_option', self._system_model.BatterySystem.batt_replacement_option)
        self._financial_model.value('en_standalone_batt', self._system_model.BatterySystem.en_standalone_batt)
        self._financial_model.value('om_batt_replacement_cost', self._system_model.SystemCosts.om_batt_replacement_cost)
        self._financial_model.value('om_replacement_cost_escal', self._system_model.SystemCosts.om_replacement_cost_escal)
        super().simulate_financials(interconnect_kw, project_life)

    @property
    def system_capacity(self) -> float:
        """pass through to established name property"""
        return self.system_capacity_kw

    @system_capacity.setter
    def system_capacity(self, size_kw: float):
        """pass through to established name setter"""
        self.system_capacity_kw = size_kw

    @property
    def system_capacity_kw(self) -> float:
        return self._system_model.value('system_capacity')      # [kW] DC

    @system_capacity_kw.setter
    def system_capacity_kw(self, size_kw: float):
        """
        Sets the system capacity
        :param size_kw: DC system size in kW
        :return:
        """
        self._system_model.value('system_capacity', size_kw)

    @property
    def dc_degradation(self) -> float:
        """Annual DC degradation for lifetime simulations [%/year]"""
        return self._system_model.Lifetime.dc_degradation

    @dc_degradation.setter
    def dc_degradation(self, dc_deg_per_year: Sequence):
        self._system_model.Lifetime.dc_degradation = dc_deg_per_year

    @property
    def dc_ac_ratio(self) -> float:
        return self.system_capacity / (self.n_inverters * self.inverter_power)

    @property
    def module_power(self) -> float:
        """Module power in kW"""
        module_attribs = get_module_attribs(self._system_model)
        return module_attribs['P_mp_ref']

    @property
    def module_width(self) -> float:
        """Module width in meters"""
        module_attribs = get_module_attribs(self._system_model)
        return module_attribs['width']

    @property
    def module_length(self) -> float:
        """Module length in meters"""
        module_attribs = get_module_attribs(self._system_model)
        return module_attribs['length']

    @property
    def module_height(self) -> float:
        """Module height in meters"""
        return self.module_length

    @property
    def inverter_power(self) -> float:
        """Inverter power in kW"""
        return get_inverter_power(self._system_model)

    @property
    def modules_per_string(self) -> float:
        """Modules per string"""
        return self._system_model.SystemDesign.subarray1_modules_per_string

    @modules_per_string.setter
    def modules_per_string(self, _modules_per_string: float):
        """Sets the modules per string and updates the system capacity"""
        self._system_model.SystemDesign.subarray1_modules_per_string = _modules_per_string
        self._system_model.SystemDesign.subarray2_modules_per_string = 0 
        self._system_model.SystemDesign.subarray3_modules_per_string = 0
        self._system_model.SystemDesign.subarray4_modules_per_string = 0
        self.system_capacity = self.module_power * _modules_per_string * self.n_strings

    @property
    def n_strings(self) -> float:
        """Total number of strings"""
        return self._system_model.SystemDesign.subarray1_nstrings \
               + self._system_model.SystemDesign.subarray2_nstrings \
               + self._system_model.SystemDesign.subarray3_nstrings \
               + self._system_model.SystemDesign.subarray4_nstrings

    @n_strings.setter
    def n_strings(self, _n_strings: float):
        """Sets the total number of strings and updates the system capacity"""
        self._system_model.SystemDesign.subarray1_nstrings = _n_strings
        self._system_model.SystemDesign.subarray2_nstrings = 0 
        self._system_model.SystemDesign.subarray3_nstrings = 0
        self._system_model.SystemDesign.subarray4_nstrings = 0
        self.system_capacity = self.module_power * self.modules_per_string * _n_strings

    @property
    def n_inverters(self) -> float:
        """Total number of inverters"""
        return self._system_model.SystemDesign.inverter_count

    @n_inverters.setter
    def n_inverters(self, _n_inverters: float):
        """Sets the total number of inverters"""
        self._system_model.SystemDesign.inverter_count = _n_inverters

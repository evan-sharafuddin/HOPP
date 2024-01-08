
from hopp.simulation.technologies.hydrogen.electrolysis import run_h2_PEM
import numpy as np
import pandas as pd

#These are good defaults - don't need to worry about them
simulation_length = 8760 #1 year
plant_life = 30 #years
use_degradation_penalty=True
grid_connection_scenario = 'off-grid'
EOL_eff_drop = 10
pem_control_type = 'basic' #basic control = baseline control
user_defined_pem_param_dictionary = {
    "Modify BOL Eff": False,
    "BOL Eff [kWh/kg-H2]": [],
    "Modify EOL Degradation Value": True,
    "EOL Rated Efficiency Drop": EOL_eff_drop,
}

def simple_hydrogen_production_estimation(wind_generation_kWh,electrolyzer_size_mw,n_stacks,turndown_ratio = 0.1):
    electrolyzer_size_kW = electrolyzer_size_mw*1e3
    stack_size_kW = electrolyzer_size_kW/n_stacks
    minimum_power_kWh = stack_size_kW*turndown_ratio
    #saturate wind power at electrolyzer capacity
    usable_power_kWh = np.where(wind_generation_kWh>electrolyzer_size_kW,electrolyzer_size_kW,wind_generation_kWh)
    #can't use any power below turndown ratio
    usable_power_kWh = np.where(wind_generation_kWh<minimum_power_kWh,0,wind_generation_kWh)

    rated_electrolyzer_efficiency = 54.61073251891887 #kWh/kg
    simple_hydrogen_hourly_production = usable_power_kWh*(1/rated_electrolyzer_efficiency) #kg/hr

    return simple_hydrogen_hourly_production
def run_electrolyzer(wind_generation_kWh,electrolyzer_size_mw,number_electrolyzer_stacks):
    """
    Inputs
    ----------
    wind_generation_kWh : np.array of len() = 8760
        hourly wind generation profile in units of kWh
    electrolyzer_size_mw : int
        total installed electrolyzer capacity [MW]
    number_electrolyzer_stacks : int
        the number of electrolyzer stacks in electrolyzer farm

    Returns
    -------
    H2_Results : dict
        includes performance info of electrolyzer used for LCOH calc
    aH2p_avg : float
        annual average hydrogen production across plant life [kg/year]
    """
    #01: define electrolyzer inputs

    #here is where we run the electrolyzer
    H2_Results, H2_Timeseries, H2_Summary,energy_input_to_electrolyzer =\
    run_h2_PEM.run_h2_PEM(wind_generation_kWh,
    electrolyzer_size_mw,
    plant_life, number_electrolyzer_stacks,[],
    pem_control_type,100,user_defined_pem_param_dictionary,
    use_degradation_penalty,grid_connection_scenario,[])

    #H2 production per year of plant life in kg-H2/year
    aH2p_life = H2_Results['Performance Schedules']['Annual H2 Production [kg/year]'].values
    aH2p_avg = np.mean(aH2p_life)
    return H2_Results, aH2p_avg
def calculate_hydrogen_storage_capacity(hydrogen_hourly_production,hydrogen_demand_kg_pr_hr = None):
    if hydrogen_demand_kg_pr_hr is None:
        hydrogen_demand_kg_pr_hr = np.mean(hydrogen_hourly_production)
    diff = hydrogen_hourly_production - hydrogen_demand_kg_pr_hr
    diff = np.insert(diff,0,0)
    fake_soc = np.cumsum(diff)
    hydrogen_storage_size_kg = np.abs(np.max(fake_soc)- np.min(fake_soc))

    return hydrogen_storage_size_kg
def simple_approximate_lcoh(electrolyzer_size_mw, H2_Results, electrolyzer_unit_capex = 500, stack_replacement_cost = 15/100,discount_rate = 0.08):
    """
    Inputs
    ----------
    electrolyzer_size_mw : int
        total installed electrolyzer capacity [MW]
    H2_Results : dict
        includes performance info of
    electrolyzer_unit_capex : float or int
        uninstalled electrolyzer direct capex cost in $/kW
    stack_replacement_cost : float (between 0 and 1)
        percent of overnight electrolyzer capex that is required to replace a stack
    discount_rate : float (between 0 and 1)
        annually applied discount rate
    Returns
    -------
    LCOH_approx : float
        approximate ratio of electrolyzer costs to hydrogen produced [$/kg-H2]
    """
    years = np.arange(0,plant_life,1)
    # stack_replacement_cost = 15/100  #[% of installed capital cost]
    variable_OM = 1.30  #[$/MWh]
    fixed_OM = 12.8 #[$/kW-y]
    install_factor = 0.12
    indirect_cost_factor = 0.42
    electrolyzer_overnight_unit_capex = electrolyzer_unit_capex*(1+install_factor)*(1+indirect_cost_factor) #[$/kW]
    electrolyzer_total_CapEx = electrolyzer_overnight_unit_capex*(electrolyzer_size_mw*1e3) #[$]

    #H2 production per year of plant life in kg-H2/year
    aH2p_life = H2_Results['Performance Schedules']['Annual H2 Production [kg/year]'].values
    percent_of_capacity_replaced = H2_Results['Performance Schedules']['Refurbishment Schedule [MW replaced/year]'].values/electrolyzer_size_mw
    elec_efficiency_per_yr_kWhprkg=H2_Results['Performance Schedules']['Annual Average Efficiency [kWh/kg]'].values
    
    electrolyzer_refurbishment_schedule = percent_of_capacity_replaced*stack_replacement_cost
    variable_OM_perkg = (variable_OM/1000)*elec_efficiency_per_yr_kWhprkg #[$/kg-year]
    variable_OM_total = variable_OM_perkg*aH2p_life #[$/year]
    fixed_OM_total = np.ones(plant_life)*fixed_OM*(electrolyzer_size_mw*1e3) #[$/year]
    stack_replacement_total = electrolyzer_refurbishment_schedule*electrolyzer_total_CapEx #[$/year]
    
    denom = (1+discount_rate)**years
    
    hydrogen_per_year = [(aH2p_life[i])/(denom[i]) for i in years]
    variable_om_per_year = [(variable_OM_total[i])/(denom[i]) for i in years]
    fixed_om_per_year = [(fixed_OM_total[i])/(denom[i]) for i in years]
    stack_rep_per_year = [(stack_replacement_total[i])/(denom[i]) for i in years]
    elec_opex_pr_year = np.array(variable_om_per_year) + np.array(fixed_om_per_year) + np.array(stack_rep_per_year)
    
    elec_capex_per_year = np.zeros(plant_life)
    elec_capex_per_year[0] = electrolyzer_total_CapEx
    elec_cost_per_year = elec_opex_pr_year + elec_capex_per_year
    # LCOH_approx = (electrolyzer_total_CapEx/hydrogen_per_year[0]) + sum(elec_opex_pr_year[i]/hydrogen_per_year[i] for i in years)
    LCOH_approx =  sum(elec_cost_per_year[i]/hydrogen_per_year[i] for i in years)
    
    return LCOH_approx


wind_generation_kWh = np.array([0]) #output from WPGNN

#wind turbine
n_turbines = 10
turbine_size_MW = 6 #MW
wind_farm_capacity = turbine_size_MW*n_turbines #MW

#electrolyzer
stack_size_MW = 10
n_stacks = 6 #could set n_stacks = 1
electrolyzer_size_MW = n_stacks*stack_size_MW

#simplified method for estimating hydrogen production from power timeseries
hydrogen_hourly_production_kg_simple = simple_hydrogen_production_estimation(wind_generation_kWh,electrolyzer_size_MW,n_stacks)

#actually run the electrolyzer for layout optimization to maximize annual_H2
H2_Results, annual_H2 = run_electrolyzer(wind_generation_kWh,electrolyzer_size_MW,n_stacks)

#OR layout optimization to minimize hydrogen_storage_capacity
hydrogen_hourly_production = H2_Results['hydrogen_hourly_production']
hydrogen_storage_capacity = calculate_hydrogen_storage_capacity(hydrogen_hourly_production)

#Later: optimize to reduce LCOH
LCOH_estimate = simple_approximate_lcoh(electrolyzer_size_MW, H2_Results)
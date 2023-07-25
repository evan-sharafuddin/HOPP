import os
import sys
import warnings
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import numpy_financial as npf
import matplotlib.pyplot as plt
import warnings
from pathlib import Path
import time
from multiprocessing import Pool

from hybrid.sites import SiteInfo
from hybrid.sites import flatirons_site as sample_site
from hybrid.keys import set_developer_nrel_gov_key

# from plot_reopt_results import plot_reopt_results
# from run_reopt import run_reopt
# import jsonrun_profast_for_hydrogen

from examples.H2_Analysis.hopp_for_h2 import hopp_for_h2
from examples.H2_Analysis.run_h2a import run_h2a as run_h2a
from examples.H2_Analysis.simple_dispatch import SimpleDispatch
from examples.H2_Analysis.simple_cash_annuals import simple_cash_annuals
import examples.H2_Analysis.run_h2_PEM as run_h2_PEM

from lcoe.lcoe import lcoe as lcoe_calc

import hopp_tools
import inputs_py
import copy 
import plot_results
import run_RODeO
import run_profast_for_hydrogen
import run_profast_for_steel

from green_industry_run_scenarios import batch_generator_kernel
from green_concrete.cement_plant import CementPlant

from itertools import product

'''
Use this script to run cement plant simulations.

NOTE configuration options are below under the name = main statement, 
comment out options that you don't want

See HOPP/green_concrete for more information on the cement plant configurations

'''

def simulate_cement_plant(
        ccus_input,
        fuel_mix_input,
        hybrid_electricity_input,
        cli_to_cem_input,
        atb_year_input,
        site_location_input,
        cli_production_input,
        plant_life_input,
        plant_capacity_factor_input,
        couple_with_steel_ammonia_input,
        grid_connection_case_input,
):

    cement_plant = CementPlant(
        ccus=ccus_input, 
        fuel_mix=fuel_mix_input,
        hybrid_electricity=hybrid_electricity_input,
        cli_to_cem=cli_to_cem_input,
        atb_year=atb_year_input,
        site_location=site_location_input, 
        cli_production=cli_production_input, 
        plant_life=plant_life_input,
        plant_capacity_factor=plant_capacity_factor_input, 
        couple_with_steel_ammonia=couple_with_steel_ammonia_input,
        grid_connection_case=grid_connection_case_input,
    )

    warnings.filterwarnings("ignore")
    sys.path.append('')

    # Establish directories
    parent_path = os.path.abspath('')
    #results_dir = parent_path + '\\examples\\H2_Analysis\\results\\'
    results_dir = parent_path + '/examples/H2_Analysis/results/'
    fin_sum_dir = parent_path + '/examples/H2_Analysis/Phase1B/Fin_summary/'
    energy_profile_dir = parent_path + '/examples/H2_Analysis/Phase1B/Energy_profiles/'
    price_breakdown_dir = parent_path + '/examples/H2_Analysis/Phase1B/ProFAST_price/'
    floris_dir = parent_path + '/floris_input_files/'
    orbit_path = ('examples/H2_Analysis/OSW_H2_sites_turbines_and_costs.xlsx')
    renewable_cost_path = ('examples/H2_Analysis/green_steel_site_renewable_costs_ATB.xlsx')

    # NOTE have not implemented FLORIS for green_concrete
    floris = False # otherwise pySAM

    # Turn to False to run ProFAST for hydrogen LCOH (ALWAYS FALSE)
    run_RODeO_selector = False

    # Grid price scenario ['wholesale','retail-peaks','retail-flat']
    grid_price_scenario = 'retail-flat'

    if run_RODeO_selector == True:
        # RODeO requires output directory in this format, but apparently this format
        # is problematic for people who use Mac
        rodeo_output_dir = 'examples\\H2_Analysis\\RODeO_files\\Output_test\\'
    else:
        # People who use Mac probably won't be running RODeO, so we can just give
        # the model a dummy string for this variable
        rodeo_output_dir = 'examples/H2_Analysis/RODeO_files/Output_test/'

    # Distributed scale power electronics direct coupling information
    direct_coupling = True

    # Electrolzyer cost case ('Mid' or 'Low')
    electrolyzer_cost_case = 'Low'

    # Degradation penalties for capital costs to estimate cost of plant oversizing
    electrolyzer_degradation_power_increase = 0.13
    wind_plant_degradation_power_decrease = 0.08

    # Determine if run with electrolyzer degradation or not
    electrolyzer_degradation_penalty = True

    # Determine if PEM stack operation is optimized or not
    pem_control_type = 'basic' #use 'optimize' for Sanjana's controller; 'basic' to not optimize
        
    save_hybrid_plant_yaml = True # hybrid_plant requires special processing of the SAM objects
    save_model_input_yaml = True # saves the inputs for each model/major function
    save_model_output_yaml = True # saves the outputs for each model/major function

    # Target steel production rate. Note that this is the production after taking into account
    # steel plant capacity factor. E.g., if CF is 0.9, divide the number below by 0.9 to get
    # the total steel plant capacity used for economic calculations
    if cement_plant.config['Steel & Ammonia']:
        steel_annual_production_rate_target_tpy = 1000000
    else:
        steel_annual_production_rate_target_tpy = 0

    cement_plant.hopp_misc['Steel production rate (tpy)'] = steel_annual_production_rate_target_tpy

    #-------------------- Define scenarios to run----------------------------------
        
    # NOTE for now, set atb_years, site_selection, and grid_connection_cases when constructing CementPlant object
    atb_years = [
                #2020,
                #2025,
                # 2030,
                2035
                ]

    policy = {
        # 'no-policy': {'Wind ITC': 0, 'Wind PTC': 0, "H2 PTC": 0, 'Storage ITC': 0},
        'base': {'Wind ITC': 0, 'Wind PTC': 0.0051, "H2 PTC": 0.6, 'Storage ITC': 0.06},
        # 'max': {'Wind ITC': 0, 'Wind PTC': 0.03072, "H2 PTC": 3.0, 'Storage ITC': 0.5},   
        # 'max on grid hybrid': {'Wind ITC': 0, 'Wind PTC': 0.0051, "H2 PTC": 0.60, 'Storage ITC': 0.06},
        # 'max on grid hybrid': {'Wind ITC': 0, 'Wind PTC': 0.026, "H2 PTC": 0.60, 'Storage ITC': 0.5},
        # 'option 3': {'Wind ITC': 0.06, 'Wind PTC': 0, "H2 PTC": 0.6}, 
        # 'option 4': {'Wind ITC': 0.3, 'Wind PTC': 0, "H2 PTC": 3},
        # 'option 5': {'Wind ITC': 0.5, 'Wind PTC': 0, "H2 PTC": 3}, 
    }

    site_selection = [
                    # 'Site 1', #IN
                    # 'Site 2', #TX
                    'Site 3', #IA
                    # 'Site 4', #MS
                    # 'Site 5' #WY
                    ] 

    electrolysis_cases = [
                            'Centralized',
                        #   'Distributed'
                            ]

    grid_connection_cases = [
                            'off-grid',
                            # 'grid-only',
                            # 'hybrid-grid'
                            ]


    # adjusts hydrogen storage capacity (see run_scenarios 872)
    storage_capacity_cases = [ 
                            1.0,
                            #1.25,
                            #1.5
                            ] 

    num_pem_stacks= 6
    run_solar_param_sweep=False # runs through various solar setups 

    # ensures that the hybrid plant/steel cases are same as those for cement
    if cement_plant:
        atb_years = [cement_plant.config['ATB year']]
        site_selection == [cement_plant.config['site location']]
        grid_connection_cases = [cement_plant.config['Grid connection case']]

    #---- Create list of arguments to pass to batch generator kernel --------------    
    arg_list = []
    for i in policy:
        for atb_year in atb_years:
            for site_location in site_selection:
                for electrolysis_scale in electrolysis_cases:
                    for grid_connection_scenario in grid_connection_cases:
                        for storage_capacity_multiplier in storage_capacity_cases:
                            arg_list.append([policy, i, atb_year, site_location, electrolysis_scale,run_RODeO_selector,floris,\
                                            grid_connection_scenario,grid_price_scenario,\
                                            direct_coupling,electrolyzer_cost_case,electrolyzer_degradation_power_increase,wind_plant_degradation_power_decrease,\
                                                steel_annual_production_rate_target_tpy,parent_path,results_dir,fin_sum_dir,energy_profile_dir,price_breakdown_dir,rodeo_output_dir,floris_dir,renewable_cost_path,\
                                            save_hybrid_plant_yaml,save_model_input_yaml,save_model_output_yaml,num_pem_stacks,run_solar_param_sweep,electrolyzer_degradation_penalty,\
                                                pem_control_type,storage_capacity_multiplier, cement_plant])

    # decide if model requires HOPP based on configurations
    # NOTE HOPP cannot be run if no hydrogen is being produced (divide by zero errors occur with the electrolyzer)

    if cement_plant.config['Steel & Ammonia'] or cement_plant.config['Using hydrogen']:
        # run model using HOPP
        print('running HOPP...')
        cement_plant.hopp_misc['Running HOPP'] = True

        for runs in range(len(arg_list)):
            batch_generator_kernel(arg_list[runs])

    else:
        if cement_plant.config['CCUS'] != 'None':
            # oxygen must be purchased -- no hydrogen is being created 
            cement_plant.feed_consumption['oxygen (purchased)'] = cement_plant.feed_consumption['oxygen (hybrids)']
            cement_plant.feed_consumption['oxygen (hybrids)'] = 0

        if cement_plant.config['Hybrid electricity']:
            raise NotImplementedError('Cannot simulate cement plant with hybrid electricity in this configuration: must be coupled with steel/ammonia or be using hydrogen in the fuel mixture.')
        
        else:
            # run model without using HOPP
            print('not running HOPP...')
            cement_plant.hopp_misc['Running HOPP'] = False

            hopp_dict, solution, summary, price_breakdown, cement_breakeven_price, \
            cement_annual_capacity, cement_production_capacity_margin_pc, cement_price_breakdown = \
            cement_plant.run_pf()

if __name__ == '__main__':
    # comment out undesired configuration options
    inputs = {
        'Carbon capture': [
            'None',
            # 'Oxyfuel',
            # 'CaL (tail-end)',
        ],

        'Fuel mixture': [
            'C1',
            # 'C2',
            # 'C3',
            # 'C4',
            # 'C5',
            # 'C6',
        ],

        'Hybrid electricity': [
            True,
            False,
        ],

        'Clinker-to-cement scenario': [
            'OPC',
            # 'US Average',
            # 'European Average',
        ],

        'Simulation year': [
            2020,
            # 2025,
            # 2030,
            # 2035,
        ],

        'Site location': [
            'IA',
            # 'WY',
            # 'TX',
            # 'MS',
            # 'IN',
        ],

        'Clinker production rate': [
            1e6,
        ],

        'Plant life': [
            25,
        ],
        
        'Plant capacity factor': [
            0.9,
        ],

        'Couple with steel/ammonia': [
            True,
            False,
        ],

        'Grid connection case': [
            # 'off-grid',
            'grid-only',
            # 'hybrid-grid',
        ],
    }

    values = inputs.values()
    combinations = list(product(*values))

    if input(f'{len(combinations)} combinations. Continue? (y/n)\n') != 'y':
        print('Aborting')
    else:
        os.system('cls')
        for combination in combinations:
            print('-----------')
            print(combination)
            
            try:
                simulate_cement_plant(*combination)
            except Exception as e:
                print(repr(e))

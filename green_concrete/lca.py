from green_concrete.convert import btu_to_j
import pandas as pd
import numpy as np
import os.path 

def lca(self):
    
    '''
    Performs a life cycle analysis on the carbon emissions associated with cement production
    
    Adapted from LCA_single_scenario_ProFAST.py

    ASSUMPTIONS
        Oxygen is not considered
            When oxygen is supplied from steel plant, it is assumed that the environmental impact
            for this oxygen is associated with the steel plant, and for the scope of the cement plant
            this oxygen is "carbon free"
            For purchased oxygen, a LCA has not been implemented yet
        TODO add other assumptions here

    Args:
        self: CementPlant() instance
    
    Returns:
        lca_results: dictionary containing LCA data, without carbon capture being applied
        lca_results_ccus: dictionary containing LCA data, with carbon capture multiplyer being applied
    '''

    if self.config['Fuel Mixture'] == 'IEAGHG':
        print('WARNING: this LCA does not account for emissions associated with the alternative fuel mix')

    dircambium = '../Examples/H2_Analysis/Cambium_data/StdScen21_MidCase95by2035_hourly_' 
    dircambium = os.path.join(os.path.split(__file__)[0], dircambium)

    hopp_dict = self.config['Hopp dict']
    site_name = self.config['site location']
    atb_year = self.config['ATB year']
    system_life        = self.config['Plant lifespan']
    # grid_connection_scenario = self.config['Grid connection scenario']

    # Conversions
    g_to_kg_conv  = 0.001  # Conversion from grams to kilograms
    kg_to_MT_conv = 0.001 # Converion from kg to metric tonnes
    MT_to_kg_conv = 1000 # Conversion from metric tonne to kilogram
    kWh_to_MWh_conv = 0.001 # Conversion from kWh to MWh

        ### Grid electricity
        
    grid_trans_losses   = 0.05 # Grid losses of 5% are assumed (-)
    fuel_to_grid_curr   = 48   # Fuel mix emission intensity for current power grid (g CO2e/kWh)
    fuel_to_grid_futu   = 14   # Fuel mix emission intensity for future power grid (g CO2e/kWh)
    
    if atb_year == 2020:
        cambium_year = 2025
    elif atb_year == 2025:
        cambium_year = 2030
    elif atb_year == 2030:
        cambium_year =2035
    elif atb_year == 2035:
        cambium_year = 2040

    # Read in Cambium data  
    cambiumdata_filepath = dircambium + site_name + '_'+str(cambium_year) + '.csv'
    cambium_data = pd.read_csv(cambiumdata_filepath,index_col = None,header = 4,usecols = ['lrmer_co2_c','lrmer_ch4_c','lrmer_n2o_c','lrmer_co2_p','lrmer_ch4_p','lrmer_n2o_p','lrmer_co2e_c','lrmer_co2e_p','lrmer_co2e'])

    cambium_data = cambium_data.reset_index().rename(columns = {'index':'Interval','lrmer_co2_c':'LRMER CO2 combustion (kg-CO2/MWh)','lrmer_ch4_c':'LRMER CH4 combustion (g-CH4/MWh)','lrmer_n2o_c':'LRMER N2O combustion (g-N2O/MWh)',\
                                                'lrmer_co2_p':'LRMER CO2 production (kg-CO2/MWh)','lrmer_ch4_p':'LRMER CH4 production (g-CH4/MWh)','lrmer_n2o_p':'LRMER N2O production (g-N2O/MWh)','lrmer_co2e_c':'LRMER CO2 equiv. combustion (kg-CO2e/MWh)',\
                                                'lrmer_co2e_p':'LRMER CO2 equiv. production (kg-CO2e/MWh)','lrmer_co2e':'LRMER CO2 equiv. total (kg-CO2e/MWh)'})

    cambium_data['Interval']=cambium_data['Interval']+1
    cambium_data = cambium_data.set_index('Interval') 

    if self.hopp_misc['Running HOPP']: 
        solar_size_mw = hopp_dict.main_dict['Configuration']['solar_size']
        storage_size_mw = hopp_dict.main_dict['Configuration']['storage_size_mw']
        # H2_Results = hopp_dict.main_dict['Models']['run_H2_PEM_sim']['output_dict']['H2_Results']
        
        ### Renewable infrastructure embedded emission intensities

        
        ely_stack_capex_EI = 0.019 # PEM electrolyzer CAPEX emissions (kg CO2e/kg H2)
        wind_capex_EI      = 10    # Electricity generation capacity from wind, nominal value taken (g CO2e/kWh)
        if solar_size_mw != 0:
            solar_pv_capex_EI = 37     # Electricity generation capacity from solar pv, nominal value taken (g CO2e/kWh)
        else:
            solar_pv_capex_EI = 0   # Electricity generation capacity from solar pv, nominal value taken (g CO2e/kWh)

        if storage_size_mw != 0:
            battery_EI = 20             # Electricity generation capacity from battery (g CO2e/kWh)
        else:
            battery_EI = 0  # Electricity generation capacity from battery (g CO2e/kWh)
        
            
        energy_from_grid_df = pd.DataFrame(hopp_dict.main_dict["Models"]["grid"]["ouput_dict"]['energy_from_the_grid'],columns=['Energy from the grid (kWh)'])
        energy_from_renewables_df = pd.DataFrame(hopp_dict.main_dict["Models"]["grid"]["ouput_dict"]['energy_from_renewables'],columns=['Energy from renewables (kWh)'])       
        
        # Calculate hourly grid emissions factors of interest. If we want to use different GWPs, we can do that here. The Grid Import is an hourly data i.e., in MWh
        # NOTE since this is a cement LCA, only considering emissions associated with energy production/consumption for cement

        if len(energy_from_grid_df) != len(energy_from_renewables_df):
            raise Exception("grid and renewable energy timeseries not the same length (see green_concrete/lca.py)")
        else: 
            # all have units kg-CO2e
            total_grid_emissions = [0] * len(energy_from_grid_df)
            scope2_grid_emissions = [0] * len(energy_from_grid_df)
            scope3_grid_emissions = [0] * len(energy_from_grid_df)

        for idx in range(len(energy_from_grid_df)):

            energy_used_total = energy_from_grid_df['Energy from the grid (kWh)'][idx] + energy_from_renewables_df['Energy from renewables (kWh)'][idx]
            if energy_used_total == 0:
                grid_frac = 0
            else:
                grid_frac = energy_from_grid_df['Energy from the grid (kWh)'][idx] / energy_used_total

            # finds the total amount of GRID energy used by cement (both electrical and for producing hydrogen), 
            # so steel energy consumption is not considered in the LCA
            if self.config['Hybrid electricity'] != 0: # hybrid plant powering cement, need to account to that amount not going to the electrolyzer
                print('shouldnt be here')
                electricity_demand_cement_hourly = self.feed_consumption['hybrid electricity'] * self.config['Cement Production Rate (annual)'] / 8760
                grid_energy_used_cement = (electricity_demand_cement_hourly + \
                (energy_used_total - electricity_demand_cement_hourly) * self.config['Hydrogen to cement frac']) * grid_frac
            else: # cement plant powered by the grid
                electricity_demand_cement_hourly = self.feed_consumption['grid electricity'] * self.config['Cement Production Rate (annual)'] / 8760
                grid_energy_used_cement = electricity_demand_cement_hourly + \
                (energy_used_total * self.config['Hydrogen to cement frac']) * grid_frac
            

            total_grid_emissions[idx] = grid_energy_used_cement * cambium_data['LRMER CO2 equiv. total (kg-CO2e/MWh)'][idx + 1] / 1000
            scope2_grid_emissions[idx] = grid_energy_used_cement  * cambium_data['LRMER CO2 equiv. combustion (kg-CO2e/MWh)'][idx + 1] / 1000
            scope3_grid_emissions[idx] = grid_energy_used_cement  * cambium_data['LRMER CO2 equiv. production (kg-CO2e/MWh)'][idx + 1] / 1000

        # NOTE since hydrogen emissions are derived from electricity emissions, just pooling those in with the rest of the electricity
        # demand for the plant
    
    else: # hybrid electricity is not enabled --> grid electricity only
        total_grid_emissions = [0] * 8760
        scope2_grid_emissions = [0] * 8760
        scope3_grid_emissions = [0] * 8760

        electricity_demand_cement_hourly = self.feed_consumption['grid electricity'] * self.config['Cement Production Rate (annual)'] / 8760
        
        energy_from_grid = [electricity_demand_cement_hourly] * 8760 
        
        for idx in range(len(energy_from_grid)):
            total_grid_emissions[idx] = energy_from_grid[idx] * cambium_data['LRMER CO2 equiv. total (kg-CO2e/MWh)'][idx + 1] / 1000
            scope2_grid_emissions[idx] = energy_from_grid[idx]  * cambium_data['LRMER CO2 equiv. combustion (kg-CO2e/MWh)'][idx + 1] / 1000
            scope3_grid_emissions[idx] = energy_from_grid[idx]  * cambium_data['LRMER CO2 equiv. production (kg-CO2e/MWh)'][idx + 1] / 1000
    
    ### Sum total emissions
    scope2_grid_emissions_sum = sum(scope2_grid_emissions)*system_life # total emissions over plant lifespan (kg-CO2e)
    scope3_grid_emissions_sum = sum(scope3_grid_emissions)*system_life # kg_to_MT_conv -- got rid of this for these two, why would you do that?
    # scope3_ren_sum            = energy_from_renewables_df['Energy from renewables (kWh)'].sum()*system_life # kWh

    ### Fuel emissions
    conversion_factor = btu_to_j(1e3, 1) # extracts conversion factor for below conversion
    ef = {
        ###\ source: https://www.sciencedirect.com/science/article/pii/S0959652622014445
        # ef = emission factor (g/MMBtu --> kg/MJ; from the above source)
        'coal': 89920 / conversion_factor, 
        'natural gas': 59413 / conversion_factor, 
        'hydrogen': 0,
        'pet coke': 106976 / conversion_factor, 
        'waste': 145882 / conversion_factor, 
        'tire': 60876 / conversion_factor, 
        'solvent': 72298 / conversion_factor, 
        ###/

        ###\ source: https://backend.orbit.dtu.dk/ws/portalfiles/portal/161972551/808873_PhD_thesis_Morten_Nedergaard_Pedersen_fil_fra_trykkeri.pdf (table 3-2)
        # TODO look more into the specifics of these emission reportings
        # '''
        #     Carbon-neutral fuels, as defined by the European commission, are essentially biomass 
        #     which include agricultural and forestry biomass, biodegradable municipal waste, animal
        #     waste, paper waste [20] (Table 3). Certain authors argue that, in fact, burning these
        #     carbon-neutral waste can be even regarded as a GHG sink because they would 
        #     otherwise decay to form methane which is much a more powerful GHG than CO2[17], 
        #     [21]. Waste materials derived from fossil fuels such as solvent, plastics, used 
        #     tyres are not regarded as carbon-neutral. However, it is important to note that
        #     transferring waste fuels from incineration plants to cement kiln results in a 
        #     significant net CO2 reduction because cement kilns are more efficient. Another
        #     advantage is that no residues are generated since the ashes are completely 
        #     incorporated in clinker [21]
        # '''
        'SRF (wet)': 9,
        'MBM (wet)': 0,
        ###/

        ###\ https://www.sciencedirect.com/science/article/pii/S1540748910003342#:~:text=Glycerol%20has%20a%20very%20high,gasoline%2C%20respectively%20%5B5%5D.
        'glycerin':  0.073 * 1e3 / self.lhv['glycerin'], # g CO2/g glycerol --> g CO2/kg glycerol --> g CO2/MJ glycerol
        # NOTE this is an incredibly crude estimate -- want to find a better source that is more applicable to cement/concrete
        #   see section 3.1 for assumptions/measurement setup
        ###/
    }

    ### sum emissions from each fuel
    # uncomment print statements for debugging
    # print('\n------------- Calculating fuel emissions ---------')
    fuel_emissions = 0 # kgCO2
    for key in ef.keys():
        if key not in self.feed_consumption.keys() or not self.feed_consumption[key]:
            # print(f'{key} not found in feed_consumption.keys()')
            continue
        else:
            fuel_emissions += self.feed_consumption[key] * self.config['Cement Production Rate (annual)'] \
                * self.lhv[key] * system_life * ef[key] # kg feed/t cem -> kg CO2
    
    ###\ source: https://www.sciencedirect.com/science/article/pii/S0959652622014445
    calcination_emissions_rate = 553 # kg CO2/tonne cem, assuming cli/cement ratio of 0.95 
    ###/
    calcination_emissions = calcination_emissions_rate * self.config['Cement Production Rate (annual)'] * system_life

    ### Calculate LCA results
    cement_production = self.config['Cement Production Rate (annual)'] * system_life
    grid_electricity_EI = (scope2_grid_emissions_sum + scope3_grid_emissions_sum) / cement_production
    renewable_electricity_EI = 0 # TODO do this maybe
    fuel_EI = fuel_emissions / cement_production
    process_EI = calcination_emissions / cement_production
    total_cement_EI = grid_electricity_EI + renewable_electricity_EI + fuel_EI + process_EI

    # # Uncomment for debugging
    # print('---------- LCA RESULTS --------------')
    # print(f'Emissions from grid electricity (kg CO2e/ton cement): {grid_electricity_EI}\n',
    #       f'Indirect emissions from renewable electricity (kg CO2e/ton cement): {renewable_electricity_EI}\n',
    #       f'Emissions from fuel (kg CO2e/ton cement): {fuel_EI}\n',
    #       f'Process emissions (kg CO2e/ton cement): {process_EI}\n',
    #       f'Total cement emissions (kg CO2e/ton cement): {total_cement_EI}\n')

    # print('---------- LCA RESULTS with carbon capture-----------')
    # print(f'Emissions from grid electricity (kg CO2e/ton cement): {grid_electricity_EI}\n',
    #       f'Indirect emissions from renewable electricity (kg CO2e/ton cement): {renewable_electricity_EI}\n',
    #       f'Emissions from fuel (kg CO2e/ton cement): {fuel_EI * (1 - self.config["Carbon capture efficency (%)"])}\n',
    #       f'Process emissions (kg CO2e/ton cement): {process_EI * (1 - self.config["Carbon capture efficency (%)"])}\n',
    #       f'Total cement emissions (kg CO2e/ton cement): {grid_electricity_EI + renewable_electricity_EI + fuel_EI * (1 - self.config["Carbon capture efficency (%)"]) + process_EI * (1 - self.config["Carbon capture efficency (%)"])}\n')
    
    lca_results = {
        'Emissions from grid electricity (kg CO2e/ton cement)': grid_electricity_EI,
        'Indirect emissions from renewable electricity (kg CO2e/ton cement)': renewable_electricity_EI,
        'Emissions from fuel (kg CO2e/ton cement)': fuel_EI,
        'Process emissions (kg CO2e/ton cement)': process_EI,
        'Total cement emissions (kg CO2e/ton cement)': total_cement_EI
    }

    lca_results_ccus = {
        'Emissions from grid electricity (kg CO2e/ton cement)': grid_electricity_EI,
        'Indirect emissions from renewable electricity (kg CO2e/ton cement)': renewable_electricity_EI,
        'Emissions from fuel (kg CO2e/ton cement)': fuel_EI * (1 - self.config["Carbon capture efficency (%)"]),
        'Process emissions (kg CO2e/ton cement)': process_EI * (1 - self.config["Carbon capture efficency (%)"]),
        'Total cement emissions (kg CO2e/ton cement)': grid_electricity_EI + renewable_electricity_EI \
                                                        + fuel_EI * (1 - self.config["Carbon capture efficency (%)"]) \
                                                        + process_EI * (1 - self.config["Carbon capture efficency (%)"])
    }
    
    return lca_results, lca_results_ccus
    
    # TODO quantify the impact of quarrying, raw materials, etc on emissions?
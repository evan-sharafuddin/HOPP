
"""
Created on Wed June 14 2:28 2023

@author: evan-sharafuddin
"""

# Abbreviations
# LHV - lower heat value 
# ng - natural gas
# clk - clinker
# tdc - total direct costs (see paper)
# epc - engineering process construction ?

# TODO
# does 't' mean short ton, tonne, etc?

class ConcretePlant:
    """  
    Modular class to allow for multiple varieties of cement/concrete production
    and their respective techno-economic analises
        
    """
    
    def __init__(self):
        pass

    def clinker_tea():
        """
        Performs a techno-economic analysis on a BAT clinker plant

        Adapted from this spreadsheet: https://zenodo.org/record/1475804
        Accompanying paper: https://www.sintef.no/globalassets/project/cemcap/2018-11-14-deliverables/d4.6-cemcap-comparative-techno-economic-analysis-of-co2-capture-in-cement-plants.pdf

        """

        # ---------------------------------- Flags and User Settings ----------------------------------
        ccs = True # carbon capture enabled, monoethanolamine (MEA) reference technology (see paper)


        # ---------------------------------- Utilities and Consumables ----------------------------------
        # NOTE: this will probably be substituted with values from HOPP (at least for electricity)
        
        ## costs
        raw_meal = 3.012 # €/ton raw meal
        fuel = 3 # €/GJ LHV
        electricity = 58.1 # €/MWH_e 
        steam = 25.3 # €/MWH_th (from ng boiler)
        cooling_water = 0.39 # €/m^3
        ammonia = 0.13 # €/ton NH3 

        ## above values normalized by ton of clinker produced
        if ccs:
            raw_meal_clk = 1.66 # ton raw meal/ton clk
            fuel_clk = 10 # GJ LHV fuel/ton clk
            electricity_clk = 0.01 # MWH_e/ton clk
            steam_clk = 0 # MWH_th/ton clk
            cooling_water_clk = 10 # m^3 cooling water/ton clk
            ammonia_clk = 5 # kg_NH3/ton clk
        else:
            raw_meal_clk = 1.66 # ton raw meal/ton clk
            fuel_clk = 3.135 # GJ LHV fuel/ton clk
            electricity_clk = 0.1319 # MWH_e/ton clk
            steam_clk = 0 # MWH_th/ton clk
            cooling_water_clk = 0 # m^3 cooling water/ton clk
            ammonia_clk = 5 # kg_NH3/ton clk

        ## climate impacts (carbon emissions)
        raw_meal_co2 = 0 # kg CO2/ton raw meal ### actually?? what about quarrying emissions?
        # NOTE: excluding fuel on purpose
        electricity_co2 = 262 # kg CO2/MWH_e
        steam_co2 = 224 # kg CO2/MWH_th
        cooling_water_co2 = 0 # kg CO2/m^3
        ammonia_co2 = 0 # kg CO2/kg NH3

        # ---------------------------------- Plant Info ----------------------------------
        # NOTE: current data are the rated capacities for this reference plant
        
        ## clinker production
        clinker_production = 2895.5 # ton/day
        cement_clinker_ratio = 1.36 # NOTE: usually designated as clinker/cement ratio
        cement_production = clinker_production * cement_clinker_ratio

        ## CO2 emissions
        co2_stack = 28.3 # kg/s
        co2_stack_per_ton = co2_stack * 3600 * 24 / clinker_production # kg/ton clinker
        co2_elec = 1.2 # kg/s
        co2_elec_per_ton = electricity_clk * electricity_co2 # kg/ton clinker
        co2_steam_per_ton = steam_clk * steam_co2 # kg/ton clk
        co2_steam = co2_steam_per_ton * clinker_production / 3600 / 24 # kg/s INCONSISTENT W SS
        co2_other_per_ton = cooling_water_clk * cooling_water_co2 + \
                            ammonia_clk * ammonia_co2 # kg/ton clk
        co2_other = co2_other_per_ton * clinker_production / 24 / 3600 # kg/s INCONSISTENT W SS

        # ---------------------------------- CAPEX ----------------------------------
        total_direct_cost = 149.82 # M€
        indirect_costs = 0.14 # % TDC
        epc = total_direct_cost * (1 + indirect_costs) # M€
        owner_costs = 0.07 # % TDC
        project_contingency = 0.15 # % TDC
        owner_cost_conting = total_direct_cost * (owner_costs + project_contingency) # M€
        total_plant_cost = epc + owner_cost_conting # M€ (kiln only!)

        # calculate capex for CSS infrastructure
        if ccs: 
            total_direct_cost = 180 # M€
            indirect_costs = 0.14 # % TDC
            epc = total_direct_cost * (1 + indirect_costs) # M€
            owner_costs = 0.07 # % TDC
            project_contingency = 0.15 # % TDC
            owner_cost_conting = total_direct_cost * (owner_costs + project_contingency) # M€
            total_plant_cost = epc + owner_cost_conting + total_plant_cost # M€ (kiln and capture system)
        


    def portland_tea(): # OPC-TEA
        pass
        
        
    def run_profast_for_concrete():
        pass



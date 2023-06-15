
"""
Created on Wed June 14 2:28 2023

@author: evan-sharafuddin
"""

import ProFAST

# Abbreviations
# LHV - lower heat value 
# ng - natural gas
# clk - clinker
# tdc - total direct costs (see paper)
# epc - engineering process construction ?
# om - O&M

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
            total_plant_cost = epc + owner_cost_conting + total_plant_cost # M€ (kiln and capture system, if CSS enabled)
        
        # ---------------------------------- OPEX ----------------------------------
        ## carbon tax
        ### in spreadsheet, skipping for now ###

        total_consumables = raw_meal * raw_meal_clk + \
                            fuel * fuel_clk + \
                            electricity * electricity_clk + \
                            steam * steam_clk + \
                            cooling_water * cooling_water_clk + \
                            ammonia * ammonia_clk # €/ton clk
        
        other_var_om = 0.8 # €/ton cement
        other_var_om = 0.8 * cement_clinker_ratio # €/ton clk

        insurance_local_tax_rate = 0.02 # % TPC
        insurance_local_tax = total_plant_cost * insurance_local_tax_rate # M€/year

        maintenance_cost_rate = 0.02 # % TPC
        maintenance = maintenance_cost_rate * total_plant_cost # M€/year
        ## labor
        if ccs:
            num_persons = 120
        else:
            num_persons = 100

        labor_per_person = 60 # k€/year/person
        operating_labor = labor_per_person * num_persons * 1e3 / 1e6 # M€/year
        
        
        maintenance_labor_rate = 0.4 # % of maintenance cost
        maintenance_labor = maintenance_labor_rate * maintenance # M€/year

        admin_support__rate = 0.3 # % oper. and maintenance labor cost
        admin_support = admin_support__rate * (operating_labor * maintenance_labor) # M€/year

        labor_cost = operating_labor + admin_support # M€/year

        # ---------------------------------- ProFAST ----------------------------------
        pf = ProFAST.ProFAST('blank')
        gen_inflation = 0.00
        pf.set_params('commodity',{"name":'Clinker',"unit":"ton","initial price":1000,"escalation":gen_inflation})
        pf.set_params('capacity',plant_capacity_mtpy/365) #units/day
        pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
        pf.set_params('analysis start year',2022)
        pf.set_params('operating life',plant_life)
        pf.set_params('installation months',20)
        pf.set_params('installation cost',{"value":installation_cost,"depr type":"Straight line","depr period":4,"depreciable":False})
        pf.set_params('non depr assets',land_cost)
        pf.set_params('end of proj sale non depr assets',land_cost*(1+gen_inflation)**plant_life)
        pf.set_params('demand rampup',5.3)
        pf.set_params('long term utilization',plant_capacity_factor)
        pf.set_params('credit card fees',0)
        pf.set_params('sales tax',0) 
        pf.set_params('license and permit',{'value':00,'escalation':gen_inflation})
        pf.set_params('rent',{'value':0,'escalation':gen_inflation})
        pf.set_params('property tax and insurance percent',0)
        pf.set_params('admin expense percent',0)
        pf.set_params('total income tax rate',0.27)
        pf.set_params('capital gains tax rate',0.15)
        pf.set_params('sell undepreciated cap',True)
        pf.set_params('tax losses monetized',True)
        pf.set_params('operating incentives taxable',True)
        pf.set_params('general inflation rate',gen_inflation)
        pf.set_params('leverage after tax nominal discount rate',0.0824)
        pf.set_params('debt equity ratio of initial financing',1.38)
        pf.set_params('debt type','Revolving debt')
        pf.set_params('debt interest rate',0.0489)
        pf.set_params('cash onhand percent',1)

        



    def portland_tea(): # OPC-TEA
        pass
        
        
    def run_profast_for_concrete():
        pass

    # ---------------------------------- Misc. Functions ----------------------------------
    def call_profast
    
    def euro_to_usd(cost_EUR):
        ''' 
        Converts monetary values from EUR to USD

        NOTE: conversion factor is the average from 2014, which was the cost basis
        year given in the spreadsheet
        
        '''
        conversion_factor = 1.3283 # USD/EUR
        return conversion_factor * cost_EUR




"""
Created on Wed June 14 2:28 2023

@author: evan-sharafuddin
"""

import ProFAST
import pandas as pd
from pathlib import Path
import os

# Abbreviations
# LHV - lower heat value 
# ng - natural gas
# cli - clinker
# cem - cement
# tdc - total direct costs (see paper)
# epc - Engineering, process, and construction costs (total direct costs + indirect costs)
# om - O&M
# BAT - best available technology

# TODO
# convert variables to dictionaries? Would be easier to convert hard code to user input
# mark all locations that need to account for scalable plant capacity
#   do we want to scale plant based on clinker or cement production? Assuming cement.
# TRY TO MAKE THE LCOC SOMEWHAT SIMILAR TO THAT IN THE PAPER
#   off by about 20...

# Important Assumptions
# * "It is worth noting that the development and land costs are not considered in the project estimates."
# * TPC calculations exclude "land property (in particula rthe quaqrry), emerging emission abatement technology 
# (e.g. SCR) and developing cost (power and water supply)"
# * Production Costs: "excl. freight, raw material deposit, land property, permits etc. The rang eof production costs
# is based on different utilization rates from 70 to 90 %"


class ConcretePlant:
    """  
    Class for green concrete analysis

    NOTE only considering a cemenet plant at the moment but this might change
        
    """

    def __init__(self, css_ca_looping=False, css_oxyfuel=False, natural_gas_pure=False, natural_gas_H2_blend=False, \
                 renewable_electricity=False, SCMs=False, atb_year=2035, site_location='IA', cli_production=1e6, \
                 cli_cem_ratio=73.7e-2, plant_life=25, plant_capacity_factor = 91.3e-2):
                 # source of plant_capacity_factor: CEMCAP
        
        if css_ca_looping and css_oxyfuel or natural_gas_pure and natural_gas_H2_blend:
            raise Exception("Invalid configuration -- make sure only one option is true for CSS and/or natural gas")
        
        self.configurations = {
            'CSS (Ca looping)': css_ca_looping,
            'CSS (oxyfuel combustion)': css_oxyfuel,
            'Natural gas, pure': natural_gas_pure,
            'Natural gas, hydrogen blend': natural_gas_H2_blend,
            'Renewable electricity': renewable_electricity,
            'Using SCMs': False,
            'ATB year': atb_year,
            'site location': site_location,
            'Clinker Production Rate (annual)': cli_production,
            'Clinker-to-cement ratio': cli_cem_ratio,
            'Plant lifespan': plant_life,
            'Plant capacity factor': plant_capacity_factor,
        }
        
        self.configurations['Cement Production Rate (annual)'] = self.configurations['Clinker Production Rate (annual)'] / self.configurations['Clinker-to-cement ratio']

        # NOTE input clinker production, not cement production, as a configuration!

        
        
    
    def eur_to_usd(self, multiplyer, *costs):
        ''' 
        Converts monetary values from EUR to USD

        multiplyer argument allows you to account for prefix (ex: M, k)

        NOTE: conversion factor is the average from 2014, which was the cost basis
        year given in the paper

        source: https://www.exchangerates.org.uk/EUR-USD-spot-exchange-rates-history-2013.html
    
        '''
        conversion_factor = 1.3284 # USD/EUR
        vals = []
        for cost in costs:
            vals.append(cost * conversion_factor * multiplyer)
        
        if len(vals) == 1:
            return vals[0]
        return vals

    def btu_to_j(self, multiplyer, *vals):
        '''
        Converts energy values from BTU to J

        multiplyer argment allows you to account for prefix (ex: M, k)

        '''

        vals_j = []
        for val in vals:
            vals_j.append(val * 1055.6 * multiplyer)

        if len(vals_j) == 1:
            return vals_j[0]
        return vals_j
            
    ### TODO decarbonization pathways
        # CCS 
        #   calcium looping
        #   oxyfuel combustion
        # substituting coal with natural gas
        #   pure natural gas
        #   hydrogen fuel mix
        # energy efficency measures in kiln, etc (this might already be considered with the precalciner/preheater tech)
        # renewable electricity (link HOPP)

    def run_profast_for_cement(self):
        """
        Performs a techno-economic analysis on a BAT cement plant

        NOTE focusing on just cement for now
        
        Source unless otherwise specified: IEAGHG REPORT (https://ieaghg.org/publications/technical-reports/reports-list/9-technical-reports/1016-2013-19-deployment-of-ccs-in-the-cement-industry)
        Other Sources:
            * CEMCAP Spreadsheet (https://zenodo.org/record/1475804)
            * CEMCAP Report (https://www.sintef.no/globalassets/project/cemcap/2018-11-14-deliverables/d4.6-cemcap-comparative-techno-economic-analysis-of-co2-capture-in-cement-plants.pdf)
            * Fuel LHV values (https://courses.engr.illinois.edu/npre470/sp2018/web/Lower_and_Higher_Heating_Values_of_Gas_Liquid_and_Solid_Fuels.pdf)
            * Emission Factors for fuel (https://www.sciencedirect.com/science/article/pii/S0959652622014445)
            * Emission factors for electricity (https://emissionsindex.org/)
        """

        # TODO pass in as configurations
        configurations = {
            'CSS (Ca looping)': False,
            'CSS (oxyfuel combustion)': False,
            'Natural gas, pure': False,
            'Natural gas, hydrogen blend': False,
            'Renewable electricity': False,
            'ATB year': 2035,
            'site location': 'IA',
        }
        

        # ---------------------------- Profast Parameters -----------------------
        ## Plant specs
        plant_cfg = self.configurations
        
        
        # { #hard coded for now

        
        # 'CSS (Ca looping)': css_ca_looping,
        # 'CSS (oxyfuel combustion)': css_oxyfuel,
        # 'Natural gas, pure': natural_gas_pure,
        # 'Natural gas, hydrogen blend': natural_gas_H2_blend,
        # 'Renewable electricity': renewable_electricity,
        # 'Using SCMs': False,
        # 'ATB year': atb_year,
        # 'site location': site_location,
        # 'Clinker Production Rate (annual)': cli_production,
        # 'Clinker-to-cement ratio': cli_cem_ratio,
        # 'Plant lifespan': plant_life,
        # 'Plant capacity factor': plant_capacity_factor,
        # }
        # plant_cfg['Cement Production Rate (annual)'] = plant_cfg['Clinker Production Rate (annual)'] / plant_cfg['Clinker-to-cement ratio']

        raw_meal_cli_factor = 1.6 # loss of raw meal during production of clinker... can remove this if know feedstock data for the indiv. 
                                  # components in the raw meal

        ### TODO verify the reliability of these numbers, lots of different ones coming up in the IEAGHG article
        thermal_energy = 3400e-3 # MJ/kg cli -- might want to fact check this (2010, worldwide, preclaciner/preheater dry kiln)
        electrical_energy = 108 # kWh/t cement (2010, worldwide)
        ###

        ## Economic specs
        contingencies_fees = 1e-2 # fraction of installed costs (CAPEX)
        taxation_insurance = 1e-2 # fraction of installed costs, per year (OPEX)

    
        # ------------------------------ CAPEX ------------------------------
        # section 5.1
        # NOTE all values in M€
        # NOTE currently this does not include land property (in particular the quarry), 
        # emerging emission abatement technology, developing cost (power & water supply)

        ### Plant Equipment
        ## quarry 
        # TODO
        ## raw material crushing and prep
        crushing_plant = 3.5
        storage_conveying_raw_material = 3.5
        grinding_plant_raw_meal = 16.8
        storage_conveyor_silo = 2.1
        ## pyroprocessing
        kiln_plant = 11.9
        grinding_plant_cli = 9.8
        ## cem production
        silo = 9.8 
        packaging_conveyor_loading_storing = 6.3
        ## coal grinding 
        coal_mill_silo = 6.3

        equip_costs = crushing_plant + storage_conveying_raw_material + grinding_plant_raw_meal + \
                    + storage_conveyor_silo + kiln_plant + grinding_plant_cli + \
                    silo + packaging_conveyor_loading_storing + coal_mill_silo

        ### installation
        civil_steel_erection_other = 75.5 
        installed_costs = equip_costs + civil_steel_erection_other
        epc_costs = 10 
        contigency_fees = installed_costs * contingencies_fees
        tpc = installed_costs + epc_costs + contigency_fees
        # NOTE according to spreadsheet, tpc = 203.75
        owners_costs = 11.9
        other = 8.0 # working capital, start-ups, spare parts
        interest_during_construction = 6.4
        land_cost = 0 # TODO
        developing_cost = 0 # TODO
        total_capex = tpc + owners_costs + other + interest_during_construction

        # ////////// unit conversions ////////////// M€ --> $
        crushing_plant, storage_conveying_raw_material, grinding_plant_raw_meal, storage_conveying_raw_material, kiln_plant, \
        grinding_plant_cli, silo, packaging_conveyor_loading_storing, coal_mill_silo, equip_costs, \
        civil_steel_erection_other, installed_costs, epc_costs, contigency_fees, tpc, owners_costs, other, \
        interest_during_construction, land_cost, developing_cost, total_capex = \
        self.eur_to_usd(1e6,
            crushing_plant, storage_conveying_raw_material, grinding_plant_raw_meal, storage_conveying_raw_material, kiln_plant, \
        grinding_plant_cli, silo, packaging_conveyor_loading_storing, coal_mill_silo, equip_costs, \
        civil_steel_erection_other, installed_costs, epc_costs, contigency_fees, tpc, owners_costs, other, \
        interest_during_construction, land_cost, developing_cost, total_capex) # 
        
        

        # ------------------------------ OPEX ------------------------------ 
      
        # ///////////// FEEDSTOCKS /////////////
        lhv = {
            #/ Source: Fuel LHV values
            'coal': 26.122, # MJ/kg, ASSUMING "bituminous coal (wet basis)"
            'natural gas': 47.141, # MJ/kg 
            'hydrogen': 120.21, # MJ/kg
            'pet coke': 29.505, # MJ/kg 
            #/

            # "european alternative fuel input" -- IEAGHG
            'animal meal': 18, # MJ/kg
            'sewage sludge': 4, # MJ/kg
            'pretreated domestic wastes': 16, # MJ/kg
            'pretreated industrial wastes': (18 + 23) / 2, # MJ/kg (given as range)
            'tires': 28, # MJ/kg
            'solvents': (23 + 29) / 2, # MJ/kg (given as range)
        }

        # can change this by altering the compositions of each fuel below, or by introducing new alternative fuels
        alt_fuel_lhv = 0.194 * lhv['tires'] + 0.117 * lhv['solvents'] + 0.12 * lhv['pretreated domestic wastes'] \
        + 0.569 * lhv['pretreated industrial wastes'] # multiplying by each fuel's composition, MJ/kg 
        
        lhv['alt fuel'] = alt_fuel_lhv
        
        # fuel compositions (percent thermal input) -- must add up to 1
        frac = {
            'coal': 0.7,
            'natural gas': 0,
            'hydrogen': 0,
            'pet coke': 0,
            'alt fuel': 0.3,
        }
        if sum(frac.values()) != 1:
            raise Exception("Fuel composition fractions must add up to 1")
        
        feed_consumption = {
            'coal': thermal_energy * frac['coal'] / lhv['coal'], # kg coal/kg cli
            'alt fuel': thermal_energy * frac['alt fuel'] / lhv['alt fuel'],
            # TODO might want to search for better values (these are from IEAGHG)
        } 

        feed_cost = {
            # Fuels
            'coal': 3e-3 * lhv['coal'], # €/MJ (paper gave in GJ)
            'nat gas': 6e-3 * lhv['natural gas'], # €/MJ
            'alt fuel': 1 * lhv['alt fuel'], # €/ton cement
        
            # Raw materials
            # TODO replace with unit costs for each material, not sure if this is necissary though
            'raw meal': 5 * plant_cfg['Clinker-to-cement ratio'], # €/ton cement 
            'process water': 0.014, # €/ton cement
            'misc': 0.8, # €/ton cement
        }

        # Electricity
        
        if plant_cfg['ATB year'] == 2020:
            grid_year = 2025
        elif plant_cfg['ATB year'] == 2025:
            grid_year = 2030
        elif plant_cfg['ATB year'] == 2030:
            grid_year = 2035
        elif plant_cfg['ATB year'] == 2035:
            grid_year = 2040
            
        # Read in csv for grid prices
        grid_prices = pd.read_csv(os.path.join(os.path.split(__file__)[0], 'examples/H2_Analysis/annual_average_retail_prices.csv'),index_col = None,header = 0)
        elec_price = grid_prices.loc[grid_prices['Year']==grid_year,plant_cfg['site location']].tolist()[0] # $/MWh?
        elec_price *= 1e-3 # $/kWh

        # TODO pass in as configurations
        if configurations['Renewable electricity']:
            elec_price = 0
        
        feed_cost['electricity'] = elec_price

        # ////////////// waste ////////////////
        # TODO: cost of cement kiln dust disposal? could be included already in some of the other costs

        # ///////////// unit conversions //////////// € --> $ 

        for key, value in feed_cost.items():
            if key == 'electricity': # this has already been converted
                continue

            feed_cost[key] = self.eur_to_usd(1, value)
        
    
        # ------------ fixed -----------------
        ## fixed ($/ton cem)
        
        num_workers = 100
        cost_per_worker = 60 # k€/person
        operational_labor = self.eur_to_usd(1e3, num_workers * cost_per_worker) # $
        maintenance_equip = self.eur_to_usd(1, 5.09) # $
        ### CEMCAP SPREADSHEET
        maintenance_labor = 0.4 * maintenance_equip # $
        admin_support = 0.3 * (operational_labor + maintenance_labor) 
        # TODO: sort out what to do with these... not used in pf
        insurance = 0.8
        local_tax = 0.8
        # not used in pf
       
        
        # ----------------------------- Emissions/LCA --------------------------
        '''
        ## fuels
            specific emissions

        ## process
            calcination
            anything w/ resource extraction?

        ## electricty
            specific emissions

        ## raw materials and waste products?

        '''

        ### source: https://www.sciencedirect.com/science/article/pii/S0959652622014445
        # ef = emission factor
        pet_coke_ef, natural_gas_ef, coal_ef, waste_ef, tire_ef, solvent_ef = \
            self.btu_to_j(1e-6 * 1e3, 106976, 59413, 89920, 145882, 60876, 72298) # kg/J

        print(f'pet coke ef: {pet_coke_ef}')
            
        calcination_emissions = 553 # kg/tonne cem, assuming cli/cement ratio of 0.95 

        # NOTE ignorning other emissions (fuel for quarrying, etc)
        ###

        ### source: https://emissionsindex.org/
        electricity_ef = 355 # kg/kWh
        ###

        # TODO quantify the impact of quarrying, raw materials, etc on emissions

        # ------------------------- TODO Other Adjustable Parameters ---------------------------
        # fuel types and compositions
            # hydrogen mixing
            # oxy combustion

        # renewable electricity
        # carbon capture
        # SCMs (less clinker needed per unit cement)
            # slag from steel production

        # cement compositions 
            # need to do more research on strength of compositions, and if these 
            # are actually viable compositions

        '''
        POSSIBLE CONFIGURATIONS
        * standard plant (draw directly from a paper)
        * CCS (with oxycombustion?)
            * oxygen feedstock
            * different energy consumptions
            * different capital costs
        * energy efficency measures
            * different capital costs
            * different energy costs
        * renewably sourced electricity
            * electricity cost and no electrical emissions
        * hydrogen fuel mix
            * different capital costs
            * hydrogen feedstock
            * different energy consumptions
        '''


        # ------------------------- Fixed Parameters -------------------------------
        # strength of concrete (only choose known cement compositions that will achieve this strength)
        # preheater and precalciner (already implemented in a lot of plants)

        '''
        # additional considerations (confirm with people that know cement/concrete)
        * different compsotions and strength
        * different compositions and settling time
        NRMCA REPORT:
        * 28 day strength
        * water to cementitious maerials ratio
        * SCM reactivity
        * admixtures use ("air entraining admixture" for lower strength concrete exposed to freeze/thaw)
        * aggregate use (different for lightweight vs. heavy concretes)

        '''
        
        # ------------------------------ ProFAST ------------------------------
        # Set up ProFAST
        pf = ProFAST.ProFAST('blank')
        
        gen_inflation = 0.00
        pf.set_params('commodity',{"name":'Cement',"unit":"metric tonnes (t)","initial price":1000,"escalation":gen_inflation})
        pf.set_params('capacity',plant_cfg['Cement Production Rate (annual)'] / 365) #units/day
        pf.set_params('operating life',plant_cfg['Plant lifespan'])
        pf.set_params('installation cost',{"value": installed_costs,"depr type":"Straight line","depr period":4,"depreciable":False})
        pf.set_params('non depr assets', land_cost) 
        pf.set_params('long term utilization',plant_cfg['Plant capacity factor'])
        
        # TODO: not sure how these fit into the model given in the paper
        pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
        pf.set_params('installation months',36) # not sure about this one
        pf.set_params('analysis start year',2013) # is this ok? financials are based on 2013 conversion rates
        pf.set_params('credit card fees',0)
        pf.set_params('sales tax',0) 
        pf.set_params('rent',{'value':0,'escalation':gen_inflation})
        pf.set_params('property tax and insurance percent',0)

        # TODO: do not understand what these mean/don't know what to do with them
        pf.set_params('total income tax rate',0.27)
        pf.set_params('capital gains tax rate',0.15)
        pf.set_params('sell undepreciated cap',True)
        pf.set_params('tax losses monetized',True)
        pf.set_params('operating incentives taxable',True)
        pf.set_params('general inflation rate',gen_inflation)
        pf.set_params('leverage after tax nominal discount rate',0.00) # 0.0824
        pf.set_params('debt equity ratio of initial financing',0.00) # 1.38
        pf.set_params('debt type','Revolving debt')
        pf.set_params('debt interest rate',0.00) # 0.0489
        pf.set_params('cash onhand percent',1)
        pf.set_params('admin expense percent',0)
        pf.set_params('end of proj sale non depr assets',land_cost*(1+gen_inflation)**plant_cfg['Plant lifespan'])
        pf.set_params('demand rampup',0) # 5.3
        pf.set_params('license and permit',{'value':00,'escalation':gen_inflation})
        
        # ------------------------------ Add capital items to ProFAST ------------------------------
        # NOTE: these are all converted to USD
        # NOTE: did not change the last three arguments
        pf.add_capital_item(name="crushing plant",cost=crushing_plant,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='storage, conveying raw material',cost=storage_conveying_raw_material,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='grinding plant, raw meal',cost=grinding_plant_raw_meal,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='storage, conveyor, silo',cost=storage_conveyor_silo,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='kiln plant',cost=kiln_plant,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='grinding plant, clinker',cost=grinding_plant_cli,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='silo',cost=silo,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='packaging plant, conveyor, loading, storing',cost=packaging_conveyor_loading_storing,depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='mill, silo',cost=coal_mill_silo,depr_type="MACRS",depr_period=7,refurb=[0])
        
        # ------------------------------ Add fixed costs ------------------------------
        # NOTE: in the document these values were given in EUR/t cem, so I am just going to multiply
        # them by the annual production capacity of the plant (at plant capacity rate)
        # NOTE: operating labor cost includes maintenance labor cost, according to the paper
        pf.add_fixed_cost(name="Annual Operating Labor Cost",usage=1,unit='$/year',\
                          cost=operational_labor * plant_cfg['Cement Production Rate (annual)'] * plant_cfg['Plant capacity factor'],escalation=gen_inflation)
        pf.add_fixed_cost(name="Maintenance Labor Cost",usage=1,unit='$/year',\
                          cost=maintenance_labor * plant_cfg['Cement Production Rate (annual)'] * plant_cfg['Plant capacity factor'],escalation=gen_inflation)
        pf.add_fixed_cost(name="Administrative & Support Labor Cost",usage=1,unit='$/year',\
                          cost=admin_support * plant_cfg['Cement Production Rate (annual)'] * plant_cfg['Plant capacity factor'],escalation=gen_inflation)
        pf.add_fixed_cost(name="Property tax and insurance",usage=1,unit='$/year',\
                          cost=taxation_insurance * tpc,escalation=0.0) 
        

        # ------------------------------ Add feedstocks, note the various cost options ------------------------------
        # NOTE feedstocks without consumption data have a usage of 1 (i.e. already in the desired units)
        pf.add_feedstock(name='Maintenance Materials',usage=1.0,unit='Units per ton of cement',cost=maintenance_equip,escalation=gen_inflation)
        pf.add_feedstock(name='Raw materials',usage=1.0,unit='kg per ton cem',cost=feed_cost['raw meal'] * plant_cfg['Clinker-to-cement ratio'],escalation=gen_inflation)
        pf.add_feedstock(name='coal',usage=feed_consumption['coal'],unit='kg per ton cement',cost=feed_cost['coal'],escalation=gen_inflation)
        # TODO find cost per MJ for alternative fuel
        pf.add_feedstock(name='alternative fuel',usage=1,unit='units per ton cem',cost=feed_cost['alt fuel'],escalation=gen_inflation)
        pf.add_feedstock(name='electricity',usage=electrical_energy,unit='kWh per ton cem',cost=feed_cost['electricity'],escalation=gen_inflation)
        pf.add_feedstock(name='process water',usage=1,unit='units per ton cem',cost=feed_cost['process water'],escalation=gen_inflation)
        pf.add_feedstock(name='Misc.',usage=1,unit='units per ton cem',cost=feed_cost['misc'],escalation=gen_inflation)

        # ------------------------------ Solve for breakeven price ------------------------------
        solution = pf.solve_price()

        # ------------------------------ Organizing Return Values ------------------------------
        summary = pf.summary_vals
        
        price_breakdown = pf.get_cost_breakdown()
        
        # CAPEX
        price_breakdown_crushing_plant = price_breakdown.loc[price_breakdown['Name']=='crushing plant','NPV'].tolist()[0]
        price_breakdown_storage_convey_raw_material = price_breakdown.loc[price_breakdown['Name']=='storage, conveying raw material','NPV'].tolist()[0]  
        price_breakdown_grinding_plant_raw_meal = price_breakdown.loc[price_breakdown['Name']=='grinding plant, raw meal','NPV'].tolist()[0] 
        price_breakdown_storage_conveyor_silo = price_breakdown.loc[price_breakdown['Name']=='storage, conveyor, silo','NPV'].tolist()[0]     
        price_breakdown_kiln_plant = price_breakdown.loc[price_breakdown['Name']=='kiln plant','NPV'].tolist()[0] 
        price_breakdown_grinding_plant_cli = price_breakdown.loc[price_breakdown['Name']=='grinding plant, clinker','NPV'].tolist()[0] 
        price_breakdown_silo = price_breakdown.loc[price_breakdown['Name']=='silo','NPV'].tolist()[0] 
        price_breakdown_packaging_conveyor_loading = price_breakdown.loc[price_breakdown['Name']=='packaging plant, conveyor, loading, storing','NPV'].tolist()[0]  
        price_breakdown_mill_silo = price_breakdown.loc[price_breakdown['Name']=='mill, silo','NPV'].tolist()[0]
        price_breakdown_installation = price_breakdown.loc[price_breakdown['Name']=='Installation cost','NPV'].tolist()[0]
    
        # fixed OPEX
        price_breakdown_labor_cost_annual = price_breakdown.loc[price_breakdown['Name']=='Annual Operating Labor Cost','NPV'].tolist()[0]  
        price_breakdown_labor_cost_maintenance = price_breakdown.loc[price_breakdown['Name']=='Maintenance Labor Cost','NPV'].tolist()[0]  
        price_breakdown_labor_cost_admin_support = price_breakdown.loc[price_breakdown['Name']=='Administrative & Support Labor Cost','NPV'].tolist()[0] 
        price_breakdown_proptax_ins = price_breakdown.loc[price_breakdown['Name']=='Property tax and insurance','NPV'].tolist()[0]
        
        # variable OPEX
        price_breakdown_maintenance_materials = price_breakdown.loc[price_breakdown['Name']=='Maintenance Materials','NPV'].tolist()[0]  
        price_breakdown_water = price_breakdown.loc[price_breakdown['Name']=='process water','NPV'].tolist()[0] 
        price_breakdown_raw_materials = price_breakdown.loc[price_breakdown['Name']=='Raw materials','NPV'].tolist()[0]
        price_breakdown_coal = price_breakdown.loc[price_breakdown['Name']=='coal','NPV'].tolist()[0]
        price_breakdown_alt_fuel = price_breakdown.loc[price_breakdown['Name']=='alternative fuel','NPV'].tolist()[0]
        price_breakdown_electricity = price_breakdown.loc[price_breakdown['Name']=='electricity','NPV'].tolist()[0]
        price_breakdown_misc = price_breakdown.loc[price_breakdown['Name']=='Misc.','NPV'].tolist()[0]
        price_breakdown_taxes = price_breakdown.loc[price_breakdown['Name']=='Income taxes payable','NPV'].tolist()[0]\
            - price_breakdown.loc[price_breakdown['Name'] == 'Monetized tax losses','NPV'].tolist()[0]\

        if gen_inflation > 0:
            price_breakdown_taxes = price_breakdown_taxes + price_breakdown.loc[price_breakdown['Name']=='Capital gains taxes payable','NPV'].tolist()[0]

        # TODO look into (331-342) further -- probably has something to do with the parameters I'm confused about
        # Calculate financial expense associated with equipment
        price_breakdown_financial_equipment = price_breakdown.loc[price_breakdown['Name']=='Repayment of debt','NPV'].tolist()[0]\
            + price_breakdown.loc[price_breakdown['Name']=='Interest expense','NPV'].tolist()[0]\
            + price_breakdown.loc[price_breakdown['Name']=='Dividends paid','NPV'].tolist()[0]\
            - price_breakdown.loc[price_breakdown['Name']=='Inflow of debt','NPV'].tolist()[0]\
            - price_breakdown.loc[price_breakdown['Name']=='Inflow of equity','NPV'].tolist()[0]    
            
        # Calculate remaining financial expenses
        price_breakdown_financial_remaining = price_breakdown.loc[price_breakdown['Name']=='Non-depreciable assets','NPV'].tolist()[0]\
            + price_breakdown.loc[price_breakdown['Name']=='Cash on hand reserve','NPV'].tolist()[0]\
            + price_breakdown.loc[price_breakdown['Name']=='Property tax and insurance','NPV'].tolist()[0]\
            - price_breakdown.loc[price_breakdown['Name']=='Sale of non-depreciable assets','NPV'].tolist()[0]\
            - price_breakdown.loc[price_breakdown['Name']=='Cash on hand recovery','NPV'].tolist()[0]
        
        # list containing all of the prices established above
        breakdown_prices = [price_breakdown_crushing_plant, 
                            price_breakdown_storage_convey_raw_material, 
                            price_breakdown_grinding_plant_raw_meal, 
                            price_breakdown_storage_conveyor_silo, 
                            price_breakdown_kiln_plant, 
                            price_breakdown_grinding_plant_cli, 
                            price_breakdown_silo, 
                            price_breakdown_packaging_conveyor_loading, 
                            price_breakdown_mill_silo, 
                            price_breakdown_installation, 
                            price_breakdown_labor_cost_annual, 
                            price_breakdown_labor_cost_maintenance, 
                            price_breakdown_labor_cost_admin_support, 
                            price_breakdown_proptax_ins, 
                            price_breakdown_maintenance_materials, 
                            price_breakdown_water, 
                            price_breakdown_raw_materials, 
                            price_breakdown_coal, 
                            price_breakdown_alt_fuel, 
                            price_breakdown_electricity, 
                            price_breakdown_misc, 
                            price_breakdown_taxes, 
                            price_breakdown_financial_equipment, 
                            price_breakdown_financial_remaining]
                    
        price_breakdown_check = sum(breakdown_prices)

       
        # a neater way to implement is add to price_breakdowns but I am not sure if ProFAST can handle negative costs
        # TODO above comment might not be an issue, so might not have had to pull out all these values
            
        bos_savings = 0 * (price_breakdown_labor_cost_admin_support) * 0.3 # TODO is this applicable for cement?

        breakdown_prices.append(price_breakdown_check)
        breakdown_prices.append(bos_savings) 

        breakdown_categories = ['Raw Material Crushing CAPEX',
                                'Storage, Conveying Raw Material CAPEX',
                                'Grinding Plant, Raw Meal CAPEX', 
                                'Storage, Conveyor, Silo CAPEX',
                                'Kiln Plant CAPEX',
                                'Grinding Plant, Clinker CAPEX',
                                'Silo CAPEX',
                                'Packaging Plant, Conveyor, Loading, Storing CAPEX',
                                'Mill, Silo CAPEX',
                                'Installation Cost',
                                'Annual Operating Labor Cost (including maintenance?)',
                                'Maintenance Labor Cost (zero at the moment?)',
                                'Administrative & Support Labor Cost',
                                'Property tax and insurance',
                                'Maintenance Materials',
                                'Process Water',
                                'Raw Materials',
                                'coal',
                                'Alternative Fuel',
                                'energy', 
                                'Misc. Variable OPEX',
                                'Taxes',
                                'Equipment Financing',
                                'Remaining Financial',
                                'Total',
                                'BOS Savings (?)']
        
        if len(breakdown_categories) != len(breakdown_prices):
            raise Exception("categories and prices lists have to be the same length")

        cement_price_breakdown = dict()
        for category, price in zip(breakdown_categories, breakdown_prices):
            cement_price_breakdown[f'cement price: {category} ($/ton)'] = price

        print(f"price breakdown (manual): {price_breakdown_check}")
        print(f"price breakdown (paper): {self.eur_to_usd(1, 50.9)}")
        print(f"price breakdown (CEMCAP spreadsheet, excluding carbon tax): {self.eur_to_usd(1, 46.02)}")
        print(f"percent error from CEMCAP: {(price_breakdown_check - self.eur_to_usd(1, 46.02))/self.eur_to_usd(1, 46.02) * 100}%")
        '''
        possible reasons for the discrepancy from CEMCAP
        '''
        # TODO what is the point of this line here?
        price_breakdown = price_breakdown.drop(columns=['index','Amount'])

        cem_production_actual = plant_cfg['Cement Production Rate (annual)'] * plant_cfg['Plant capacity factor']
        return(solution,summary,price_breakdown,cem_production_actual,cement_price_breakdown,total_capex)


if __name__ == '__main__':
    plant = ConcretePlant()
    (solution, summary, price_breakdown, cem_production_actual, cement_price_breakdown, total_capex) = \
    plant.run_profast_for_cement()

    path = Path('C:\\Users\\esharafu\\Documents\\cement_econ.csv')
    thing = pd.DataFrame(cement_price_breakdown,index=[0]).transpose()
    thing.to_csv(path)




### outline
'''
        ## Feedstocks
        # fuels
            specific cost
            unit consumption rates
        * coal
        * natural gas
        * pet coke
        * alternative fuels
            * tires
            * solvents
            * biofuels
            

        # raw materials
            specific cost
            unit consumption rates
        * limestone
        * clay
        * sand
        * iron ore

        # electricity
            specific cost
            unit consumption rates
        * grid
        * renewable
        * on site power plant?
            
        # waste
            specific cost
            unit production rates
        * CKD
            
        ## Fixed
'''

'''
        ## fuels
            specific emissions

        ## process
            calcination
            anything w/ resource extraction?

        ## electricty
            specific emissions

        ## raw materials and waste products?

'''


'''
        POSSIBLE CONFIGURATIONS
        * standard plant (draw directly from a paper)
        * CCS (with oxycombustion?)
            * oxygen feedstock
            * different energy consumptions
            * different capital costs
        * energy efficency measures
            * different capital costs
            * different energy costs
        * renewably sourced electricity
            * electricity cost and no electrical emissions
        * hydrogen fuel mix
            * different capital costs
            * hydrogen feedstock
            * different energy consumptions
        '''


        # ------------------------- Fixed Parameters -------------------------------
        # strength of concrete (only choose known cement compositions that will achieve this strength)
        # preheater and precalciner (already implemented in a lot of plants)

'''
        # additional considerations (confirm with people that know cement/concrete)
        * different compsotions and strength
        * different compositions and settling time
        NRMCA REPORT:
        * 28 day strength
        * water to cementitious maerials ratio
        * SCM reactivity
        * admixtures use ("air entraining admixture" for lower strength concrete exposed to freeze/thaw)
        * aggregate use (different for lightweight vs. heavy concretes)

'''
    

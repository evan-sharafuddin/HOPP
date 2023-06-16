
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
# epc - Engineering, process, and construction costs (total direct costs + indirect costs)
# om - O&M
# BAT - best available technology

# TODO
# convert variables to dictionaries? Would be easier to convert hard code to user input

# Important Assumptions
# "It is worth noting that the development and land costs are not considered in the project estimates."

class ConcretePlant:
    """  
    Class for green concrete analysis
        
    """
    
    def __init__(self):
        pass
    
    def eur_to_usd(self, cost_EUR, multiplyer):
        ''' 
        Converts monetary values from EUR to USD

        multiplyer argument allows you to account for prefix (ex: M, k)

        NOTE: conversion factor is the average from 2014, which was the cost basis
        year given in the paper

        source: https://www.exchangerates.org.uk/EUR-USD-spot-exchange-rates-history-2013.html
        
        '''
        conversion_factor = 1.3284 # USD/EUR
        return conversion_factor * cost_EUR * multiplyer


    def run_profast_for_cement(self):
        """
        Performs a techno-economic analysis on a BAT concrete plant
        
        Adapted from this paper: https://ieaghg.org/publications/technical-reports/reports-list/9-technical-reports/1016-2013-19-deployment-of-ccs-in-the-cement-industry

        """

        # ------------------------------ Reference Plant Specs ------------------------------
        # section 1.3
        # "BAT" plant, located in Europe

        clk_production = 1 # Mt/y
        clk_cem_ratio = 73.7e-2
        cem_production = clk_production / clk_cem_ratio # Mt/y
        raw_meal_clk_factor = 1.6 # what is this
        specific_fuel_consumption = 3280 # kJ/kg clk
        fuel_proportions = {
                            'Fossil fuel': 69.5e-2,
                            'Alternative fuel': 26e-2,
                            'biomass': 4.5e-2
        }

        specific_elec_demand = 97 # kWh/t cem, grinding of clinker and addition of other constituents
        specific_elec_demand_clk = 65 # kWh/t clk
        raw_material_moisture = 6e-2 # %

        co2_elec = (0.5 + 0.7) / 2 # t CO2/MWh
        spec_indirect_co2_elec = (0.049 + 0.068) / 2 # t CO2/ t cement
        spec_direct_co2_clk = 0.828 # t CO2/t clk
        spec_direct_co2_clk_no_biogenic = 0.804 # t co2/t clk
        total_spec_co2_with_elec = (0.66 + 0.68) / 2 # t co2/t cem

        # ------------------------------ Economic Specs ------------------------------
        # section 5.1

        plant_life = 25 # yr
        capacity_rate = 80e-2 # what is this?
        contingencies_fees = 10e-2 # fraction of installed costs
        taxation_insurance = 1e-2 # fraction of installed costs, per year


        # ------------------------------ CAPEX ------------------------------
        # section 5.1
        # (all values in M€)
        
        # NOTE: currently this does not include land property (in particular the quarry), 
        # emerging emission abatement technology, developing cost (power & water supply)
        
        ## raw materials
        crushing_plant = 3.5
        storage_conveying_raw_material = 3.5
        grinding_plant_raw_meal = 16.8
        storage_conveyor_silo = 2.1
        ## clk production
        kiln_plant = 11.9
        grinding_plant_clk = 9.8
        ## cem production
        silo = 9.8 
        packaging_conveyor_loading_storing = 6.3
        ## coal grinding 
        coal_mill_silo = 6.3
        equip_costs = crushing_plant + storage_conveying_raw_material + grinding_plant_raw_meal + \
                    + storage_conveyor_silo + kiln_plant + grinding_plant_clk + \
                    silo + packaging_conveyor_loading_storing + coal_mill_silo
        
        civil_steel_erection_other = 75.5 
        installed_costs = equip_costs + civil_steel_erection_other
        epc_costs = 10 
        contigency_fees = 14.5
        tpc = 170
        owners_costs = 11.9
        other = 8.0 # working capital, start-ups, spare parts
        interest_during_construction = 6.4
        land_cost = 0 # model does not consider cost of land 
        total_capex = tpc + owners_costs + other + interest_during_construction

        # ------------------------------ OPEX ------------------------------ 
        # section 5.1.2

        ## variable 
        raw_materials = 3.7 # €/ton cememt
        fossil_fuel = 35.2 # €/ton cement
        alt_fuel = 1 # €/ton cement 
        power_kiln_plant_grinding = 8.8 # €/ton cement
        process_water = 0.014 # €/ton cement
        misc = 0.8 # €/ton cement
        total_var_opex = raw_materials + fossil_fuel + alt_fuel + power_kiln_plant_grinding + process_water + misc # €/ton cement

        ## fixed (€/ton cem)
        maintenance = 5.0
        operational_labor = 5.5 # NOTE: confused about what document means by "maintenance". Cost of maintenance materials, 
        # maintenance labor, or both? Either way the given value for admin support doesn't really add up
        admin_support = 2.3 # (supposedly 30% of operational and maintenance labor)
        insurance = 0.8
        local_tax = 0.8
        total_fixed_opex = maintenance + operational_labor + admin_support + insurance + local_tax

        capital_charges = 17
        production_costs = 50.9 # see page 71, assuming utilization rate of 80%?
        
        # ------------------------------ ProFAST ------------------------------
        # Set up ProFAST
        pf = ProFAST.ProFAST('blank')
        
        # Fill these in - can have most of them as 0 also
        gen_inflation = 0.00
        pf.set_params('commodity',{"name":'concrete',"unit":"metric tonnes (t)","initial price":1000,"escalation":gen_inflation})
        pf.set_params('capacity',cem_production * 1e6 / 365) #units/day
        pf.set_params('operating life',plant_life)
        pf.set_params('installation cost',{"value":installed_costs,"depr type":"Straight line","depr period":4,"depreciable":False})
        pf.set_params('non depr assets',land_cost)
        pf.set_params('long term utilization',capacity_rate)
        
        # did not do anything to these
        pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
        pf.set_params('end of proj sale non depr assets',land_cost*(1+gen_inflation)**plant_life)
        pf.set_params('demand rampup',5.3)
        pf.set_params('installation months',20) # not sure about this one
        pf.set_params('analysis start year',2022)
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

        # ------------------------------ Add capital items to ProFAST ------------------------------
        # NOTE: these are all converted to USD
        # NOTE: did not change the last three arguments
        pf.add_capital_item(name="crushing plant",cost=self.eur_to_usd(crushing_plant, 1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='storage, conveying raw material',cost=self.eur_to_usd(storage_conveying_raw_material, 1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='grinding plant, raw meal',cost=self.eur_to_usd(grinding_plant_raw_meal,1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='storage, conveyor, silo',cost=self.eur_to_usd(storage_conveyor_silo,1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='kiln plant',cost=self.eur_to_usd(kiln_plant,1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='grinding plant, clinker',cost=self.eur_to_usd(grinding_plant_clk,1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='silo',cost=self.eur_to_usd(silo,1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='packaging plant, conveyor, loading, storing',cost=self.eur_to_usd(packaging_conveyor_loading_storing,1e6),\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        pf.add_capital_item(name='mill, silo',cost=coal_mill_silo,\
                            depr_type="MACRS",depr_period=7,refurb=[0])
        
        # ------------------------------ Add fixed costs ------------------------------
        # NOTE: in the document these values were given in EUR/t cem, so I am just going to multiply
        # them by the annual production capacity of the plant (at plant capacity rate)
        pf.add_fixed_cost(name="Annual Operating Labor Cost",usage=1,unit='$/year',\
                          cost=self.eur_to_usd(operational_labor * cem_production * capacity_rate,1),escalation=gen_inflation)
        # making below be zero, assuming "maintenance" refers to "maintenance materials"
        pf.add_fixed_cost(name="Maintenance Labor Cost",usage=1,unit='$/year',\
                          cost=0*self.eur_to_usd(maintenance * cem_production * capacity_rate,1),escalation=gen_inflation)
        pf.add_fixed_cost(name="Administrative & Support Labor Cost",usage=1,unit='$/year',\
                          cost=self.eur_to_usd(admin_support * cem_production * capacity_rate,1),escalation=gen_inflation)
        pf.add_fixed_cost(name="Property tax and insurance",usage=1,unit='$/year',\
                          cost=self.eur_to_usd(taxation_insurance * tpc,1),escalation=0.0) 
        

        # ------------------------------ Add feedstocks, note the various cost options ------------------------------
        # NOTE: do not have consumption data, so just setting usage = 1 for now
        pf.add_feedstock(name='Maintenance Materials',usage=1.0,unit='Units per ton of cement',cost=maintenance,escalation=gen_inflation)
        pf.add_feedstock(name='Raw materials',usage=1.0,unit='unit per ton cem',cost=raw_materials,escalation=gen_inflation)
        pf.add_feedstock(name='fossil fuel',usage=1,unit='unit per ton cement',cost=35.2,escalation=gen_inflation)
        pf.add_feedstock(name='alternative fuel',usage=1,unit='unit per ton cem',cost=alt_fuel,escalation=gen_inflation)
        pf.add_feedstock(name='power, kiln plant + grinding',usage=1,unit='unit per ton cem',cost=power_kiln_plant_grinding,escalation=gen_inflation)
        pf.add_feedstock(name='process water',usage=1,unit='unit per ton cem',cost=process_water,escalation=gen_inflation)
        pf.add_feedstock(name='Misc.',usage=1,unit='unit per ton cem',cost=misc,escalation=gen_inflation)

       # TODO: any coproducts to add?

        # ------------------------------ Solve for breakeven price ------------------------------
        solution = pf.solve_price()
        summary = pf.summary_vals

        # TODO: organize values like done at bottom of run_profast_for_steel.py

        return(solution, summary)


if __name__ == '__main__':
    plant = ConcretePlant()
    (a,b) = plant.run_profast_for_cement()




    
    def clinker_tea(): # using spreadsheet, ignore this (incomplete)
        pass

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

        ## Other
        capacity_factor = 91.3
        operational_life = 25 # yrs
        construction_time = 3 # yrs

        ## not sure what these are/if they are used for anything, 
        # but they were in the spreadsheet so I'm including them anyway
        # percentage_of_TPC_depreciation = 1 
        # Inflation_rate=0e-2
        # Construction_inflat=0e-2
        # Percentage_of_Debt_Capital=50e-2
        # Percentage_of_Equity_capital=50.0e-2
        # Interest_on_debt=8.00e-2
        # Interest_on_equity=8.00e-2
        # Discounted_cash_flow_rate=8.00e-2
        # DCF_and_inflation=8.00e-2
        # depreciation_time = 0 # yrs
        # tax_rate = 0 

        

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

        # ---------------------------------- ProFAST Parameters ----------------------------------
        pf = ProFAST.ProFAST('blank')

        # NOTE: substituted variable values but none of the economic parameters because
        # I did not know what a lot of them meant
        gen_inflation = 0.00
        pf.set_params('commodity',{"name":'Clinker',"unit":"ton","initial price":1000,"escalation":gen_inflation})
        pf.set_params('capacity',clinker_production) #units/day
        pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
        pf.set_params('analysis start year',2022) # does this depend on atb_year? Or is it dependent on the spreadsheet?
        pf.set_params('operating life',operational_life)
        pf.set_params('installation months',construction_time * 3)
        pf.set_params('installation cost',{"value":total_plant_cost,"depr type":"Straight line","depr period":4,"depreciable":False}) # equipment AND installation costs, is that ok here?
        pf.set_params('non depr assets',0) # originally land costs
        pf.set_params('end of proj sale non depr assets',0) # originally: land_cost*(1+gen_inflation)**plant_life
        pf.set_params('demand rampup',5.3) # ??
        pf.set_params('long term utilization',capacity_factor)
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


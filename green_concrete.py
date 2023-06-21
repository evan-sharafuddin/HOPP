
"""
Created on Wed June 14 2:28 2023

@author: evan-sharafuddin
"""

import ProFAST
import pandas as pd
from pathlib import Path

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
        Performs a techno-economic analysis on a BAT cement plant

        NOTE: focusing on just cement for now
        
        Adapted from this paper: https://ieaghg.org/publications/technical-reports/reports-list/9-technical-reports/1016-2013-19-deployment-of-ccs-in-the-cement-industry

        """

        # ------------------------------ Reference Plant Specs ------------------------------
        # section 1.3
        # "BAT" plant, located in Europe

        # TODO: plant capacity is fixed -- would need a different reference to adjust this
        cli_production = 1 # Mt/y
        cli_cem_ratio = 73.7e-2 # depends on proportion of SCMs
        cem_production = cli_production / cli_cem_ratio # Mt/y
        
        raw_meal_cli_factor = 1.6 # loss of raw meal during production of clinker
        thermal_energy = 3280 # kJ/kg cli
        
        # TODO: add functionality of adding different fuels, and their LHVs so that 
        # we can experiment with different fuel compositions and see if they are
        # viable (right now, these proportions are 'hard coded' into the current TEA)
        fuel = {
                            'Fossil fuel': 69.5e-2,
                            'Alternative fuel': 26e-2,
                            'biomass': 4.5e-2
        }


        elec_cli = 65 # kWh/t cli
        elec_cli_per_cem = elec_cli * cli_cem_ratio # kWh/t cem (same as above but in terms of cement)
        elec_other = 49 # electricity consumption for grinding clinker and other consituents
        elec_tot = elec_cli_per_cem + elec_other # kWh/t cem, grinding of clinker and addition of other constituents

        raw_material_moisture = 6e-2 # %, assuming this is weight that gets evaporated off during the process


        ## Emissions data (specific to reference plant fuel mix, "30 % substitution by alternative fuel mix")
        # when applicable, took the average of the given range of values
        co2_elec = (0.5 + 0.7) / 2 # t CO2/MWh
        spec_indirect_co2_elec = (0.049 + 0.068) / 2 # t CO2/ t cement
        spec_direct_co2_cli = 0.828 # t CO2/t cli
        spec_direct_co2_cli_no_biogenic = 0.804 # t co2/t cli
        total_spec_co2_with_elec = (0.66 + 0.68) / 2 # t co2/t cem

        # ------------------------------ Economic Specs ------------------------------
        # section 5.1

        plant_life = 25 # yr
        capacity_rate = 80e-2 
        cem_production_actual = cem_production * capacity_rate
        contingencies_fees = 1e-2 # fraction of installed costs
        taxation_insurance = 1e-2 # fraction of installed costs, per year


        # ------------------------------ CAPEX ------------------------------
        # section 5.1
        # (all values in M€)
        
        # NOTE: currently this does not include land property (in particular the quarry), 
        # emerging emission abatement technology, developing cost (power & water supply)
        
        ## quarry 
        # TODO
        ## raw materials
        crushing_plant = 3.5
        storage_conveying_raw_material = 3.5
        grinding_plant_raw_meal = 16.8
        storage_conveyor_silo = 2.1
        ## cli production
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
        
        ## installation and total CAPEX 
        civil_steel_erection_other = 75.5 
        installed_costs = equip_costs + civil_steel_erection_other
        epc_costs = 10 
        contigency_fees = installed_costs * contingencies_fees
        tpc = installed_costs + epc_costs + contigency_fees
        owners_costs = 11.9
        other = 8.0 # working capital, start-ups, spare parts
        interest_during_construction = 6.4
        land_cost = 0 # model does not consider cost of land 
        total_capex = tpc + owners_costs + other + interest_during_construction

        # ------------------------------ OPEX ------------------------------ 
        # section 5.1.2

        ## variable TODO: these need to be dependent on the fuel substitutions used and the 
        # source of power (renewable, grid, fossil fuel pp)
        '''
        TODO 
        raw materials: 
        * clinker ingredients (limestone, clay, sand, iron ore)
        * Gypsum
        * SCMs?

        fossil fuel & alternative fuel:
        * hydrogen?
        * types of alternative fuels used --> consider required thermal energy and relative proportions
        
        power:
        * renewables?

        process water:
        * scale with plant capacity
        '''
        raw_materials = 3.7 # €/ton cememt
        fossil_fuel = 35.2 # €/ton cement
        alt_fuel = 1 # €/ton cement 
        power_kiln_plant_grinding = 8.8 # €/ton cement
        process_water = 0.014 # €/ton cement
        
        misc = 0.8 # €/ton cement
        
        # not used in pf
        total_var_opex = raw_materials + fossil_fuel + alt_fuel + power_kiln_plant_grinding + process_water + misc # €/ton cement

        ## fixed (€/ton cem)
        maintenance = 5.0
        operational_labor = 5.5 # NOTE: confused about what document means by "maintenance". Cost of maintenance materials, 
        # maintenance labor, or both? Either way the given value for admin support doesn't really add up
        admin_support = 2.3 # (supposedly 30% of operational and maintenance labor)
        # TODO: sort out what to do with these... not used in pf
        insurance = 0.8
        local_tax = 0.8
        # not used in pf
        total_fixed_opex = maintenance + operational_labor + admin_support + insurance + local_tax
        
        # ------------------------------ ProFAST ------------------------------
        # Set up ProFAST
        pf = ProFAST.ProFAST('blank')
        
        gen_inflation = 0.00
        pf.set_params('commodity',{"name":'cement',"unit":"metric tonnes (t)","initial price":1000,"escalation":gen_inflation})
        pf.set_params('capacity',cem_production * 1e6 / 365) #units/day
        pf.set_params('operating life',plant_life)
        pf.set_params('installation cost',{"value": self.eur_to_usd(installed_costs,1e6),"depr type":"Straight line","depr period":4,"depreciable":False})
        pf.set_params('non depr assets', self.eur_to_usd(land_cost,1e6)) # assuming Mega EUR
        pf.set_params('long term utilization',capacity_rate)
        
        # TODO: not sure how these fit into the model given in the paper
        pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
        pf.set_params('installation months',20) # not sure about this one
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
        pf.set_params('end of proj sale non depr assets',land_cost*(1+gen_inflation)**plant_life)
        pf.set_params('demand rampup',0) # 5.3
        pf.set_params('license and permit',{'value':00,'escalation':gen_inflation})
        
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
        pf.add_capital_item(name='grinding plant, clinker',cost=self.eur_to_usd(grinding_plant_cli,1e6),\
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
        # NOTE: operating labor cost includes maintenance labor cost, according to the paper
        pf.add_fixed_cost(name="Annual Operating Labor Cost",usage=1,unit='$/year',\
                          cost=self.eur_to_usd(operational_labor * cem_production * capacity_rate,1),escalation=gen_inflation)
        # TODO for now, making below be zero, assuming "maintenance" refers to "maintenance materials"
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
        price_breakdown_fossil_fuel = price_breakdown.loc[price_breakdown['Name']=='fossil fuel','NPV'].tolist()[0]
        price_breakdown_alt_fuel = price_breakdown.loc[price_breakdown['Name']=='alternative fuel','NPV'].tolist()[0]
        price_breakdown_power = price_breakdown.loc[price_breakdown['Name']=='power, kiln plant + grinding','NPV'].tolist()[0]
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
                            price_breakdown_fossil_fuel, 
                            price_breakdown_alt_fuel, 
                            price_breakdown_power, 
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
                                'Fossil Fuel',
                                'Alternative Fuel',
                                'Power (Kiln Plant & Grinding Electricity)', 
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
        print(f"price breakdown (paper): {self.eur_to_usd(50.9,1)}")
        
        # TODO what is the point of this line here?
        price_breakdown = price_breakdown.drop(columns=['index','Amount'])

        return(solution,summary,price_breakdown,cem_production_actual,cement_price_breakdown,total_capex)


if __name__ == '__main__':
    plant = ConcretePlant()
    (solution, summary, price_breakdown, cem_production_actual, cement_price_breakdown, total_capex) = \
    plant.run_profast_for_cement()

    print(solution)

    path = Path('C:\\Users\\esharafu\\Documents\\thing.csv')
    thing = pd.DataFrame(cement_price_breakdown,index=[0]).transpose()
    thing.to_csv(path)
































    
    

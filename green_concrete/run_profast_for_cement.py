import ProFAST
import pandas as pd
import os
from pathlib import Path
from green_concrete.convert import *

def run_profast_for_cement(
        self,
        hopp_dict=None,
        lcoh=6.79, 
        hydrogen_annual_production=1e20,  # default value, ensures there is always plenty of hydrogen  
        gen_inflation=0.00,
):
    """
    Performs a techno-economic analysis on a BAT cement plant

    Requires a ConcretePlant instance
    """

    if hopp_dict is not None and hopp_dict.save_model_input_yaml:
        input_dict = { # TODO make sure this is in the right format
            'levelized_cost_hydrogen': lcoh,
            'hydrogen_annual_production': hydrogen_annual_production,
            'configuration dictionary': self.config,
            'atb_year': self.config['ATB year'],
            'site_name': self.config['site location'],
        }

        hopp_dict.add('Models', {'steel_LCOS': {'input_dict': input_dict}})

    if self.feed_consumption['hydrogen']  != 0:
        # TODO this doesn't consider the hydrogen already allocated for steel production, so going to have to account for that sometime
        # TODO clarify with Evan R. and Elenya about the hydrogen stuff and CF
        max_cement_production_capacity_tpy = min(self.config['Cement Production Rate (annual)'] / self.config['Plant capacity factor'], \
                                                hydrogen_annual_production / self.feed_consumption['hydrogen'])
    else:
        max_cement_production_capacity_tpy = self.config['Cement Production Rate (annual)'] # ton/year

    # this will only be different from self.config['Cement Production Rate (annual)'] if hydrogen production can't keep up with the nominal plant capacity
    cement_production_rate_tpy = max_cement_production_capacity_tpy * self.config['Plant capacity factor']


    # TODO cleaner way to do this?
    self.feed_costs['hydrogen'] = lcoh
    
    # ------------------------------ ProFAST ------------------------------
    # Set up ProFAST
    pf = ProFAST.ProFAST('blank')

    pf.set_params('commodity',{"name":'Cement',"unit":"metric tonnes (t)","initial price":1000,"escalation":gen_inflation})
    pf.set_params('capacity', cement_production_rate_tpy / 365) # convert from ton/yr --> ton/day
    pf.set_params('operating life',self.config['Plant lifespan'])
    # NOTE direct costs = equipment costs + installation costs
    pf.set_params('installation cost',{"value": self.total_direct_costs - sum(self.equip_costs.values()),"depr type":"Straight line","depr period":4,"depreciable":False})
    pf.set_params('non depr assets', self.land_cost) 
    pf.set_params('long term utilization',self.config['Plant capacity factor'])
    pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
    pf.set_params('installation months', self.config['Construction time (months)']) # source: CEMCAP
    pf.set_params('analysis start year',2022) # is this ok? financials are based on 2013 conversion rates
    pf.set_params('credit card fees',0)
    pf.set_params('sales tax',0) 
    pf.set_params('rent',{'value':0,'escalation':gen_inflation})
    pf.set_params('property tax and insurance percent',0)
    pf.set_params('total income tax rate',0.27)
    pf.set_params('capital gains tax rate',0.15)
    pf.set_params('sell undepreciated cap',True)
    pf.set_params('tax losses monetized',True)
    pf.set_params('operating incentives taxable',True)
    pf.set_params('general inflation rate',gen_inflation)
    pf.set_params('leverage after tax nominal discount rate',0.0824) # 0.0824
    pf.set_params('debt equity ratio of initial financing',1.38) # 1.38
    pf.set_params('debt type','Revolving debt')
    pf.set_params('debt interest rate',0.0489) # 0.0489
    pf.set_params('cash onhand percent',1)
    pf.set_params('admin expense percent',0)
    pf.set_params('end of proj sale non depr assets',self.land_cost*(1+gen_inflation)**self.config['Plant lifespan'])
    pf.set_params('demand rampup',5.3) # 5.3
    pf.set_params('license and permit',{'value':00,'escalation':gen_inflation})

    # ------------------------------ Add capital items to ProFAST ------------------------------
    # NOTE: these are all converted to USD
    # NOTE: did not change the last three arguments
    for key, value in self.equip_costs.items():
        pf.add_capital_item(name=key,cost=value,depr_type="MACRS",depr_period=7,refurb=[0]) 
    
    # ------------------------------ Add fixed costs ------------------------------
    pf.add_fixed_cost(name="Annual Operating Labor Cost",usage=1,unit='$/year', cost=self.operational_labor,escalation=gen_inflation)
    pf.add_fixed_cost(name="Maintenance Labor Cost",usage=1,unit='$/year', cost=self.maintenance_labor,escalation=gen_inflation)
    pf.add_fixed_cost(name="Administrative & Support Labor Cost",usage=1,unit='$/year', cost=self.admin_support,escalation=gen_inflation)
    pf.add_fixed_cost(name="Property tax and insurance",usage=1,unit='$/year', cost=self.config['Taxation and insurance'] * self.tpc,escalation=0.0) 
    
    # ------------------------------ Add feedstocks, note the various cost options ------------------------------
    # NOTE feedstocks without consumption data have a usage of 1 (i.e. already in the desired units)
    for key, value in self.feed_units.items():
        pf.add_feedstock(name=key, usage=self.feed_consumption[key], unit=f'{self.feed_units[key]} per ton cement',cost=self.feed_costs[key],escalation=gen_inflation)

    # TODO add this to dictionary
    pf.add_feedstock(name='Maintenance Materials',usage=1.0,unit='Units per ton of cement',cost=self.maintenance_equip / self.config['Cement Production Rate (annual)'],escalation=gen_inflation)

    # ------------------------------ Solve for breakeven price ------------------------------
    solution = pf.solve_price()
    summary = pf.summary_vals
    price_breakdown = pf.get_cost_breakdown()

    print(f"price breakdown (ProFAST): {solution['price']}")
    print(f"price breakdown (paper): {eur2013(1, 50.9)}")
    print(f"price breakdown (CEMCAP spreadsheet, excluding carbon tax): {eur2013(1, 46.02)}")
    print(f"percent error from CEMCAP: {(solution['price'] - eur2013(1, 46.02))/eur2013(1, 46.02) * 100}%")
    
    price_breakdown = price_breakdown.drop(columns=['index', 'Amount'])
    price_breakdown_manual = self.manual_price_breakdown_helper(gen_inflation, price_breakdown)
    cement_annual_capacity = self.config['Cement Production Rate (annual)']
    cement_nominal_capacity = self.config['Cement Production Rate (annual)'] * self.config['Plant capacity factor']
    cement_breakeven_price = solution.get('price')

    # # Calculate margin of what is possible given hydrogen production and actual steel demand
    # #steel_production_capacity_margin_mtpy = hydrogen_annual_production/1000/hydrogen_consumption_for_steel - steel_annual_capacity
    # cement_production_capacity_margin_pc = (hydrogen_annual_production / 1000 / self.feed_consumption['hydrogen'] - cement_annual_capacity) \
    #                                         / cement_annual_capacity * 100

    # hydrogen_annual_production: kg/yr
    
    cement_production_capacity_margin_pc = 0 # TODO should I implement this?

    if hopp_dict is not None and hopp_dict.save_model_output_yaml:
        output_dict = {
            'cement_economics_from_profast': solution,
            'cement_economics_summary': summary,
            'cement_breakeven_price': cement_breakeven_price,
            'cement_annual_capacity': cement_annual_capacity,
            'cement_price_breakdown': price_breakdown_manual,
            'cement_plant_capex': self.total_capex,
        }
        hopp_dict.add('Models', {'steel_LCOS': {'output_dict': output_dict}})


    ###\ write files (for testing)
    path = Path('C:\\Users\\esharafu\\Documents\\cement_econ.csv')
    thing = pd.DataFrame(price_breakdown_manual,index=[0]).transpose()
    thing.to_csv(path)

    path = Path('C:\\Users\\esharafu\\Documents\\profast_breakdown.csv')
    thing = pd.DataFrame(price_breakdown)
    thing.to_csv(path)
    ###/

    return hopp_dict, solution, summary, price_breakdown, cement_breakeven_price, \
        cement_annual_capacity, cement_production_capacity_margin_pc, price_breakdown_manual
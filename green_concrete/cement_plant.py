"""
Created on Wed June 14 2:28 2023

@author: evan-sharafuddin
"""

import ProFAST
import pandas as pd
from pathlib import Path
import os
from green_concrete.convert import *

# Unit conventions (mostly):
# * electricity = kWh
# * fuels = MJ
# * mass = kg
# * money = $
# * functional unit = ton of cement

# Source unless otherwise specified: IEAGHG REPORT (https://ieaghg.org/publications/technical-reports/reports-list/9-technical-reports/1016-2013-19-deployment-of-ccs-in-the-cement-industry)
# Other Sources:
#     CEMCAP Spreadsheet (https://zenodo.org/record/1475804)
#     CEMCAP Report (https://www.sintef.no/globalassets/project/cemcap/2018-11-14-deliverables/d4.6-cemcap-comparative-techno-economic-analysis-of-co2-capture-in-cement-plants.pdf)
#     Fuel LHV values (https://courses.engr.illinois.edu/npre470/sp2018/web/Lower_and_Higher_Heating_Values_of_Gas_Liquid_and_Solid_Fuels.pdf)
#     Emission Factors for fuel (https://www.sciencedirect.com/science/article/pii/S0959652622014445)
#     Emission factors for electricity (https://emissionsindex.org/)
#     USA clinker-to-cement ratio (https://pcr-epd.s3.us-east-2.amazonaws.com/634.EPD_for_Portland_Athena_Final_revised_04082021.pdf)

# TODO
# Important Assumptions
# * "It is worth noting that the development and land costs are not considered in the project estimates."
# * TPC calculations exclude "land property (in particula rthe quaqrry), emerging emission abatement technology 
# (e.g. SCR) and developing cost (power and water supply)"
# * Production Costs: "excl. freight, raw material deposit, land property, permits etc."
# * The scope of this model seems to mainly be the clinkering plant, as there is no mention of any SCMs, cement mixing, etc. 
# So it makes sense that the cost of OPC is more than the cost of lower clinker-to-cement mixtures

class CementPlant:
    """  
    Class for green concrete analysis

    Attributes:
        CAPEX
            self.config: holds  general plant information
                CSS: 'None', 'Oxyfuel', 'CaL (tail-end)'
                    'Oxyfuel' and 'CaL (tail-end)' are both derived from the "base case" scenarios found in CEMCAP d4.6
                Fuel Mixture: 'C1-C6' (percentages are LHV fractions unless otherwise stated)
                    C1: 100% coal
                    C2: 70% coal, 30% IEAGHG alternative fuel mix
                    C3: 50% coal, 50% natural gas
                    C4: 50% coal, 50% natural gas with 10% hydrogen by volume
                    C5: 39% hydrogen, 12% MBM, 49% glycerin (experimental fuel mix)
                    C6: 80% natural gas, 20% hydrogen
                Renewable electricity: determines if grid electricity or HOPP hybrid renewable simulation will be used
                Using SCMs: 'OPC', 'US Average', 'European Average'
                ATB year: see define_scenarios
                Site location: 'IA', 'WY', 'TX', 'MS', 'IN'
                Clinker Production Rate (annual): ideal annual production rate of clinker
                Clinker-to-cement ratio: fraction of clinker that goes into the final cement product
                    NOTE this is essentially a multiplyer at this point. The scope of this model ends at clinker,
                    and the cement produced depends on this clinker-to-cement ratio. Future work would involve
                    replacing 
                Plant lifespan: int, number of years
                Plant capacity factor: percentage of the year that plant is operating 
                    (accounts for maintenance closures, etc)
                Construction time (months): int
                Contingencies and fees: float, fraction of installed costs (CAPEX)
                Taxation and insurance: float, fraction of installed costs, annual (fixed OPEX)
                Cement Production Rate (annual): ideal annual production rate of cement 
                    (calculated using clinker-to-cement ratio)
                Thermal energy demand (MJ/kg clinker): specific thermal energy demand of the clinkering process
                Electrical energy demand (kWh/t cement): specific electrical energy demand required by grinders, 
                    rotating kiln, fans, etc
        
            self.equip_costs: holds names and costs of each major capital component
            self.tpc: total plant cost (equipment, installation, contingencies, etc)
            self.total_capex: tpc + land cost 
            self.total_direct_costs: i.e. installed costs (equipment + installation)
            self.land_cost: TODO model does not currently account for this 

        VARIABLE OPEX
            self.feed_consumption: consumption rates for each feedstock
            self.feed_costs: costs per unit of each feedstock
            self.feed_units: units that each feedstock is measured in
            TODO need better value for renewable energy LCOE
        
        FIXED OPEX
            self.operational_labor: labor costs for employees
            self.maintenance_equip: essentially a feedstock
            self.maintenance_labor: separate from maintenance equipment
            self.admin_support: labor in addition to maintenance and operations
    """

    def __init__(
        self, 
        css='None', 
        fuel_mix='C2',
        renewable_electricity=False, 
        SCM_composition='European Average', 
        couple_with_steel_ammonia=True, 
        atb_year=2035, 
        site_location='IA', 
        cli_production=1e6, 
        plant_life=25, 
        plant_capacity_factor = 0.90, # same as steel/ammonia, for consistency
    ): 
        
        # ------------ Plant Info ------------

        # ADD DIFFERENT SCM SCENARIOS HERE
        SCM_cli_cem = {
            'OPC': 0.95, # Ordinary Portland Cement
            'US Average': 0.914, #https://pcr-epd.s3.us-east-2.amazonaws.com/634.EPD_for_Portland_Athena_Final_revised_04082021.pdf
            'European Average': 0.737 # from IEAGHG/CEMCAP
        }

        '''
        decreasing clinker/cement ratio resulting in lower cost?
        https://rmi.org/wp-content/uploads/2021/08/ConcreteGuide2.pdf
        * might be valid, but need to be careful about assumptions "embedded" in the 73.7% cli/cem ratio
        claimed by IEAGHG/CEMCAP
        
        '''
        
        # Select cli-cem ratio based on SCM composition
        if SCM_composition not in SCM_cli_cem.keys():
            raise Exception('Invalid SCM composition')
        cli_cem_ratio = SCM_cli_cem[SCM_composition]

        if css == 'None':
            self.config = {
                'CSS': css, # None, Oxyfuel, Calcium Looping
                'Fuel Mixture': fuel_mix, # C1-C5
                'Renewable electricity': renewable_electricity,
                'Steel & Ammonia': couple_with_steel_ammonia,
                'SCMs': SCM_composition,
                'ATB year': atb_year,
                'site location': site_location,
                'Clinker Production Rate (annual)': cli_production,
                'Clinker-to-cement ratio': cli_cem_ratio,
                'Cement Production Rate (annual)': cli_production / cli_cem_ratio,
                'Plant lifespan': plant_life,
                'Plant capacity factor': plant_capacity_factor,
                'Contingencies and fees': 1e-2, # fraction of installed costs (CAPEX)
                'Taxation and insurance': 1e-2, # fraction of installed costs, per year (OPEX)
                'Construction time (months)': 36,
                'Thermal energy demand (MJ/kg clinker)': 3.136, # MJ/kg cli 
                'Electrical energy demand (kWh/t cement)': 90, # kWh/t cement (NOTE assuming this does not depend on the clinker-to-cement ratio, because 
                                                               #               addition of SCMs increases electrical consumption for grinding, etc)
                                                               # Source of assumption: https://docs.wbcsd.org/2017/06/CSI_ECRA_Technology_Papers_2017.pdf, No 31
                'Carbon capture efficency (%)': 0,
                'Hopp dict': None,
            }
        
        elif css == 'Oxyfuel':
            self.config = {
                'CSS': css, # None, Oxyfuel, Calcium Looping
                'Fuel Mixture': fuel_mix, # C1-C5
                'Renewable electricity': renewable_electricity,
                'Steel & Ammonia': couple_with_steel_ammonia,
                'Using SCMs': SCM_composition,
                'ATB year': atb_year,
                'site location': site_location,
                'Clinker Production Rate (annual)': cli_production,
                'Clinker-to-cement ratio': cli_cem_ratio,
                'Cement Production Rate (annual)': cli_production / cli_cem_ratio,
                'Plant lifespan': plant_life,
                'Plant capacity factor': plant_capacity_factor,
                'Contingencies and fees': 1e-2, # fraction of installed costs (CAPEX)
                'Taxation and insurance': 1e-2, # fraction of installed costs, per year (OPEX)
                # https://www.sciencedirect.com/science/article/pii/S0306261922005529#b0150 & CEMCAP Oxyfuel base case
                'Construction time (months)': 60, # combined plant and carbon capture system construction
                'Thermal energy demand (MJ/kg clinker)': 3.349, # MJ / kg cli
                'Electrical energy demand (kWh/t cement)': 132 * 1.67 * cli_cem_ratio, # kWh/t cem, using 67% increase claimed in article
                'Carbon capture efficency (%)': 0.9, # CEMCAP
                'Hopp dict': None,
            }

        elif css == 'CaL (tail-end)': # based on base-case from CEMCAP
            if fuel_mix != 'C1':
                print('Be careful... CaL calciner might require coal as a fuel source in reality.')
            self.config = {
                'CSS': css, # None, Oxyfuel, Calcium Looping
                'Fuel Mixture': fuel_mix, # C1-C5
                'Renewable electricity': renewable_electricity,
                'Steel & Ammonia': couple_with_steel_ammonia,
                'Using SCMs': SCM_composition,
                'ATB year': atb_year,
                'site location': site_location,
                'Clinker Production Rate (annual)': cli_production,
                'Clinker-to-cement ratio': cli_cem_ratio,
                'Cement Production Rate (annual)': cli_production / cli_cem_ratio,
                'Plant lifespan': plant_life,
                'Plant capacity factor': plant_capacity_factor,
                'Contingencies and fees': 1e-2, # fraction of installed costs (CAPEX)
                'Taxation and insurance': 1e-2, # fraction of installed costs, per year (OPEX)
                'Construction time (months)': 60, # combined plant and carbon capture system construction
                'Thermal energy demand (MJ/kg clinker)': 7.1 , # MJ / kg cli
                    # TODO possibility that the CaL calciner can only use coal and not the alternative
                    # fuel mixes, so might want to keep this in mind
                'Electrical energy demand (kWh/t cement)': -41.2 * cli_cem_ratio, # kWh/t cem, net electricity consumption (electricity consumed - electricity generated)
                    # NOTE power is actually generated when ASU consumption is excluded
                'Carbon capture efficency (%)': 0.936,
                'Hopp dict': None,
            }

        else:
            raise Exception('Invalid CSS Scenario.')

        
        # ---------- CAPEX and OPEX ----------
        (self.equip_costs, 
         self.tpc, 
         self.total_capex, 
         self.total_direct_costs, 
         self.land_cost) = self._capex_helper()
        
        (self.feed_consumption, 
         self.feed_costs, 
         self.feed_units,
         self.lhv, 
         self.operational_labor, 
         self.maintenance_equip, 
         self.maintenance_labor, 
         self.admin_support) = self._opex_helper()
        
        # this is used in run_scenarios to store info used for bug fixing
        self.hopp_misc = dict()

    # See files for documentation on these functions
    def _capex_helper(self):
        from green_concrete.capex import capex
        return capex(self)
    
    def _opex_helper(self):
        from green_concrete.opex import opex
        return opex(self)
    
    def lca_helper(self):
        from green_concrete.lca import lca
        return lca(self)
    
    def run_pf(
        self, 
        lcoh=6.79, 
        hydrogen_annual_production=1e20,  # default value, ensures there is always plenty of hydrogen  
    ):
        from green_concrete.run_profast_for_cement import run_profast_for_cement
        return run_profast_for_cement(self, lcoh, hydrogen_annual_production)
    
    def manual_price_breakdown_helper(
        self, 
        gen_inflation, 
        price_breakdown
    ):
        from green_concrete.manual_price_breakdown import manual_price_breakdown
        return manual_price_breakdown(self, gen_inflation, price_breakdown)
    
if __name__ == '__main__':
    plant = CementPlant()
    hopp_dict, solution, summary, price_breakdown, cement_breakeven_price, \
    cement_annual_capacity, cement_production_capacity_margin_pc, cement_price_breakdown = \
    plant.run_pf()

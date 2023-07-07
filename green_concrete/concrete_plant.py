"""
Created on Wed June 14 2:28 2023

@author: evan-sharafuddin
"""

import ProFAST
import pandas as pd
from pathlib import Path
import os
from green_concrete.convert import *

# Abbreviations
# LHV - lower heat value 
# ng - natural gas
# cli - clinker
# cem - cement
# tdc - total direct costs (see paper)
# epc - Engineering, process, and construction costs (total direct costs + indirect costs)
# om - O&M
# BAT - best available technology

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

# TODO
# TRY TO MAKE THE LCOC SOMEWHAT SIMILAR TO THAT IN THE PAPER --> off by about 20...
# Important Assumptions
# * "It is worth noting that the development and land costs are not considered in the project estimates."
# * TPC calculations exclude "land property (in particula rthe quaqrry), emerging emission abatement technology 
# (e.g. SCR) and developing cost (power and water supply)"
# * Production Costs: "excl. freight, raw material deposit, land property, permits etc."

class ConcretePlant:
    """  
    Class for green concrete analysis

    NOTE only considering a cement plant at the moment but this might change

    Attributes:
        CAPEX
            self.config: holds  general plant information
                CSS: 'None', 'Oxyfuel', 'Calcium Looping'
                Fuel Mixture: 'C1-C5'
                Renewable electricity: determines if grid electricity will be used
                Using SCMs: TODO determines whether additional SCMs will be used
                ATB year: see define_scenarios
                Site location: 'IA', 'WY', 'TX', don't remember the other two
                Clinker Production Rate (annual): ideal annual production rate of clinker
                Clinker-to-cement ratio: fraction of clinker that goes into the final cement product
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
            self.total_capex: includes land and owners cost TODO seems to be equal to tpc for oxyfuel data
            self.total_direct_costs: i.e. installed costs (equipment + installation)
            self.land_cost: TODO model does not currently account for this 

        VARIABLE OPEX
            self.feed_consumption: consumption rates for each feedstock
            self.feed_costs: costs per unit of each feedstock
            self.feed_units: units that each feedstock is measured in
        
        FIXED OPEX
            self.operational_labor: labor costs for employees
            self.maintenance_equip: essentially a feedstock
            self.maintenance_labor: separate from maintenance equipment
            self.admin_support: labor in addition to maintenance and operations
    """

    def __init__(
        self, 
        css='None', 
        fuel_mix='C1',
        renewable_electricity=False, 
        SCMs=False, 
        atb_year=2035, 
        site_location='IA', 
        cli_production=1e6, 
        cli_cem_ratio=73.7e-2, 
        plant_life=25, 
        plant_capacity_factor = 91.3e-2 # source of plant_capacity_factor: CEMCAP
    ): 
        
        # ------------ Plant Info ------------
        if css == 'None':
            self.config = {
                'CSS': css, # None, Oxyfuel, Calcium Looping
                'Fuel Mixture': fuel_mix, # C1-C5
                'Renewable electricity': renewable_electricity,
                'Using SCMs': SCMs,
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
                'Electrical energy demand (kWh/t cement)': 132 * cli_cem_ratio, # kWh/t cement 
            }
        
        elif css == 'Oxyfuel':
            self.config = {
                'CSS': css, # None, Oxyfuel, Calcium Looping
                'Fuel Mixture': fuel_mix, # C1-C5
                'Renewable electricity': renewable_electricity,
                'Using SCMs': SCMs,
                'ATB year': atb_year,
                'site location': site_location,
                'Clinker Production Rate (annual)': cli_production,
                'Clinker-to-cement ratio': cli_cem_ratio,
                'Cement Production Rate (annual)': cli_production / cli_cem_ratio,
                'Plant lifespan': plant_life,
                'Plant capacity factor': plant_capacity_factor,
                'Contingencies and fees': 1e-2, # fraction of installed costs (CAPEX)
                'Taxation and insurance': 1e-2, # fraction of installed costs, per year (OPEX)
                # https://www.sciencedirect.com/science/article/pii/S0306261922005529#b0150
                'Construction time (months)': 60, # combined plant and carbon capture system construction
                'Thermal energy demand (MJ/kg clinker)': 3.349, # MJ / kg cli
                'Electrical energy demand (kWh/t cement)': 132 * 1.67 * cli_cem_ratio, # kWh/t cem, using 67% increase claimed in article
            }
        
        else:
            raise Exception('Invalid CSS Scenario.')

        # ---------- CAPEX and OPEX ----------
        (self.equip_costs, 
         self.tpc, 
         self.total_capex, 
         self.total_direct_costs, 
         self.land_cost) = self.__capex_helper()
        
        (self.feed_consumption, 
         self.feed_cost, 
         self.feed_units, 
         self.operational_labor, 
         self.maintenance_equip, 
         self.maintenance_labor, 
         self.admin_support) = self.__opex_helper()

    # See files for documentation on these functions
    def __capex_helper(self):
        from green_concrete.capex import capex
        return capex(self)
    
    def __opex_helper(self):
        from green_concrete.opex import opex
        return opex(self)
    
    def lca_helper(self):
        from green_concrete.lca import lca
        return lca(self)
    
    def run_pf(
        self, 
        hopp_dict=None,
        lcoh=6.79, 
        hydrogen_annual_production=1e20,  # default value, ensures there is always plenty of hydrogen  
    ):
        from green_concrete.run_profast_for_cement import run_profast_for_cement
        return run_profast_for_cement(self, hopp_dict, lcoh, hydrogen_annual_production)
    
    def manual_price_breakdown_helper(
        self, 
        gen_inflation, 
        price_breakdown
    ):
        from green_concrete.manual_price_breakdown import manual_price_breakdown
        return manual_price_breakdown(self, gen_inflation, price_breakdown)
    
if __name__ == '__main__':
    plant = ConcretePlant()
    hopp_dict, solution, summary, price_breakdown, cement_breakeven_price, \
    cement_annual_capacity, cement_production_capacity_margin_pc, cement_price_breakdown = \
    plant.run_pf()

"""
## outline (ignore)
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


# ------------------------- Carbon Capture Options -------------------------
    

# //////////// Calcium Looping ///////////////


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


# ------------------------- Fixed Parameters (structural things to keep in mind?) -------------------------------
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
"""
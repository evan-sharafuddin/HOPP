
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

'''
Unit conventions (mostly):
* electricity = kWh
* fuels = MJ
* mass = kg
* money = $
* functional unit = ton of cement

'''
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
# * Production Costs: "excl. freight, raw material deposit, land property, permits etc."


class ConcretePlant:
    """  
    Class for green concrete analysis

    NOTE only considering a cemenet plant at the moment but this might change
        
    """

    def __init__(self, css='None', fuel_mix='C4',\
                 renewable_electricity=False, SCMs=False, atb_year=2035, site_location='IA', cli_production=1e6, \
                 cli_cem_ratio=73.7e-2, plant_life=25, plant_capacity_factor = 91.3e-2):
                 # source of plant_capacity_factor: CEMCAP
        
        # ------------ Plant Info ------------
        self.config = {
            'CSS': css, # None, Oxyfuel, Calcium Looping
            'Fuel Mixture': fuel_mix, # C1-C5
            'Renewable electricity': renewable_electricity,
            'Using SCMs': False,
            'ATB year': atb_year,
            'site location': site_location,
            'Clinker Production Rate (annual)': cli_production,
            'Clinker-to-cement ratio': cli_cem_ratio,
            'Plant lifespan': plant_life,
            'Plant capacity factor': plant_capacity_factor,
            'Construction time (months)': 36
        }
        
        self.config['Cement Production Rate (annual)'] = self.config['Clinker Production Rate (annual)'] / self.config['Clinker-to-cement ratio']
        # NOTE cement production rate depends on clinker production rate and clinker/cement ratio

        ###\ https://www.sciencedirect.com/science/article/pii/S0306261922005529#b0150
        if self.config['CSS'] == 'Oxyfuel':
            thermal_energy = 3.349 # MJ / kg cli
            electrical_energy = 150 * self.config['Clinker-to-cement ratio'] # kWh/t cem
            self.config['Construction time (months)'] = 60
        else:
            thermal_energy = 3.136 # MJ/kg cli -- might want to fact check this (2010, worldwide, preclaciner/preheater dry kiln)
            electrical_energy = 108 # kWh/t cement (2010, worldwide)
        ###/

        contingencies_fees = 1e-2 # fraction of installed costs (CAPEX)
        taxation_insurance = 1e-2 # fraction of installed costs, per year (OPEX)

        self.config['Thermal energy demand (MJ/kg clinker)'] = thermal_energy
        self.config['Electrical energy demand (kWh/t cement)'] = electrical_energy
        self.config['Contingencies and fees'] = contingencies_fees
        self.config['Taxation and insurance'] = taxation_insurance

        # ---------- CAPEX and OPEX ----------
        self.equip_costs, self.tpc, self.total_capex, self.installed_costs, self.land_cost = self.capex()
        
        self.feed_consumption, self.feed_cost, self.feed_units, self.other_opex = self.opex()
        self.operational_labor, self.maintenance_equip, self.maintenance_labor, self.admin_support = self.other_opex

    def capex(self):
        # section 5.1
        # NOTE all values in M€
        # NOTE currently this does not include land property (in particular the quarry), 
        # emerging emission abatement technology, developing cost (power & water supply)

        config = self.config

        ### Plant Equipment
        equip_costs = {
            ## quarry 
            # TODO
            ## raw material crushing and prep
            'crushing plant': 3.5,
            'storage, conveying raw material': 3.5,
            'grinding plant, raw meal': 16.8,
            'storage, conveyor, silo': 2.1,
            ## pyroprocessing
            'kiln plant': 11.9,
            'grinding plant, clinker': 9.8,
            ## cem production
            'silo': 9.8,
            'packaging plant, conveyor, loading, storing': 6.3,
            ## coal grinding 
            'coal mill, silo': 6.3,
        }
        
        total_equip_costs = sum(equip_costs.values()) # for use in calculating equipment costs

        ### installation
        civil_steel_erection_other = 75.5 
        installed_costs = total_equip_costs + civil_steel_erection_other
        epc_costs = 10 
        contigency_fees = installed_costs * config['Contingencies and fees']
        tpc = installed_costs + epc_costs + contigency_fees
        # NOTE according to spreadsheet, tpc = 203.75
        owners_costs = 11.9
        other = 8.0 # working capital, start-ups, spare parts
        interest_during_construction = 6.4
        land_cost = 0 # TODO
        total_capex = tpc + owners_costs + other + interest_during_construction + land_cost

        # define variables
        co2_capture_equip_oxy = dict()
        total_direct_costs_oxy = float()
        process_contingency_oxy = float()
        indirect_costs_oxy = float()
        owners_costs_oxy = float()
        project_contingencies_oxy = float() 
        tpc_oxy = float() 

        if self.config['CSS'] == 'Oxyfuel':
            # https://www.mdpi.com/1996-1073/12/3/542#app1-energies-12-00542 -- supplementary materials
            ''' 
            NOTES:
            * EC (equipment cost) + IC (installation cost) = TDC (total direct cost)
            * cost basis = 2014 EUR 
            * values coded in are first in kEUR but converted to $
            * 'false air' = air that has leaked into the flue gas (which ideally would've been 
            pure water and carbon dioxide)
            '''
            ### CAPEX
            # NOTE these are equipment costs and not direct costs
            co2_capture_equip_oxy = {
                # Oxyfuel core process units
                'OXY: Clinker cooler, kiln hood and sealings (core process)': 2944 + 102 + 160 + 160,
                'OXY: Fans, compressors and blowers (core process)': 233 + 355 + 74 + 1880,
                'OXY: Other equipment (core process)': 70 + 441 + 1013 + 19461,
                # Oxyfuel waste heat recovery system
                'OXY: Heat exchangers (waste heat recovery)': 33 + 1376 + 77 + 198 + 45 + 79 + 781 + 520 + 24 + 337,
                'OXY: Tanks and vessels (waste heat recovery)': 800,
                'OXY: Electric generators (waste heat recovery)': 3984,
                'OXY: Pumps (waste heat recovery)': 156,
                # CO2 Purification unit (CPU)
                'OXY: Fans, compressors and expanders (CPU)': 17369 + 2572 + 696,
                'OXY: Tanks and vessels (CPU)': 252 + 179 + 117 + 118 + 99,
                'OXY: Heat exchangers (CPU)': 37 + 31 * 3 + 30 + 75 + 849,
                'OXY: Pumps (CPU)': 351,
                'OXY: Other equipment (CPU)': 112,
                'OXY: Cooling tower (CPU)': 588,
            }

            total_direct_costs_oxy = 71595 # sum of the direct costs column in supplementary materials
            process_contingency_oxy = total_direct_costs_oxy * (0.3 + 0.12)
            indirect_costs_oxy = total_direct_costs_oxy * 0.14
            owners_costs_oxy = total_direct_costs_oxy * 0.07
            project_contingencies_oxy = total_direct_costs_oxy * 0.15
            tpc_oxy = total_direct_costs_oxy + process_contingency_oxy + indirect_costs_oxy \
                + owners_costs_oxy + project_contingencies_oxy

        # ////////// unit conversions ////////////// € --> $
        for key, value in equip_costs.items():
            equip_costs[key] = self.eur2013(1e6, value)
        for key, value in co2_capture_equip_oxy.items():
            co2_capture_equip_oxy[key] = self.eur2014(1e3, value)
        tpc, total_capex, installed_costs, land_cost = self.eur2013(1e6, tpc, total_capex, installed_costs, land_cost)
        tpc_oxy, total_direct_costs_oxy = self.eur2014(1e3, tpc_oxy, total_direct_costs_oxy) 
        
        if self.config['CSS'] == 'Oxyfuel':
            # update reference plant CAPEX TODO only considering tpc and equipment for now
            equip_costs.update(co2_capture_equip_oxy)
            tpc += tpc_oxy
            total_capex += tpc_oxy
            installed_costs += total_direct_costs_oxy

        return equip_costs, tpc, total_capex, installed_costs, land_cost 

    def opex(self): # includes alternate fuel mixtures
        config = self.config
      
        # ///////////// FEEDSTOCKS /////////////
        lhv = {
            ###\ Source: Fuel LHV values; Canada paper (see below) for volume based LHVs
            'coal': 26.122, # MJ/kg, ASSUMING "bituminous coal (wet basis)"
            'natural gas': 47.141, # MJ/kg
            'hydrogen': 120.21, # MJ/kg
            'pet coke': 29.505, # MJ/kg 
            ###/

            ###\ "european alternative fuel input" -- IEAGHG
            'animal meal': 18, # MJ/kg
            'sewage sludge': 4, # MJ/kg (wide range exists, including heating value for the dry substance...)
                # https://www.sludge2energy.de/sewage-sludge/calorific-value-energy-content/#:~:text=The%20dry%20substance%2Dbased%20(DS,planning%20a%20sludge2energy%20plant%20concept.
            'pretreated domestic wastes': 16, # MJ/kg
            'pretreated industrial wastes': (18 + 23) / 2, # MJ/kg (given as range)
            'tires': 28, # MJ/kg # TODO this might be too conservative
            'solvents': (23 + 29) / 2, # MJ/kg (given as range)
            ###/

            ###\ https://backend.orbit.dtu.dk/ws/portalfiles/portal/161972551/808873_PhD_thesis_Morten_Nedergaard_Pedersen_fil_fra_trykkeri.pdf, table 3-4
            'SRF (wet)': 23.2 * (1 - 0.167), # MJ/kg as recieved, Solid Recovered Fuel or Refused Derived Fuel (RDF)
            'MBM (wet)': 19.4 * (1 - 0.04), # MJ/kg as recieved, Meat and Bone Meal
            ###/

            ###\ https://www.researchgate.net/publication/270899362_Glycerol_Production_consumption_prices_characterization_and_new_trends_in_combustion
            'glycerin': 16 # MJ/kg NOTE this value might depend on the production of GLYCEROL, which makes up 95% of glycerin
            ###/
        }

        ###\ TODO is this even necissary?
        # can change this by altering the compositions of each fuel below, or by introducing new alternative fuels
        alt_fuel_lhv = 0.194 * lhv['tires'] + 0.117 * lhv['solvents'] + 0.12 * lhv['pretreated domestic wastes'] \
        + 0.569 * lhv['pretreated industrial wastes'] # multiplying by each fuel's composition, MJ/kg 
        
        lhv['alt fuel (IEAGHG mix)'] = alt_fuel_lhv
        ###/

        # fuel compositions (percent thermal input) -- must add up to 1

        '''
        SOURCES:
        Canada: Synergizing hydrogen and cement industries for Canada's climate plan - case study
        IEAGHG: https://ieaghg.org/publications/technical-reports/reports-list/9-technical-reports/1016-2013-19-deployment-of-ccs-in-the-cement-industry 
        '''
            # COMPOSITION 1: Canada Reference (100% coal)
        
        fuel_comp = {
            'C1': {
                'coal': 1,
                'natural gas': 0,
                'hydrogen': 0,
                'pet coke': 0,
                'alt fuel (IEAGHG mix)': 0,
                'animal meal': 0,
                'sewage sludge': 0,
                'solvents': 0,
                'SRF (wet)': 0,
                'MBM (wet)': 0,
                'glycerin': 0,
            },

            # COMPOSITION 2: IEAGHG Reference (70% coal, 30% alernative fuel mix)
            'C2': {
                'coal': 0.7,
                'natural gas': 0,
                'hydrogen': 0,
                'pet coke': 0,
                'alt fuel (IEAGHG mix)': 0.3,
                'animal meal': 0,
                'sewage sludge': 0,
                'solvents': 0,
                'SRF (wet)': 0,
                'MBM (wet)': 0,
                'glycerin': 0,
            },

            # COMPOSITION 3: Canada Natural Gas Substitution
            'C3': {
                'coal': 0.5,
                'natural gas': 0.5,
                'hydrogen': 0,
                'pet coke': 0,
                'alt fuel (IEAGHG mix)': 0,
                'animal meal': 0,
                'sewage sludge': 0,
                'solvents': 0,
                'SRF (wet)': 0,
                'MBM (wet)': 0,
                'glycerin': 0,
            },

            # COMPOSITION 4: Canada Hydrogen-Enriched Natural Gas Substitution
            # TODO when finding consumption values need to consider that LHV for hydrogen and NG are given as volume, but coal is given in an energy basis

            'C4': {
                'coal': 0.5,
                'natural gas': 0.45,
                'hydrogen': 0.05,
                'pet coke': 0,
                'alt fuel (IEAGHG mix)': 0,
                'animal meal': 0,
                'sewage sludge': 0,
                'solvents': 0,
                'SRF (wet)': 0,
                'MBM (wet)': 0,
                'glycerin': 0,
            },      

            # COMPOSITION 5: Experimental Climate Neutral Plant: https://www.heidelbergmaterials.com/en/pr-01-10-2021
            # TODO is composition based on mass/volume or energy?
            'C5': {
                'coal': 0,
                'natural gas': 0,
                'hydrogen': 0.39,
                'pet coke': 0,
                'alt fuel (IEAGHG mix)': 0,
                'animal meal': 0,
                'sewage sludge': 0,
                'solvents': 0,
                'SRF (wet)': 0,
                'MBM (wet)': 0.12,
                'glycerin': 0.49,
            },
        }

        ###\ NOTE converting NG and hydrogen from volume to energy basis --> CHECK THIS OR FIND DIFFERENT SOURCE
        from sympy import symbols, Eq, solve
        # x = energy fraction of natural gas
        # y = energy fraction of hydrogen gas
        x, y = symbols('x y')

        # densities and specific energies for the fuels
        rho_ng = 0.717 # kg/m^3 https://www.cs.mcgill.ca/~rwest/wikispeedia/wpcd/wp/n/Natural_gas.htm
        rho_h2 = 0.08376 # kg/m^3 https://www1.eere.energy.gov/hydrogenandfuelcells/tech_validation/pdfs/fcm01r0.pdf
        e_ng = 47.141 # see LHV's in opex()
        e_h2 = 120.21 # see LHV's in opex()

        # equations
        eq1 = Eq(x + y, 0.5)
        eq2 = Eq(x / (rho_ng * e_ng) - 10 * y / (rho_h2 * e_h2), 0)

        solution = solve((eq1, eq2), (x, y))
        
        fuel_comp['C4']['natural gas'] = float(solution[x])
        fuel_comp['C4']['hydrogen'] = float(solution[y])
        ###/

        fuel_frac = fuel_comp[config['Fuel Mixture']]

        if sum(fuel_frac.values()) != 1:
            raise Exception("Fuel composition fractions must add up to 1")

        # create feed consumption rates dict
        feed_consumption = dict()
        for key in fuel_frac.keys():
            if key not in lhv.keys():
                feed_consumption[key] = 1 # TODO change this if know specific feed consumptions for meal, water, etc
            else:
                feed_consumption[key] = config['Thermal energy demand (MJ/kg clinker)'] * fuel_frac[key] / lhv[key] * config['Clinker-to-cement ratio'] * 1e3 # kg feed/ton cement
        # overwrite IEAGHG mix value (since cost data assumes consumption ratio of 1)
        feed_consumption['alt fuel (IEAGHG mix)'] = 1
        
        # add additional feeds 
        feed_consumption.update({
            'raw meal': 1,
            'process water': 1,
            'misc': 1,
        })

        if self.config['CSS'] == 'Oxyfuel':
            feed_consumption['oxygen'] = 191 * self.config['Clinker-to-cement ratio'] # Nm^3/t cement (NOTE Nm^3 = "normal cubic meter")
            feed_consumption['cooling water make-up'] = 1
        else:
            feed_consumption['oxygen'] = 0
            feed_consumption['cooling water make-up'] = 0
            
        # add electricity 
        feed_consumption['electricity'] = config['Electrical energy demand (kWh/t cement)']

        # TODO pass in LCOH
        lcoh = 1

        feed_cost = {
            # Fuels
            'coal': 3e-3 * lhv['coal'], # €/GJ coal --> €/kg coal
            'natural gas': 6e-3 * lhv['natural gas'], # €/kg ng
            'hydrogen': lcoh, # TODO want in $/kg
            'pet coke': self.btu_to_j(1, 2.81) * lhv['pet coke'],  # $/MMBtu --> $/MJ --> $/kg coke
            'alt fuel (IEAGHG mix)': 1, # €/ton cement
            'animal meal': 0,
            'sewage sludge': 0,
            'solvents': 0,
            'SRF (wet)': 0,
            'MBM (wet)': 0,
            'glycerin': (2812 + 2955) / 2 / 1e6, # https://www.procurementresource.com/resource-center/glycerin-price-trends#:~:text=In%20North%20America%2C%20the%20price,USD%2FMT%20in%20March%202022.
            # Raw materials
            'raw meal': 5 * config['Clinker-to-cement ratio'], # €/ton cement 
            'process water': 0.014, # €/ton cement
            'misc': 0.8, # €/ton cement
            'oxygen': 0, # ASSUMPTION
            'cooling water make-up': 0.3, # €/ton cement
        }



        # Electricity
        if config['ATB year'] == 2020:
            grid_year = 2025
        elif config['ATB year'] == 2025:
            grid_year = 2030
        elif config['ATB year'] == 2030:
            grid_year = 2035
        elif config['ATB year'] == 2035:
            grid_year = 2040
            
        # Read in csv for grid prices
        grid_prices = pd.read_csv(os.path.join(os.path.split(__file__)[0], 'examples/H2_Analysis/annual_average_retail_prices.csv'),index_col = None,header = 0)
        elec_price = grid_prices.loc[grid_prices['Year']==grid_year,config['site location']].tolist()[0] # $/MWh?
        elec_price *= 1e-3 # $/kWh

        # TODO pass in as configurations
        # if configurations['Renewable electricity']:
        #     elec_price = 0
        
        feed_cost['electricity'] = elec_price

        # ////////////// waste ////////////////
        # TODO: cost of cement kiln dust disposal? could be included already in some of the other costs

        # ///////////// unit conversions //////////// € --> $ 

        for key, value in feed_cost.items():
            if key == 'electricity' or key == 'pet coke': # these have already been converted
                continue 
            feed_cost[key] = self.eur2013(1, value)
        
        # add units
        feed_units = {
        # Fuels
            'coal': 'kg',
            'natural gas': 'kg',
            'hydrogen': 'kg', # TODO is this right?
            'pet coke': 'kg',
            'alt fuel (IEAGHG mix)': 'units',
            'animal meal': 'n/a',
            'sewage sludge': 'n/a',
            'solvents': 'n/a',
            'SRF (wet)': 'n/a',
            'MBM (wet)': 'n/a',
            'glycerin': 'kg',
            # Raw materials
            'raw meal': 'units', 
            'process water': 'units',
            'misc': 'units',
            'oxygen': 'Nm^3', # TODO might want to change this
            'cooling water make-up': 'units',
            'electricity': 'kWh',
        }

        # //////////////// fixed //////////////
        ## fixed ($/year)
        
        ###\ CEMCAP spreadsheet
        num_workers = 100
        cost_per_worker = 60 # kEUR/worker/year
        operational_labor = self.eur2013(1e3, num_workers * cost_per_worker) # k€ --> $
        maintenance_equip = self.eur2013(1e6, 5.09) # M€ --> $
        maintenance_labor = 0.4 * maintenance_equip # $
        admin_support = 0.3 * (operational_labor + maintenance_labor) 
        ###/

        other_opex = [operational_labor, maintenance_equip, maintenance_labor, admin_support]
        return feed_consumption, feed_cost, feed_units, other_opex
    
    def lca(self):
        
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
    
        ef = {
            ###\ source: Emission factors for fuel
            # ef = emission factor (g/MMBtu --> g/MJ; from the above source)
            'coal': self.btu_to_j(1, 89920),
            'natural gas': self.btu_to_j(1, 59413),
            'hydrogen': None,
            'pet coke': self.btu_to_j(1, 106976),
            'waste': self.btu_to_j(1, 145882),
            'tire': self.btu_to_j(1, 60876),
            'solvent': self.btu_to_j(1, 72298),
            ###/

            ###\ source: https://backend.orbit.dtu.dk/ws/portalfiles/portal/161972551/808873_PhD_thesis_Morten_Nedergaard_Pedersen_fil_fra_trykkeri.pdf (table 3-2)
            # TODO look more into the specifics of these emission reportings
            '''
                Carbon-neutral fuels, as defined by the European commission, are essentially biomass 
                which include agricultural and forestry biomass, biodegradable municipal waste, animal
                waste, paper waste [20] (Table 3). Certain authors argue that, in fact, burning these
                carbon-neutral waste can be even regarded as a GHG sink because they would 
                otherwise decay to form methane which is much a more powerful GHG than CO2[17], 
                [21]. Waste materials derived from fossil fuels such as solvent, plastics, used 
                tyres are not regarded as carbon-neutral. However, it is important to note that
                transferring waste fuels from incineration plants to cement kiln results in a 
                significant net CO2 reduction because cement kilns are more efficient. Another
                advantage is that no residues are generated since the ashes are completely 
                incorporated in clinker [21]
            '''
            'SRF (wet)': 9,
            'MBM (wet)': 0,
            ###/

            ###\ https://www.sciencedirect.com/science/article/pii/S1540748910003342#:~:text=Glycerol%20has%20a%20very%20high,gasoline%2C%20respectively%20%5B5%5D.
            'glycerin':  0.073 * 1e3 / lhv['glycerin'], # g CO2/g glycerol --> g CO2/kg glycerol --> g CO2/MJ glycerol
            # NOTE this is an incredibly crude estimate -- want to find a better source that is more applicable to cement/concrete
            #   see section 3.1 for assumptions/measurement setup
            ###/
        }

        # convert units
        for key, value in ef.items():
            if value is None:
                continue
            ef[key] = self.btu_to_j(1e-6 * 1e3, value) # g/MMBTU --> kg/J
        
        ###\ source: Emission factors for fuel  
        calcination_emissions = 553 # kg/tonne cem, assuming cli/cement ratio of 0.95 
        ###/

        ###\ source: Emission factors for electricity
        electricity_ef = 355 # kg/kWh
        ###/

        ef['electricity'] = electricity_ef

        # TODO quantify the impact of quarrying, raw materials, etc on emissions

    def run_profast_for_cement(
        self,
        hopp_dict=None,
        lcoh=6.79, 
        hydrogen_annual_production=1e20,  # default value, ensures there is always plenty of hydrogen  
    ):
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
        if hopp_dict is not None and hopp_dict.save_model_input_yaml:
            input_dict = { # TODO make sure this is in the right format
                'levelized_cost_hydrogen': lcoh,
                'hydrogen_annual_production': hydrogen_annual_production,
                'configuration dictionary': self.config,
                'atb_year': self.config['ATB year'],
                'site_name': self.config['site location'],
            }

            hopp_dict.add('Models', {'steel_LCOS': {'input_dict': input_dict}})

        # TODO is this necissary?
        if self.feed_consumption['hydrogen']  != 0:
            # determine if hydrogen is limiting the production of cement, and the resulting plant capacity
            max_cement_production_capacity_mtpy = min(self.config['Cement Production Rate (annual)'] / self.config['Plant capacity factor'], \
                                                  hydrogen_annual_production / self.feed_consumption['hydrogen'])
        else:
            max_cement_production_capacity_mtpy = self.config['Cement Production Rate (annual)'] # ton/year
         
        print('checking plant capacity....')
        print(self.config['Cement Production Rate (annual)'] / self.config['Plant capacity factor'])
        print(hydrogen_annual_production / self.feed_consumption['hydrogen'])
        print(f'actual plant capacity: {max_cement_production_capacity_mtpy}')
        
        # TODO cleaner way to do this?
        self.feed_cost['hydrogen'] = lcoh
       
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
        
        # ------------------------------ ProFAST ------------------------------
        # Set up ProFAST
        pf = ProFAST.ProFAST('blank')
        
        gen_inflation = 0.00
        pf.set_params('commodity',{"name":'Cement',"unit":"metric tonnes (t)","initial price":1000,"escalation":gen_inflation})
        pf.set_params('capacity',max_cement_production_capacity_mtpy / 365) # convert from ton/yr --> ton/day
        pf.set_params('operating life',self.config['Plant lifespan'])
        pf.set_params('installation cost',{"value": self.installed_costs,"depr type":"Straight line","depr period":4,"depreciable":False})
        pf.set_params('non depr assets', self.land_cost) 
        pf.set_params('long term utilization',self.config['Plant capacity factor'])
        
        # TODO: not sure how these fit into the model given in the paper
        pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
        pf.set_params('installation months', self.config['Construction time (months)']) # source: CEMCAP
        pf.set_params('analysis start year',2022) # is this ok? financials are based on 2013 conversion rates

            ###\
        pf.set_params('credit card fees',0)
        pf.set_params('sales tax',0) 
            ###/ assuming these are relevant only for the sale of the product?

        pf.set_params('rent',{'value':0,'escalation':gen_inflation})
            # is this different from land cost?
        pf.set_params('property tax and insurance percent',0)

        pf.set_params('total income tax rate',0.27)
        pf.set_params('capital gains tax rate',0.15)
        ###\
        pf.set_params('sell undepreciated cap',True)
        pf.set_params('tax losses monetized',True)
        pf.set_params('operating incentives taxable',True)
        ###/ leave these as True?

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
        # NOTE: in the document these values were given in EUR/t cem, so I am just going to multiply
        # them by the annual production capacity of the plant (at plant capacity rate)
        # NOTE: operating labor cost includes maintenance labor cost, according to the paper
        pf.add_fixed_cost(name="Annual Operating Labor Cost",usage=1,unit='$/year', cost=self.operational_labor,escalation=gen_inflation)
        pf.add_fixed_cost(name="Maintenance Labor Cost",usage=1,unit='$/year', cost=self.maintenance_labor,escalation=gen_inflation)
        pf.add_fixed_cost(name="Administrative & Support Labor Cost",usage=1,unit='$/year', cost=self.admin_support,escalation=gen_inflation)
        pf.add_fixed_cost(name="Property tax and insurance",usage=1,unit='$/year', cost=self.config['Taxation and insurance'] * self.tpc,escalation=0.0) 
        
        # ------------------------------ Add feedstocks, note the various cost options ------------------------------
        # NOTE feedstocks without consumption data have a usage of 1 (i.e. already in the desired units)
        for key, value in self.feed_units.items():
            pf.add_feedstock(name=key, usage=self.feed_consumption[key], unit=f'{self.feed_units[key]} per ton cement',cost=self.feed_cost[key],escalation=gen_inflation)

        # TODO add these to dictionary
        pf.add_feedstock(name='Maintenance Materials',usage=1.0,unit='Units per ton of cement',cost=self.maintenance_equip / self.config['Cement Production Rate (annual)'],escalation=gen_inflation)
        pf.add_feedstock(name='Raw materials',usage=1.0,unit='kg per ton cem',cost=self.feed_cost['raw meal'] * self.config['Clinker-to-cement ratio'],escalation=gen_inflation)
        
        # ------------------------------ Solve for breakeven price ------------------------------
        solution = pf.solve_price()

        # ------------------------------ Organizing Return Values ------------------------------
        summary = pf.summary_vals

        price_breakdown = pf.get_cost_breakdown()
        
        # TODO update manual cost breakdown

        # CAPEX
    
        # price_breakdown_crushing_plant = price_breakdown.loc[price_breakdown['Name']=='crushing plant','NPV'].tolist()[0]
        # price_breakdown_storage_convey_raw_material = price_breakdown.loc[price_breakdown['Name']=='storage, conveying raw material','NPV'].tolist()[0]  
        # price_breakdown_grinding_plant_raw_meal = price_breakdown.loc[price_breakdown['Name']=='grinding plant, raw meal','NPV'].tolist()[0] 
        # price_breakdown_storage_conveyor_silo = price_breakdown.loc[price_breakdown['Name']=='storage, conveyor, silo','NPV'].tolist()[0]     
        # price_breakdown_kiln_plant = price_breakdown.loc[price_breakdown['Name']=='kiln plant','NPV'].tolist()[0] 
        # price_breakdown_grinding_plant_cli = price_breakdown.loc[price_breakdown['Name']=='grinding plant, clinker','NPV'].tolist()[0] 
        # price_breakdown_silo = price_breakdown.loc[price_breakdown['Name']=='silo','NPV'].tolist()[0] 
        # price_breakdown_packaging_conveyor_loading = price_breakdown.loc[price_breakdown['Name']=='packaging plant, conveyor, loading, storing','NPV'].tolist()[0]  
        # price_breakdown_mill_silo = price_breakdown.loc[price_breakdown['Name']=='coal mill, silo','NPV'].tolist()[0]
        # price_breakdown_installation = price_breakdown.loc[price_breakdown['Name']=='Installation cost','NPV'].tolist()[0]
    
        # # fixed OPEX
        # price_breakdown_labor_cost_annual = price_breakdown.loc[price_breakdown['Name']=='Annual Operating Labor Cost','NPV'].tolist()[0]  
        # price_breakdown_labor_cost_maintenance = price_breakdown.loc[price_breakdown['Name']=='Maintenance Labor Cost','NPV'].tolist()[0]  
        # price_breakdown_labor_cost_admin_support = price_breakdown.loc[price_breakdown['Name']=='Administrative & Support Labor Cost','NPV'].tolist()[0] 
        # price_breakdown_proptax_ins = price_breakdown.loc[price_breakdown['Name']=='Property tax and insurance','NPV'].tolist()[0]
        
        # # variable OPEX
        # price_breakdown_maintenance_materials = price_breakdown.loc[price_breakdown['Name']=='Maintenance Materials','NPV'].tolist()[0]  
        # price_breakdown_water = price_breakdown.loc[price_breakdown['Name']=='process water','NPV'].tolist()[0] 
        # price_breakdown_raw_materials = price_breakdown.loc[price_breakdown['Name']=='Raw materials','NPV'].tolist()[0]
        # price_breakdown_coal = price_breakdown.loc[price_breakdown['Name']=='coal','NPV'].tolist()[0]
        # price_breakdown_alt_fuel = price_breakdown.loc[price_breakdown['Name']=='alternative fuel','NPV'].tolist()[0]
        # price_breakdown_electricity = price_breakdown.loc[price_breakdown['Name']=='electricity','NPV'].tolist()[0]
        # price_breakdown_misc = price_breakdown.loc[price_breakdown['Name']=='Misc.','NPV'].tolist()[0]
        # price_breakdown_taxes = price_breakdown.loc[price_breakdown['Name']=='Income taxes payable','NPV'].tolist()[0]\
        #     - price_breakdown.loc[price_breakdown['Name'] == 'Monetized tax losses','NPV'].tolist()[0]\

        # if gen_inflation > 0:
        #     price_breakdown_taxes = price_breakdown_taxes + price_breakdown.loc[price_breakdown['Name']=='Capital gains taxes payable','NPV'].tolist()[0]

        # # TODO look into (331-342) further -- probably has something to do with the parameters I'm confused about
        # # Calculate financial expense associated with equipment
        # price_breakdown_financial_equipment = price_breakdown.loc[price_breakdown['Name']=='Repayment of debt','NPV'].tolist()[0]\
        #     + price_breakdown.loc[price_breakdown['Name']=='Interest expense','NPV'].tolist()[0]\
        #     + price_breakdown.loc[price_breakdown['Name']=='Dividends paid','NPV'].tolist()[0]\
        #     - price_breakdown.loc[price_breakdown['Name']=='Inflow of debt','NPV'].tolist()[0]\
        #     - price_breakdown.loc[price_breakdown['Name']=='Inflow of equity','NPV'].tolist()[0]    
            
        # # Calculate remaining financial expenses
        # price_breakdown_financial_remaining = price_breakdown.loc[price_breakdown['Name']=='Non-depreciable assets','NPV'].tolist()[0]\
        #     + price_breakdown.loc[price_breakdown['Name']=='Cash on hand reserve','NPV'].tolist()[0]\
        #     + price_breakdown.loc[price_breakdown['Name']=='Property tax and insurance','NPV'].tolist()[0]\
        #     - price_breakdown.loc[price_breakdown['Name']=='Sale of non-depreciable assets','NPV'].tolist()[0]\
        #     - price_breakdown.loc[price_breakdown['Name']=='Cash on hand recovery','NPV'].tolist()[0]
        
        # # list containing all of the prices established above
        # breakdown_prices = [price_breakdown_crushing_plant, 
        #                     price_breakdown_storage_convey_raw_material, 
        #                     price_breakdown_grinding_plant_raw_meal, 
        #                     price_breakdown_storage_conveyor_silo, 
        #                     price_breakdown_kiln_plant, 
        #                     price_breakdown_grinding_plant_cli, 
        #                     price_breakdown_silo, 
        #                     price_breakdown_packaging_conveyor_loading, 
        #                     price_breakdown_mill_silo, 
        #                     price_breakdown_installation, 
        #                     price_breakdown_labor_cost_annual, 
        #                     price_breakdown_labor_cost_maintenance, 
        #                     price_breakdown_labor_cost_admin_support, 
        #                     price_breakdown_proptax_ins, 
        #                     price_breakdown_maintenance_materials, 
        #                     price_breakdown_water, 
        #                     price_breakdown_raw_materials, 
        #                     price_breakdown_coal, 
        #                     price_breakdown_alt_fuel, 
        #                     price_breakdown_electricity, 
        #                     price_breakdown_misc, 
        #                     price_breakdown_taxes, 
        #                     price_breakdown_financial_equipment, 
        #                     price_breakdown_financial_remaining]
                    
        # price_breakdown_check = sum(breakdown_prices)

       
        # # a neater way to implement is add to price_breakdowns but I am not sure if ProFAST can handle negative costs
        # # TODO above comment might not be an issue, so might not have had to pull out all these values
            
        # bos_savings = 0 * (price_breakdown_labor_cost_admin_support) * 0.3 # TODO is this applicable for cement?

        # breakdown_prices.append(price_breakdown_check)
        # breakdown_prices.append(bos_savings) 

        # breakdown_categories = ['Raw Material Crushing CAPEX',
        #                         'Storage, Conveying Raw Material CAPEX',
        #                         'Grinding Plant, Raw Meal CAPEX', 
        #                         'Storage, Conveyor, Silo CAPEX',
        #                         'Kiln Plant CAPEX',
        #                         'Grinding Plant, Clinker CAPEX',
        #                         'Silo CAPEX',
        #                         'Packaging Plant, Conveyor, Loading, Storing CAPEX',
        #                         'Mill, Silo CAPEX',
        #                         'Installation Cost',
        #                         'Annual Operating Labor Cost (including maintenance?)',
        #                         'Maintenance Labor Cost (zero at the moment?)',
        #                         'Administrative & Support Labor Cost',
        #                         'Property tax and insurance',
        #                         'Maintenance Materials',
        #                         'Process Water',
        #                         'Raw Materials',
        #                         'coal',
        #                         'Alternative Fuel',
        #                         'energy', 
        #                         'Misc. Variable OPEX',
        #                         'Taxes',
        #                         'Equipment Financing',
        #                         'Remaining Financial',
        #                         'Total',
        #                         'BOS Savings (?)']
        
        # if len(breakdown_categories) != len(breakdown_prices):
        #     raise Exception("categories and prices lists have to be the same length")

        # cement_price_breakdown = dict()
        # for category, price in zip(breakdown_categories, breakdown_prices):
        #     cement_price_breakdown[f'cement price: {category} ($/ton)'] = price

        print(f"price breakdown (manual): {solution['price']}")
        print(f"price breakdown (paper): {self.eur2013(1, 50.9)}")
        print(f"price breakdown (CEMCAP spreadsheet, excluding carbon tax): {self.eur2013(1, 46.02)}")
        print(f"percent error from CEMCAP: {(solution['price'] - self.eur2013(1, 46.02))/self.eur2013(1, 46.02) * 100}%")
      
        # TODO what is the point of this line here?
        price_breakdown = price_breakdown.drop(columns=['index','Amount'])

        cement_price_breakdown = dict() # TODO fix the commented code so that includes the new stuff

        cement_annual_capacity = self.config['Cement Production Rate (annual)'] * self.config['Plant capacity factor']
        
        # return(solution,summary,price_breakdown,cement_annual_capacity,cement_price_breakdown,total_capex)

        # steel_economics_from_profast,
        # steel_economics_summary,
        # profast_steel_price_breakdown,
        # steel_annual_capacity,
        # steel_price_breakdown,
        # steel_plant_capex
 
        cement_breakeven_price = solution.get('price')

        # Calculate margin of what is possible given hydrogen production and actual steel demand
        #steel_production_capacity_margin_mtpy = hydrogen_annual_production/1000/hydrogen_consumption_for_steel - steel_annual_capacity
        cement_production_capacity_margin_pc = (hydrogen_annual_production / 1000 / self.feed_consumption['hydrogen'] - cement_annual_capacity) \
                                                / cement_annual_capacity * 100


        if hopp_dict is not None and hopp_dict.save_model_output_yaml:
            output_dict = {
                'steel_economics_from_profast': solution,
                'steel_economics_summary': summary,
                'steel_breakeven_price': cement_breakeven_price,
                'steel_annual_capacity': cement_annual_capacity,
                'steel_price_breakdown': cement_price_breakdown,
                'steel_plant_capex': self.total_capex,
            }

            hopp_dict.add('Models', {'steel_LCOS': {'output_dict': output_dict}})


        ###\ write files (for testing)
        # path = Path('C:\\Users\\esharafu\\Documents\\cement_econ.csv')
        # thing = pd.DataFrame(cement_price_breakdown,index=[0]).transpose()
        # thing.to_csv(path)

        path = Path('C:\\Users\\esharafu\\Documents\\profast_breakdown.csv')
        thing = pd.DataFrame(price_breakdown)
        thing.to_csv(path)
        ###/

        return hopp_dict, solution, summary, price_breakdown, cement_breakeven_price, \
            cement_annual_capacity, cement_production_capacity_margin_pc, cement_price_breakdown

    # ---------- Other Methods ----------
    def __oxy_combustion_css(self): # TODO currently implementing this into __init__()
        # //////////// Oxyfuel Combustion ////////////////
        # https://www.mdpi.com/1996-1073/12/3/542#app1-energies-12-00542 -- supplementary materials
        ''' 
        NOTES:
        * EC (equipment cost) + IC (installation cost) = TDC (total direct cost)
        * cost basis = 2014 EUR 
        * values coded in are first in kEUR but converted to $
        * 'false air' = air that has leaked into the flue gas (which ideally would've been 
        pure water and carbon dioxide)
        '''
        ### Plant info
        economic_life = 25 # years (TODO include??)
        construction_time_oxy = 3 # years
        discount_rate_oxy = 0.08
        # TODO where does this fit it?
            # Allocation of CO2 capture construction costs by year 1 (%) = 40/30/30
    
        ### CAPEX
        # NOTE these are equipment costs and not direct costs
        co2_capture_equip_oxy = {
            # Oxyfuel core process units
            'OXY: Clinker cooler, kiln hood and sealings (core process)': 2944 + 102 + 160 + 160,
            'OXY: Fans, compressors and blowers (core process)': 233 + 355 + 74 + 1880,
            'OXY: Other equipment (core process)': 70 + 441 + 1013 + 19461,
            # Oxyfuel waste heat recovery system
            'OXY: Heat exchangers (waste heat recovery)': 33 + 1376 + 77 + 198 + 45 + 79 + 781 + 520 + 24 + 337,
            'OXY: Tanks and vessels (waste heat recovery)': 800,
            'OXY: Electric generators (waste heat recovery)': 3984,
            'OXY: Pumps (waste heat recovery)': 156,
            # CO2 Purification unit (CPU)
            'OXY: Fans, compressors and expanders (CPU)': 17369 + 2572 + 696,
            'OXY: Tanks and vessels (CPU)': 252 + 179 + 117 + 118 + 99,
            'OXY: Heat exchangers (CPU)': 37 + 31 * 3 + 30 + 75 + 849,
            'OXY: Pumps (CPU)': 351,
            'OXY: Other equipment (CPU)': 112,
            'OXY: Cooling tower (CPU)': 588,
        }

        total_direct_costs_oxy = 71595 # sum of the direct costs column in supplementary materials
        process_contingency_oxy = total_direct_costs_oxy * (0.3 + 0.12)
        indirect_costs_oxy = total_direct_costs_oxy * 0.14
        owners_costs_oxy = total_direct_costs_oxy * 0.07
        project_contingencies_oxy = total_direct_costs_oxy * 0.15

        tpc_oxy = total_direct_costs_oxy + process_contingency_oxy + indirect_costs_oxy \
            + owners_costs_oxy + project_contingencies_oxy
        
        ### OPEX
        # Fixed
        annual_maintenance_cost_oxy = tpc_oxy * 0.025
        maintenance_labor_oxy = annual_maintenance_cost_oxy * 0.4
        taxes_insurance_oxy = tpc_oxy * 0.02
        num_workers_oxy = 20 
        cost_per_worker_oxy = 60 # k€/person/year
        operational_labor_oxy = num_workers_oxy * cost_per_worker_oxy 
        admin_support_oxy = 0.3 * (operational_labor_oxy + maintenance_labor_oxy) 

        # Variable 
        ###\ https://www.sciencedirect.com/science/article/pii/S0306261922005529#b0150
        thermal_energy_demand_oxy = 3.349 # MJ / kg cli
        electricity_demand_oxy = 150 * self.config['Clinker-to-cement ratio'] # kWh/t cem
        o2_frac_oxy = 191 * self.config['Clinker-to-cement ratio'] # Nm^3/t cement (NOTE Nm^3 = "normal cubic meter")
        ###/

    def eur2013(self, multiplyer, *costs):
        ''' 
        Converts monetary values from EUR to USD

        multiplyer argument allows you to account for prefix (ex: M, k)

        works for individual values or an iterable of values

        NOTE: conversion factor is the average from 2013, which was the cost basis
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

    def eur2014(self, multiplyer, *costs):
        ''' 
        Converts monetary values from EUR to USD

        multiplyer argument allows you to account for prefix (ex: M, k)

        works for individual values or an iterable of values

        NOTE: conversion factor is the average from 2014, which was the cost basis
        year given in the paper

        source: https://www.exchangerates.org.uk/EUR-USD-spot-exchange-rates-history-2014.html

        '''
        conversion_factor = 1.3283 # USD/EUR
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


if __name__ == '__main__':
    plant = ConcretePlant(css='None')
    hopp_dict, solution, summary, price_breakdown, cement_breakeven_price, \
    cement_annual_capacity, cement_production_capacity_margin_pc, cement_price_breakdown = \
    plant.run_profast_for_cement()












### outline (ignore)
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
    

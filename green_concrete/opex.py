from green_concrete.convert import *
import pandas as pd
import os

def opex(self): 
    '''
    Calculates and assigns OpEx values to a ConcretePlant instance

    Source: CEMCAP and IEAGHG report, unless otherwise specified 

    ADDING A NEW FUEL COMPOSITION
        1. if using fuels that already exist in feed_units, then 
        can just add a new sub-dictionary to fuel_comp
        2. if using a fuel that does not already exist in feed_units,
        this new fuel must be added to feed_units, lhv, and feed_costs

    ''' 
     
    
    
    # --------------- Variable OPEX / feedstocks ----------------
    feed_units = {
    # Fuels
        'coal': 'kg',
        'natural gas': 'kg',
        'hydrogen': 'kg', 
        'pet coke': 'kg',
        'alt fuel (IEAGHG mix)': 'units',
        'animal meal': 'n/a',
        'sewage sludge': 'n/a',
        'solvents': 'n/a',
        'SRF (wet)': 'kg',
        'MBM (wet)': 'kg',
        'glycerin': 'kg',
        'tires': 'kg',
        
        # Raw materials
        'raw meal': 'units', 
        'process water': 'units',
        'misc': 'units',
        'oxygen': 'Nm^3', # TODO might want to change this
        'cooling water make-up': 'units',
        'raw meal': 'units',

        # other
        'grid electricity': 'kWh',
        'renewable electricity': 'kWh',
    }
    
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

    feed_costs = {
        # Fuels
        'coal': 3e-3 * lhv['coal'], # €/GJ coal --> €/kg coal
        'natural gas': 6e-3 * lhv['natural gas'], # €/kg ng
        'hydrogen': None, # $/kg, will be inserted in run_profast_for_cement()
        'pet coke': btu_to_j(1, 2.81) * lhv['pet coke'],  # $/MMBtu --> $/MJ --> $/kg coke
        'alt fuel (IEAGHG mix)': 1, # €/ton cement
        'animal meal': 0,
        'sewage sludge': 0,
        'solvents': 0,
        'tires': 0,
        'SRF (wet)': 0,
        'MBM (wet)': 0,
        'glycerin': (2812 + 2955) / 2 / 1e6, # https://www.procurementresource.com/resource-center/glycerin-price-trends#:~:text=In%20North%20America%2C%20the%20price,USD%2FMT%20in%20March%202022.
        # Raw materials
        'raw meal': 5 * self.config['Clinker-to-cement ratio'], # €/ton cement 
        'process water': 0.014, # €/ton cement
        'misc': 0.8, # €/ton cement
        'oxygen': 0, # ASSUMPTION
        'cooling water make-up': 0.3, # €/ton cement
    }

    # SOURCES:
    # Canada: Synergizing hydrogen and cement industries for Canada's climate plan - case study
    # IEAGHG: https://ieaghg.org/publications/technical-reports/reports-list/9-technical-reports/1016-2013-19-deployment-of-ccs-in-the-cement-industry 
   
    fuel_comp = {
        # COMPOSITION 1: Canada Reference (100% coal)
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
            'tires': 0,
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
            'tires': 0,
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
            'tires': 0,
        },

        # COMPOSITION 4: Canada Hydrogen-Enriched Natural Gas Substitution
        # see system solved below
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
            'tires': 0,
        },      

        # COMPOSITION 5: Experimental Climate Neutral Plant: https://www.heidelbergmaterials.com/en/pr-01-10-2021
        # NOTE assuming energy basis here
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
            'tires': 0,
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

    # select fuel composition configuration to use
    fuel_frac = fuel_comp[self.config['Fuel Mixture']]

    # add fuels to feed_consumption dict
    feed_consumption = dict()
    for key in lhv.keys():
        feed_consumption[key] = self.config['Thermal energy demand (MJ/kg clinker)'] * fuel_frac[key] / lhv[key] * self.config['Clinker-to-cement ratio'] * 1e3 # kg feed/ton cement
    
    # add remaining feeds and IEAGHG fuel mix
    feed_consumption.update({
        'raw meal': 1,
        'process water': 1,
        'misc': 1,
        'alt fuel (IEAGHG mix)': 1,
    })

    # /////////// CSS FEEDS ///////////
    if self.config['CSS'] == 'Oxyfuel':
        feed_consumption['oxygen'] = 1148 * 365 / 1000 / self.config['Cement Production Rate (annual)'] # tO2/day --> kg/t cement 
        feed_consumption['cooling water make-up'] = 1
    elif self.config['CSS'] == 'CaL (tail-end)': 
        feed_consumption['oxygen'] = 440 * self.config['Clinker-to-cement ratio'] # kgO2/t cli --> kg/t cement
        feed_consumption['cooling water make-up'] = 0.9
    else:
        feed_consumption['oxygen'] = 0
        feed_consumption['cooling water make-up'] = 0
        
    # //////////// Electricity /////////////
    if self.config['Renewable electricity']:
        feed_consumption['renewable electricity'] = self.config['Electrical energy demand (kWh/t cement)']
        feed_consumption['grid electricity'] = 0
    else: 
        feed_consumption['renewable electricity'] = 0
        feed_consumption['grid electricity'] = self.config['Electrical energy demand (kWh/t cement)']

    if self.config['ATB year'] == 2020:
        grid_year = 2025
    elif self.config['ATB year'] == 2025:
        grid_year = 2030
    elif self.config['ATB year'] == 2030:
        grid_year = 2035
    elif self.config['ATB year'] == 2035:
        grid_year = 2040
        
    # Read in csv for grid prices
    grid_prices = pd.read_csv(os.path.join(os.path.split(__file__)[0], '..\\examples\\H2_Analysis\\annual_average_retail_prices.csv'),index_col = None,header = 0)
    elec_price = grid_prices.loc[grid_prices['Year']==grid_year,self.config['site location']].tolist()[0] # $/MWh?
    elec_price *= 1e-3 # $/kWh
    
    feed_costs['grid electricity'] = elec_price
    
    # this will be overwritten if renewable electricity is  used
    feed_costs['renewable electricity'] = None

    # ////////////// waste ////////////////
    # TODO: cost of cement kiln dust disposal? could be included already in some of the other costs

    # ///////////// unit conversions //////////// € --> $ 
    for key, value in feed_costs.items():
        if 'electricity' in key or key == 'pet coke' or key == 'glycerin' or value is None: # these have already been converted
            continue 
        feed_costs[key] = eur2013(1, value)

    # ---------------- Fixed OPEX -----------------
    ## fixed ($/year)
    if self.config['CSS'] == 'None':
        num_workers = 100
    else:
        num_workers = 120 # CEMCAP spreadsheet

    cost_per_worker = 60 # kEUR/worker/year
    operational_labor = eur2013(1e3, num_workers * cost_per_worker) # k€ --> $
    maintenance_equip = eur2013(1e6, 5.09) # M€ --> $
    maintenance_labor = 0.4 * maintenance_equip # $
    admin_support = 0.3 * (operational_labor + maintenance_labor) 

    # ------------------ tests -----------------
    for key in feed_consumption.keys():
        if key not in feed_costs.keys() or key not in feed_units.keys():
            raise Exception(f"{key} was found in feed_consumption, but not in either feed_costs or feed_units")
    for key in feed_costs.keys():
        if key not in feed_consumption.keys() or key not in feed_units.keys():
            raise Exception(f"{key} was found in feed_costs, but not in either feed_consumption or feed_units")
    for key in feed_units.keys():
        if key not in feed_costs.keys() or key not in feed_consumption.keys():
            raise Exception(f"{key} was found in feed_units, but not in either feed_costs or feed_consumption")
    if sum(fuel_frac.values()) != 1:
        raise Exception("Fuel composition fractions must add up to 1")
        
    return feed_consumption, feed_costs, feed_units, operational_labor, maintenance_equip, maintenance_labor, admin_support

from green_concrete.convert import * 
   
def capex(self):
    '''
    Calculates and assigns CapEx values to a ConcretePlant instance

    Source: CEMCAP and IEAGHG report, unless otherwise specified 

    NOTE all values in M€
    
    NOTE currently this does not include land property (in particular the quarry), 
    emerging emission abatement technology, developing cost (power & water supply)

    '''
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

    ### installation
    total_direct_costs = 149.82 # CEMCAP, adjusted from 2013 --> 2014 using CEPCI index
    owners_costs = total_direct_costs * 0.07
    indirect_costs = total_direct_costs * 0.14
    project_contingencies = total_direct_costs * 0.15
    tpc = total_direct_costs + owners_costs + indirect_costs + project_contingencies
    land_cost = 0 # TODO
    total_capex = tpc + land_cost
    
    # ////////// unit conversions ////////////// € --> $
    for key, value in equip_costs.items():
        equip_costs[key] = eur2013(1e6, value)
    tpc, total_capex, total_direct_costs, land_cost = eur2013(1e6, tpc, total_capex, total_direct_costs, land_cost)

    # Carbon Capture Options
    if self.config['CSS'] == 'Oxyfuel':
        return *oxyfuel_capex(equip_costs, tpc, total_capex, total_direct_costs), land_cost
    elif self.config['CSS'] == 'Calcium looping':
        pass
    elif self.config['CSS'] == 'None':
        return equip_costs, tpc, total_capex, total_direct_costs, land_cost 
    else: 
        raise Exception('Invalid CSS Scenario')

def oxyfuel_capex(equip_costs, tpc, total_capex, total_direct_costs):
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
    total_capex_oxy = tpc_oxy # assuming no extra land needed for CO2 capture plant
    
    # ////////// unit conversions ////////////// € --> $
    for key, value in co2_capture_equip_oxy.items():
        co2_capture_equip_oxy[key] = eur2014(1e3, value)
    tpc_oxy, total_direct_costs_oxy = eur2014(1e3, tpc_oxy, total_direct_costs_oxy)

    # update reference plant CAPEX TODO only considering tpc and equipment for now
    equip_costs.update(co2_capture_equip_oxy)
    tpc += tpc_oxy
    total_capex += tpc_oxy
    total_direct_costs += total_direct_costs_oxy

    return equip_costs, tpc, total_capex, total_direct_costs
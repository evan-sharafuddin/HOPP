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
    if self.config['CCUS'] == 'Oxyfuel':
        return *_oxyfuel_capex(equip_costs, tpc, total_capex, total_direct_costs), land_cost
    elif self.config['CCUS'] == 'CaL (tail-end)':
        return *_cal_tail_end_capex(equip_costs, tpc, total_capex, total_direct_costs), land_cost
    elif self.config['CCUS'] == 'None':
        return equip_costs, tpc, total_capex, total_direct_costs, land_cost 
    else: 
        raise Exception('Invalid CCUS Scenario')

def _oxyfuel_capex(equip_costs, tpc, total_capex, total_direct_costs):
    # https://www.mdpi.com/1996-1073/12/3/542#app1-energies-12-00542 -- supplementary materials
    ''' 
    Calculates CapEx values specific to the addition of an Oxyfuel CCUS system
    
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
        # NOTE Ignoring ASU, cost of 19461
        'OXY: Other equipment (core process)': 70 + 441 + 1013,
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

    total_direct_costs_oxy = 52134 # sum of the direct costs column in supplementary materials
    process_contingency_oxy = total_direct_costs_oxy * 0.42
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
    total_capex += total_capex_oxy
    total_direct_costs += total_direct_costs_oxy

    return equip_costs, tpc, total_capex, total_direct_costs

def _cal_tail_end_capex(equip_costs, tpc, total_capex, total_direct_costs):
    ''' 
    Calculates CapEx values specific to the addition of an Oxyfuel CCUS system
    
    NOTES:
    * EC (equipment cost) + IC (installation cost) = TDC (total direct cost)
    * cost basis = 2014 EUR 
    * values coded in are first in kEUR but converted to $
    * 'false air' = air that has leaked into the flue gas (which ideally would've been 
    pure water and carbon dioxide)

    SOURCE: CEMCAP d4.6 article and supplementary information
    '''

    ### CAPEX
    # NOTE these are equipment costs and not direct costs
    co2_capture_equip_cal = {
        # Limestone grinding plant 
        'CaL TE: Limestone grinding plant': 2484.2,

        'CaL TE: Carbonator fan': 551.6,
        'CaL TE: Carbonator reactor': 7522,
        'CaL TE: Condensate pump': 19.5,
    
        'CaL TE: CO2 fan': 295.7,
        'CaL TE: Calciner reactor': 5273,
        'CaL TE: Feedwater pump': 307.2,

        'CaL TE: Dearator': 194.1,
        'CaL TE: Regenerative feedwater preheater': 144.2,
        'CaL TE: Condenser': 671.8,
        'CaL TE: Cooling tower for steam cycle condensor heat rejection': 817.5,
        'CaL TE: Steam turbine and electric generator': 8550.9,
        'CaL TE: CO2 compression and purification unit': 31873,

        # NOTE ignoring ASU for now

        'CaL TE: Heat exchangers': 48.8 + 305.1 + 12.8 + 37 + 6.4 + 9.2,
    }

    total_direct_costs_cal = 81020.6 # sum of TEC and IC numbers in CEMCAP d4.6 supplementary info
    total_direct_costs_steam_turbine = 9423.8 
    process_contingency_cal = (total_direct_costs_cal - total_direct_costs_steam_turbine) * 0.32 \
        + total_direct_costs_steam_turbine * 0.05
    cost_avoided_no_asu = total_direct_costs_cal / 124.8
    
    # these values were with ASU included, so assuming they are proportional to TDC
    indirect_costs_cal = 20.8 * cost_avoided_no_asu
    owners_costs_cal = 10.4 * cost_avoided_no_asu
    project_contingencies_cal = 22.3 * cost_avoided_no_asu

    tpc_cal = total_direct_costs_cal + process_contingency_cal + indirect_costs_cal \
        + owners_costs_cal + project_contingencies_cal
    total_capex_cal = tpc_cal # assuming no extra land needed

     # ////////// unit conversions ////////////// € --> $
    for key, value in co2_capture_equip_cal.items():
        co2_capture_equip_cal[key] = eur2014(1e3, value)
    tpc_cal, total_direct_costs_cal = eur2014(1e3, tpc_cal, total_direct_costs_cal)

    # update reference plant CAPEX TODO only considering tpc and equipment for now
    equip_costs.update(co2_capture_equip_cal)
    tpc += tpc_cal
    total_capex += tpc_cal
    total_direct_costs += total_direct_costs_cal

    return equip_costs, tpc, total_capex, total_direct_costs
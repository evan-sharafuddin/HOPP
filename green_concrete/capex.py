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

    # ///////// Oxyfuel CAPEX ////////
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
        equip_costs[key] = eur2013(1e6, value)
    for key, value in co2_capture_equip_oxy.items():
        co2_capture_equip_oxy[key] = eur2014(1e3, value)
    tpc, total_capex, installed_costs, land_cost = eur2013(1e6, tpc, total_capex, installed_costs, land_cost)
    tpc_oxy, total_direct_costs_oxy = eur2014(1e3, tpc_oxy, total_direct_costs_oxy) 
    
    if self.config['CSS'] == 'Oxyfuel':
        # update reference plant CAPEX TODO only considering tpc and equipment for now
        equip_costs.update(co2_capture_equip_oxy)
        tpc += tpc_oxy
        total_capex += tpc_oxy
        installed_costs += total_direct_costs_oxy

    return equip_costs, tpc, total_capex, installed_costs, land_cost 
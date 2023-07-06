from green_concrete.convert import btu_to_j

def lca(self):
    '''
    Performs a life cycle analysis on the carbon emissions associated with cement production
    
    
    '''
        
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
        'coal': btu_to_j(1, 89920),
        'natural gas': btu_to_j(1, 59413),
        'hydrogen': None,
        'pet coke': btu_to_j(1, 106976),
        'waste': btu_to_j(1, 145882),
        'tire': btu_to_j(1, 60876),
        'solvent': btu_to_j(1, 72298),
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
        ef[key] = btu_to_j(1e-6 * 1e3, value) # g/MMBTU --> kg/J
    
    ###\ source: Emission factors for fuel  
    calcination_emissions = 553 # kg/tonne cem, assuming cli/cement ratio of 0.95 
    ###/

    ###\ source: Emission factors for electricity
    electricity_ef = 355 # kg/kWh
    ###/

    ef['electricity'] = electricity_ef

    # TODO quantify the impact of quarrying, raw materials, etc on emissions
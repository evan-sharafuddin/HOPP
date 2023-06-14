# based off of steel_LCOS in hopp_tools_steel.py
# Evan Sharafuddin
import pandas as pd
import os

def  steel_LCOS(
    hopp_dict,
    levelized_cost_hydrogen,
    hydrogen_annual_production,
    steel_annual_production_rate_target_tpy,
    lime_unitcost,
    carbon_unitcost,
    iron_ore_pellet_unitcost,o2_heat_integration,atb_year,site_name
):
    if hopp_dict.save_model_input_yaml:
        input_dict = {
            'levelized_cost_hydrogen': levelized_cost_hydrogen,
            'hydrogen_annual_production': hydrogen_annual_production,
            'lime_unitcost': lime_unitcost,
            'carbon_unitcost': carbon_unitcost,
            'iron_ore_pellet_unitcost': iron_ore_pellet_unitcost,
            'o2_heat_integration':o2_heat_integration,
            'atb_year':atb_year,
            'site_name':site_name
        }

        hopp_dict.add('Models', {'steel_LCOS': {'input_dict': input_dict}})

    from run_profast_for_steel import run_profast_for_steel
    
    # Steel production break-even price analysis

    # Could connect these to other things in the model
    steel_capacity_factor = 0.9
    steel_plant_life = 30
    
    hydrogen_consumption_for_steel = 0.06596              # metric tonnes of hydrogen/metric tonne of steel production
    # Could be good to make this more conservative, but it is probably fine if demand profile is flat

    max_steel_production_capacity_mtpy = min(steel_annual_production_rate_target_tpy/steel_capacity_factor,hydrogen_annual_production/1000/hydrogen_consumption_for_steel)
    
    # Should connect these to something (AEO, Cambium, etc.)
    natural_gas_cost = 4                        # $/MMBTU

     # Specify grid cost year for ATB year
    if atb_year == 2020:
        grid_year = 2025
    elif atb_year == 2025:
        grid_year = 2030
    elif atb_year == 2030:
        grid_year = 2035
    elif atb_year == 2035:
        grid_year = 2040
        
    # Read in csv for grid prices
    grid_prices = pd.read_csv(os.path.join(os.path.split(__file__)[0], 'examples/H2_Analysis/annual_average_retail_prices.csv'),index_col = None,header = 0)
    elec_price = grid_prices.loc[grid_prices['Year']==grid_year,site_name].tolist()[0]
    # if site_name=='WY':
    #     elec_price = grid_prices.loc[grid_prices['Year']==grid_year,'TX'].tolist()[0]
    # else:
    #     elec_price = grid_prices.loc[grid_prices['Year']==grid_year,site_name].tolist()[0]
    
    

    #electricity_cost = lcoe - (((policy_option['Wind PTC']) * 100) / 3) # over the whole lifetime 
    
    steel_economics_from_profast,steel_economics_summary,profast_steel_price_breakdown,steel_annual_capacity,steel_price_breakdown,steel_plant_capex=\
        run_profast_for_steel(max_steel_production_capacity_mtpy,\
            steel_capacity_factor,steel_plant_life,levelized_cost_hydrogen,\
            elec_price,natural_gas_cost,lime_unitcost,
                carbon_unitcost,
                iron_ore_pellet_unitcost,
                o2_heat_integration)

    steel_breakeven_price = steel_economics_from_profast.get('price')

    # Calculate margin of what is possible given hydrogen production and actual steel demand
    #steel_production_capacity_margin_mtpy = hydrogen_annual_production/1000/hydrogen_consumption_for_steel - steel_annual_capacity
    steel_production_capacity_margin_pc = (hydrogen_annual_production/1000/hydrogen_consumption_for_steel - steel_annual_capacity)/steel_annual_capacity*100

    if o2_heat_integration !=1:
        if hopp_dict.save_model_output_yaml:
            output_dict = {
                'steel_economics_from_profast': steel_economics_from_profast,
                'steel_economics_summary': steel_economics_summary,
                'steel_breakeven_price': steel_breakeven_price,
                'steel_annual_capacity': steel_annual_capacity,
                'steel_price_breakdown': steel_price_breakdown,
                'steel_plant_capex':steel_plant_capex
            }

            hopp_dict.add('Models', {'steel_LCOS': {'output_dict': output_dict}})

    return hopp_dict, steel_economics_from_profast, steel_economics_summary, profast_steel_price_breakdown,steel_breakeven_price, steel_annual_capacity, steel_production_capacity_margin_pc,steel_price_breakdown
